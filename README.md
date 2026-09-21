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

| Plugin | Command | What it is |
|---|---|---|
| `schema` | `/schema` | Framework-agnostic relational schema conventions, with a checker that reads the live catalogue |
| `comments` | `/comments` | Near-zero comments in every file, with an auditor that finds the ones to remove |

## Invoke these rather than waiting for them

Both ship as skills, and a skill loads when Claude decides it needs one. Measured on 20 realistic
prompts per skill, three runs each, that decision goes the wrong way almost every time: the schema
skill loaded on 2 invocations in 20 that squarely called for it, and the comments skill on 0.

Rewriting the descriptions does not fix it. Four rounds of automatic optimisation produced
identical scores, and a hand-written imperative version - "MUST be read before writing or editing
any file" - moved nothing. The cause is not the wording. A conventions skill describes how to do
work Claude already knows how to do, so it is never reached for.

## Adopting these in a repository

`/schema adopt` and `/comments adopt` do the setup. What they put in place, weakest to strongest:

| Layer | Reaches | Stops a merge |
|---|---|---|
| `CLAUDE.md` pointing at the spec | the model, on every turn, always in context | no |
| `/schema`, `/comments` | when somebody asks | no |
| The checkers in CI | every pull request | **yes, once the job is a required status check** |

Only the last one enforces. The first is what changes the code as it is written, and the two are
worth having together: CI tells you after the fact, `CLAUDE.md` is what stops it being written
that way.

Adding the workflow is not enough on its own. The job has to be a **required status check** in
branch protection, or a red run is a red run somebody can merge past.

The comments audit needs no services and takes seconds. The schema check needs a live database, so
its workflow is gated on migration paths and has one line the template cannot know - how this
project builds its schema.

The eval sets and results are in `evals/`, so the measurement can be repeated when the model or
the harness changes.

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
