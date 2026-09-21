# Engineering standards

Standards for Claude Code, as plugins. One copy, versioned here, used by every repository rather
than copied into each and left to drift.

## Using it

```
/plugin marketplace add thekiharani/claude-standards
/plugin install schema@claude-standards
/plugin install comments@claude-standards
```

## Plugins

| Plugin | What it is |
|---|---|
| `schema` | Framework-agnostic relational schema conventions, with a checker that reads the live catalogue |
| `comments` | Near-zero comments in every file, with an auditor that finds the ones to remove |

## Working on it

Each skill's rules live in `references/`, and anything that can be checked has a check. Changing a
rule means changing three things together, which is what keeps the standard from becoming prose:

1. the normative text in `references/spec.md`
2. the check in `scripts/`
3. a case in `tests/fixtures/` and its ID in the `EXPECTED` list

```bash
cd plugins/schema/skills/relational-schema/tests && ./run_tests.sh
cd plugins/comments/skills/minimal-comments/tests && ./run_tests.sh
```

It spins up a throwaway PostgreSQL, loads a fixture that breaks every checkable rule once and a
second that breaks none, and asserts both. A rule with no failing fixture is a rule nobody can tell
has stopped working; a false positive on the conforming fixture is how a checker gets muted.
