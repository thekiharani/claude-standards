---
description: Review the migrations and schema changes in the current diff against the standard
---

Read `${CLAUDE_PLUGIN_ROOT}/skills/relational-schema/references/spec.md` and this repository's
`schema-conventions.toml`, then review the schema changes in the working tree or the named diff,
citing rule IDs.

Check G5 before anything else: if a changed migration has already run anywhere that is not
disposable, that changes what is safe, and it is worth saying before any other finding. A
migration that has run is finished - later work is its own additive file, and consolidating into
it leaves production on one schema and a fresh database on another.
