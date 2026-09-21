#!/usr/bin/env python3
"""Check a live database against the relational schema conventions.

Reads the catalogue rather than the migration files, because the catalogue is what the
application runs on: a database that drifted from its migrations is exactly the case worth
catching, and the files cannot tell you it happened.

    python verify_schema.py --url "$DATABASE_URL"
    python verify_schema.py --url "$DATABASE_URL" --rules K,C --format json
    python verify_schema.py --url "$DATABASE_URL" --config path/to/schema-conventions.toml

Needs psycopg (v3) or psycopg2 for PostgreSQL. Exits non-zero when any rule fails, so it can be
the last line of a CI job.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

try:  # tomllib landed in 3.11; tomli is the backport.
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    try:
        import tomli as tomllib  # type: ignore
    except ModuleNotFoundError:
        tomllib = None  # type: ignore

POWERS_OF_TWO = {8, 16, 32, 64, 128, 256, 512, 1024, 2048}

# Tables the framework owns, whose shape is not ours to dictate. A project adds its own.
DEFAULT_IGNORED = {
    "schema_migrations", "migrations", "alembic_version", "flyway_schema_history",
    "jobs", "job_batches", "failed_jobs", "cache", "cache_locks", "sessions",
}


@dataclass
class Finding:
    rule: str
    level: str  # fail | warn | unverifiable
    subject: str
    detail: str


@dataclass
class Config:
    engine: str = "postgres"
    tenancy_enabled: bool = False
    tenant_column: str = ""
    tenant_table: str = ""
    role_keys: dict[str, str] = field(default_factory=dict)
    widths: dict[str, dict[str, Any]] = field(default_factory=dict)
    json_allowed: set[str] = field(default_factory=set)
    lifecycle: dict[str, str] = field(default_factory=dict)
    unique_exceptions: set[str] = field(default_factory=set)
    ignored_tables: set[str] = field(default_factory=lambda: set(DEFAULT_IGNORED))

    @classmethod
    def load(cls, path: Path | None) -> "Config":
        if path is None or not path.exists():
            return cls()
        if tomllib is None:
            sys.exit("A config was given but no TOML parser is available. pip install tomli")

        raw = tomllib.loads(path.read_text())
        project, tenancy = raw.get("project", {}), raw.get("tenancy", {})
        keys, columns = raw.get("keys", {}), raw.get("columns", {})
        lifecycle_raw = raw.get("lifecycle", {})

        lifecycle: dict[str, str] = {}
        for klass, tables in lifecycle_raw.items():
            for table in tables:
                lifecycle[table] = klass

        return cls(
            engine=project.get("engine", "postgres"),
            tenancy_enabled=tenancy.get("enabled", False),
            tenant_column=tenancy.get("column", ""),
            tenant_table=tenancy.get("table", ""),
            role_keys=keys.get("roles", {}),
            widths=columns.get("widths", {}),
            json_allowed=set(columns.get("json", {}).get("allowed", [])),
            lifecycle=lifecycle,
            unique_exceptions=set(raw.get("uniqueness", {}).get("exceptions", {})),
            ignored_tables=set(DEFAULT_IGNORED) | set(project.get("ignore_tables", [])),
        )


def singularise(table: str) -> str:
    if table.endswith("ies"):
        return table[:-3] + "y"
    if table.endswith("ses"):
        return table[:-2]
    return table[:-1] if table.endswith("s") else table


class Catalogue:
    """Everything the checks need, read in a handful of queries rather than one per rule."""

    def __init__(self, connection, config: Config):
        self.config = config
        self.cur = connection.cursor()

    def rows(self, sql: str, params: tuple = ()) -> list[tuple]:
        self.cur.execute(sql, params)
        return self.cur.fetchall()

    def tables(self) -> list[str]:
        found = self.rows("""
            select table_name from information_schema.tables
            where table_schema = 'public' and table_type = 'BASE TABLE'
            order by table_name
        """)
        return [t for (t,) in found if t not in self.config.ignored_tables]

    def columns(self) -> list[tuple]:
        return self.rows("""
            select table_name, column_name, data_type, character_maximum_length, is_nullable
            from information_schema.columns
            where table_schema = 'public'
            order by table_name, ordinal_position
        """)

    def foreign_keys(self) -> list[tuple]:
        return self.rows("""
            select con.conrelid::regclass::text,
                   a.attname,
                   con.confrelid::regclass::text,
                   array_length(con.conkey, 1)
            from pg_constraint con
            join pg_namespace n on n.oid = con.connamespace and n.nspname = 'public'
            join pg_attribute a on a.attrelid = con.conrelid
                and a.attnum = con.conkey[array_length(con.conkey, 1)]
            where con.contype = 'f'
            order by 1, 2
        """)

    def rls(self) -> list[tuple]:
        return self.rows("""
            select c.relname, c.relrowsecurity, c.relforcerowsecurity
            from pg_class c
            join pg_namespace n on n.oid = c.relnamespace and n.nspname = 'public'
            where c.relkind = 'r'
        """)

    def indexes(self) -> list[tuple]:
        # indisprimary matters: a primary key cannot be partial (U1) and cannot lead with the
        # tenant column (T7), so flagging one is noise that gets the whole check muted.
        return self.rows("""
            select t.relname, i.relname, ix.indisunique, ix.indpred is not null,
                   (select a.attname from pg_attribute a
                    where a.attrelid = t.oid and a.attnum = ix.indkey[0]),
                   ix.indisprimary,
                   (select array_agg(a.attname order by k.ord)
                    from unnest(ix.indkey) with ordinality as k(attnum, ord)
                    join pg_attribute a on a.attrelid = t.oid and a.attnum = k.attnum)
            from pg_index ix
            join pg_class i on i.oid = ix.indexrelid
            join pg_class t on t.oid = ix.indrelid
            join pg_namespace n on n.oid = t.relnamespace and n.nspname = 'public'
            order by t.relname, i.relname
        """)

    def triggers(self) -> set[str]:
        found = self.rows("""
            select distinct c.relname
            from pg_trigger tg
            join pg_class c on c.oid = tg.tgrelid
            join pg_namespace n on n.oid = c.relnamespace and n.nspname = 'public'
            where not tg.tgisinternal
        """)
        return {t for (t,) in found}

    def check_constraints(self) -> set[tuple[str, str]]:
        found = self.rows("""
            select con.conrelid::regclass::text, con.conname
            from pg_constraint con
            join pg_namespace n on n.oid = con.connamespace and n.nspname = 'public'
            where con.contype = 'c'
        """)
        return set(found)


# --- the rules -------------------------------------------------------------------------------

def check_keys(cat: Catalogue) -> list[Finding]:
    out: list[Finding] = []
    cfg = cat.config

    for table, column, dtype, *_ in cat.columns():
        if column == "id" and table not in cfg.ignored_tables and dtype != "uuid":
            out.append(Finding("K1", "fail", f"{table}.id", f"is {dtype}, not uuid"))

    used_roles: set[str] = set()
    for table, column, target, width in cat.foreign_keys():
        if table in cfg.ignored_tables or width != 1:
            continue
        if not column.endswith("_id"):
            out.append(Finding("K3", "fail", f"{table}.{column}", f"-> {target}, does not end _id"))
            continue
        if column == f"{singularise(target)}_id":
            continue
        if cfg.role_keys.get(column) == target:
            used_roles.add(column)
            continue
        out.append(Finding(
            "K5", "fail", f"{table}.{column}",
            f"-> {target}, neither the table's name nor an allowlisted role",
        ))

    for role in cfg.role_keys.keys() - used_roles:
        out.append(Finding("K6", "fail", role, "is on the role allowlist and nothing uses it"))

    out.append(Finding("K2", "unverifiable", "uuid generation",
                       "whether the application supplies the id is not visible in the catalogue"))
    return out


def check_tenancy(cat: Catalogue) -> list[Finding]:
    cfg = cat.config
    if not cfg.tenancy_enabled:
        return []

    out: list[Finding] = []
    tables = cat.tables()
    scoped = {t for t, c, *_ in cat.columns() if c == cfg.tenant_column and t in tables}

    if cfg.engine != "postgres":
        out.append(Finding("T3", "unverifiable", cfg.engine,
                           "no row-level security on this engine; T6 is the only structural defence"))
    else:
        for table, enabled, forced in cat.rls():
            if table not in scoped:
                continue
            if not enabled:
                out.append(Finding("T3", "fail", table, "carries the tenant column with no RLS"))
            elif not forced:
                out.append(Finding("T3", "fail", table,
                                   "RLS is enabled but not FORCED, so the table owner is exempt"))

    composite = {
        table for table, _, _, width in cat.foreign_keys() if width and width > 1
    }
    for table in sorted(scoped - composite - {cfg.tenant_table}):
        out.append(Finding("T6", "warn", table,
                           "no composite (tenant, id) foreign key; cross-tenant rows are possible if RLS is off"))

    for table, index, _unique, _partial, first, primary, _cols in cat.indexes():
        if primary:
            continue
        if table in scoped and first and first != cfg.tenant_column:
            out.append(Finding("T7", "warn", f"{table}.{index}",
                               f"leads with {first} rather than {cfg.tenant_column}"))
    return out


def check_columns(cat: Catalogue) -> list[Finding]:
    out: list[Finding] = []
    cfg = cat.config

    for table, column, dtype, width, _null in cat.columns():
        if table in cfg.ignored_tables:
            continue
        if dtype == "character varying" and width is not None and width not in POWERS_OF_TWO:
            agreed = cfg.widths.get(column)
            if not agreed or agreed.get("width") != width:
                out.append(Finding("C1", "fail", f"{table}.{column}",
                                   f"varchar({width}) is not a power of two and names no standard"))
        if dtype == "json":
            out.append(Finding("C5", "fail", f"{table}.{column}", "is json, not jsonb"))
        if dtype == "jsonb" and cfg.json_allowed and column not in cfg.json_allowed:
            out.append(Finding("C8", "warn", f"{table}.{column}",
                               "is a jsonb column outside the agreed list"))
        if dtype == "USER-DEFINED":
            out.append(Finding("C4", "warn", f"{table}.{column}",
                               "looks like an engine-native enum type"))

    out.append(Finding("C7", "unverifiable", "jsonb typing",
                       "whether a jsonb column has a typed representation lives in application code"))
    return out


def check_time(cat: Catalogue) -> list[Finding]:
    out: list[Finding] = []
    for table, column, dtype, *_ in cat.columns():
        if table in cat.config.ignored_tables:
            continue
        if column.endswith("_at") and dtype != "timestamp with time zone":
            out.append(Finding("D2", "fail", f"{table}.{column}", f"is {dtype}, not a timestamptz"))
        if column.endswith("_on") and dtype != "date":
            out.append(Finding("D2", "fail", f"{table}.{column}", f"is {dtype}, not a date"))
    return out


def check_money(cat: Catalogue) -> list[Finding]:
    out: list[Finding] = []
    by_table: dict[str, set[str]] = {}
    for table, column, dtype, *_ in cat.columns():
        by_table.setdefault(table, set()).add(column)

    checks = {name for _, name in cat.check_constraints()}

    for table, columns in by_table.items():
        if table in cat.config.ignored_tables:
            continue
        amounts = {c for c in columns if c.endswith("_minor")}
        if amounts and "currency" not in columns:
            out.append(Finding("M2", "fail", table,
                               f"holds {', '.join(sorted(amounts))} with no currency column"))
        for amount in amounts:
            if not any(amount in name for name in checks):
                out.append(Finding("M4", "warn", f"{table}.{amount}", "has no bounds check"))

        for column in columns:
            if re.search(r"_(usd|eur|gbp|kes|ngn|zar)$", column):
                out.append(Finding("M3", "fail", f"{table}.{column}",
                                   "names a currency in the column"))

    for table, column, dtype, *_ in cat.columns():
        if table in cat.config.ignored_tables:
            continue
        if dtype in {"double precision", "real"} and ("amount" in column or "price" in column):
            out.append(Finding("M1", "fail", f"{table}.{column}", f"is {dtype}, not an integer minor unit"))

    out.append(Finding("M5", "unverifiable", "money value object",
                       "whether amounts are read through a typed wrapper lives in application code"))
    return out


def check_lifecycle(cat: Catalogue) -> list[Finding]:
    cfg = cat.config
    if not cfg.lifecycle:
        return [Finding("L", "unverifiable", "lifecycle",
                        "no lifecycle assignments configured, so no table can be checked")]

    out: list[Finding] = []
    triggers = cat.triggers()
    soft_deleted = {t for t, c, *_ in cat.columns() if c == "deleted_at"}

    for table in cat.tables():
        klass = cfg.lifecycle.get(table)
        if klass is None:
            out.append(Finding("L", "fail", table, "is assigned no lifecycle class"))
            continue
        if klass == "soft_delete" and table not in soft_deleted:
            out.append(Finding("L/A", "fail", table, "is class A with no deleted_at column"))
        if klass == "append_only" and table not in triggers:
            out.append(Finding("L/B", "fail", table,
                               "is class B with no trigger; an application guard alone is bypassed"))
        if klass != "soft_delete" and table in soft_deleted:
            out.append(Finding("L", "warn", table,
                               f"is class {klass} but carries deleted_at"))
    return out


def check_uniqueness(cat: Catalogue) -> list[Finding]:
    out: list[Finding] = []
    cfg = cat.config
    soft_deleted = {t for t, c, *_ in cat.columns() if c == "deleted_at"}

    for table, index, unique, partial, _first, primary, columns in cat.indexes():
        if primary or not unique or table not in soft_deleted or partial:
            continue
        if index in cfg.unique_exceptions:
            continue
        # The T6 composite tenant key has to stay total: a foreign key can reference a unique
        # constraint but not a partial index, so making this one partial would break T6 to
        # satisfy U1. T6 is the stronger guarantee, so it wins.
        if cfg.tenant_column and list(columns or []) == [cfg.tenant_column, "id"]:
            continue
        out.append(Finding("U1", "fail", f"{table}.{index}",
                           "unique on a soft-deleted table without WHERE deleted_at IS NULL, "
                           "so a deleted row holds the key forever"))

    for rule, what in [("U2", "catching a conflict from the database rather than a pre-flight select"),
                       ("U3", "handling the violation outside the aborted transaction"),
                       ("U4", "ordering the newest row by the key as well as the timestamp")]:
        out.append(Finding(rule, "unverifiable", "query code", what + " lives in application code"))
    return out


def check_indexes(cat: Catalogue) -> list[Finding]:
    """G7. Postgres does not index a foreign key; a composite leading with it counts."""
    out: list[Finding] = []
    leading: dict[str, set[str]] = {}
    for table, _index, _unique, _partial, first, _primary, _cols in cat.indexes():
        if first:
            leading.setdefault(table, set()).add(first)

    tenant = cat.config.tenant_column
    for table, column, _target, width in cat.foreign_keys():
        if table in cat.config.ignored_tables or width != 1:
            continue
        covered = column in leading.get(table, set())
        # A (tenant, column) composite is the index the tenant read wants anyway.
        if not covered and tenant and tenant in leading.get(table, set()):
            continue
        if not covered:
            out.append(Finding("G7", "warn", f"{table}.{column}",
                               "foreign key with no index leading on it"))
    return out


CHECKS = {
    "K": ("Identifiers", check_keys),
    "T": ("Multi-tenancy", check_tenancy),
    "C": ("Column types", check_columns),
    "D": ("Dates and times", check_time),
    "M": ("Money", check_money),
    "L": ("Lifecycle", check_lifecycle),
    "U": ("Uniqueness", check_uniqueness),
    "G": ("Migration discipline", check_indexes),
}


def connect(url: str):
    try:
        import psycopg
        return psycopg.connect(url)
    except ModuleNotFoundError:
        pass
    try:
        import psycopg2
        return psycopg2.connect(url)
    except ModuleNotFoundError:
        sys.exit("Needs psycopg (v3) or psycopg2. pip install 'psycopg[binary]'")


def find_config(explicit: str | None) -> Path | None:
    if explicit:
        return Path(explicit)
    here = Path.cwd()
    for directory in [here, *here.parents]:
        candidate = directory / "schema-conventions.toml"
        if candidate.exists():
            return candidate
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--url", default=os.environ.get("DATABASE_URL"), help="connection string")
    parser.add_argument("--config", help="path to schema-conventions.toml")
    parser.add_argument("--rules", help="comma-separated rule groups, e.g. K,C,M")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--strict", action="store_true", help="treat warnings as failures")
    args = parser.parse_args()

    if not args.url:
        return parser.error("no --url and no DATABASE_URL")

    config_path = find_config(args.config)
    config = Config.load(config_path)

    wanted = [g.strip().upper() for g in args.rules.split(",")] if args.rules else list(CHECKS)
    unknown = set(wanted) - set(CHECKS)
    if unknown:
        return parser.error(f"unknown rule group(s): {', '.join(sorted(unknown))}")

    with connect(args.url) as connection:
        catalogue = Catalogue(connection, config)
        findings: list[Finding] = []
        for group in wanted:
            findings.extend(CHECKS[group][1](catalogue))

    failed = [f for f in findings if f.level == "fail"]
    warned = [f for f in findings if f.level == "warn"]
    unknown_findings = [f for f in findings if f.level == "unverifiable"]

    if args.format == "json":
        print(json.dumps({
            "config": str(config_path) if config_path else None,
            "groups": wanted,
            "failed": len(failed), "warned": len(warned), "unverifiable": len(unknown_findings),
            "findings": [f.__dict__ for f in findings],
        }, indent=2))
    else:
        for finding in failed + warned:
            mark = "FAIL" if finding.level == "fail" else "WARN"
            print(f"{finding.rule:<5} {mark}  {finding.subject}")
            print(f"            {finding.detail}")
        if unknown_findings:
            print("\nNot checkable from the catalogue, so not claimed as passing:")
            for finding in unknown_findings:
                print(f"  {finding.rule:<5} {finding.subject} - {finding.detail}")
        if config_path is None:
            print("\nNo schema-conventions.toml found. Rules needing a project's own choices "
                  "(role keys, agreed widths, lifecycles) were skipped rather than guessed at.")
        print(f"\n{len(wanted)} group(s) checked: {len(failed)} failed, {len(warned)} warnings.")

    return 1 if failed or (args.strict and warned) else 0


if __name__ == "__main__":
    sys.exit(main())
