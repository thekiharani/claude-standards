---
description: Check a schema against the relational conventions, or apply them to a change you are about to make
argument-hint: "[check <database-url> | review | rules]"
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

If the repository has a `schema-conventions.toml`, read it first: it holds this project's own
choices, and the rules cannot be applied without them.
