---
description: Check a schema against the relational conventions, or apply them to a change you are about to make
argument-hint: "[check <database-url> | review | rules | adopt]"
---

Load `${CLAUDE_PLUGIN_ROOT}/skills/relational-schema/references/spec.md` and hold it while you work.

Then, depending on `$ARGUMENTS`:

**`check <database-url>`**, or no argument with `DATABASE_URL` set: run the conformance checker
against the live catalogue and report what it finds, grouped by rule.

```bash
python "${CLAUDE_PLUGIN_ROOT}/skills/relational-schema/scripts/verify_schema.py" --url "<url>"
```

Rules it reports as `unverifiable` are ones no DDL can express. Do not report them as passing.

**`review`**: review the migrations and schema changes in the current diff against the spec, citing
rule IDs. Pay particular attention to G5 - if any of the changed migrations has already run
anywhere that is not disposable, say so before anything else, because that changes what is safe.

**`rules`**, or anything else: answer the question from the spec, citing the rule ID.

**`adopt`**: set this repository up to be held to the standard. Say which of these you did:

1. Append `${CLAUDE_PLUGIN_ROOT}/assets/CLAUDE.md.snippet` to the repository's `CLAUDE.md`,
   creating it if absent. This is the layer that reaches the model while it writes.
2. Copy `${CLAUDE_PLUGIN_ROOT}/assets/schema-conventions.toml.example` to
   `schema-conventions.toml` and fill it in from the schema that is actually there - the tenant
   column if there is one, the role keys in use, the widths that are not powers of two, and a
   lifecycle class for every table. The checker skips whatever this does not declare, so an empty
   file means a check that proves little.
3. Copy `${CLAUDE_PLUGIN_ROOT}/assets/schema-check.yml` to `.github/workflows/` and set its
   migrate step, which is the one line it cannot know. It is gated on migration paths because it
   needs a database and that costs minutes.
4. Run the checker against a local database and report the baseline. An existing schema will fail
   rules; decide with the user which are worth a migration and which belong in the config's
   exception list. Both are legitimate. Reporting a schema as conforming when it does not is not.

If the repository has a `schema-conventions.toml`, read it first: it holds this project's own
choices, and the rules cannot be applied without them.
