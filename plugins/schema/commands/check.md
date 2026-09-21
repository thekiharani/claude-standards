---
description: Run the schema conformance checker against a live database and report what it finds by rule
argument-hint: "[database url, or omit to use DATABASE_URL]"
---

Read `${CLAUDE_PLUGIN_ROOT}/skills/relational-schema/references/spec.md`, and this repository's
`schema-conventions.toml` if it has one. The checker skips whatever that file does not declare, so
if it is missing say so rather than reporting a clean run.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/relational-schema/scripts/verify_schema.py" --url "$ARGUMENTS"
```

Report failures grouped by rule, with what each one means rather than only its ID. Rules it returns
as `unverifiable` are ones no DDL can express: do not present them as passing.
