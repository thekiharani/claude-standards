---
description: Audit a codebase for comments that should not be there, or apply the rule to what you are writing
argument-hint: "[audit <path> | clean <path> | adopt]"
---

Load `${CLAUDE_PLUGIN_ROOT}/skills/minimal-comments/SKILL.md` and hold it while you work.

**`audit <path>`**, or no argument for the repository root:

```bash
python "${CLAUDE_PLUGIN_ROOT}/skills/minimal-comments/scripts/audit_comments.py" <path>
```

Report what it found. The categories under "to remove" are decided; the ones under "to read and
judge" are not, and the per-file density ranking is where to start reading.

**`clean <path>`**: run the audit, remove everything in a failing category, then read the densest
files and apply the delete test to what survives - delete the comment, ask whether the next person
changes the code for the worse, keep it only if they would.

**`adopt`**: set this repository up to be held to the rule. Four things, and say which you did:

1. Append `${CLAUDE_PLUGIN_ROOT}/assets/CLAUDE.md.snippet` to the repository's `CLAUDE.md`,
   creating it if absent. This is the layer that actually reaches the model while it writes,
   because it is always in context and does not depend on a skill being loaded.
2. Copy `${CLAUDE_PLUGIN_ROOT}/assets/comment-audit.yml` to `.github/workflows/`. It needs no
   services and finishes in seconds.
3. Run the audit once and report the baseline, so the first CI run is not a surprise.
4. Tell the user to make the job a required status check in branch protection, and that this is
   the only one of the four that stops a merge.

Do not touch type annotations or pragmas. They are load bearing and a linter fails without them.

Two things to get right when cleaning: an example file may explain what a setting is for, and a
commented-out setting in one is the idiom rather than dead code. And where a docblock opens with a
line restating the class before the real reason, cut the opener and keep the paragraph.
