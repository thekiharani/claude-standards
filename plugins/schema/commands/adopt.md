---
description: Set this repository up to be held to the schema standard - conventions file, CI workflow and a baseline
---

Four things. Do them, then say which you did and what is left for the user.

1. Append `${CLAUDE_PLUGIN_ROOT}/assets/CLAUDE.md.snippet` to this repository's `CLAUDE.md`,
   creating it if absent. This is the layer that reaches the model while code is being written,
   because it is always in context.
2. Copy `${CLAUDE_PLUGIN_ROOT}/assets/schema-conventions.toml.example` to `schema-conventions.toml`
   and fill it in from the schema that is actually there: the tenant column if there is one, the
   role keys in use, the widths that are not powers of two, and the tables whose deletion shape
   is worth checking. Leave a section out rather than inventing entries for it.
3. Copy `${CLAUDE_PLUGIN_ROOT}/assets/schema-check.yml` into `.github/workflows/` and set its
   migrate step, which is the one line the template cannot know. It is gated on migration paths
   because it needs a database and that costs minutes.
4. Run the checker and report the baseline. An existing schema will fail rules: decide with the
   user which are worth a migration and which belong in the config's exception list. Both are
   legitimate. Calling a schema conformant when it is not is the only wrong answer.

Then tell the user the workflow enforces nothing until it is a required status check in branch
protection.
