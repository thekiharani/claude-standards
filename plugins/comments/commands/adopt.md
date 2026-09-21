---
description: Set this repository up to be held to the comment standard - CLAUDE.md rule, CI workflow and a baseline
---

Three things. Do them, then say which you did and what is left for the user.

1. Append `${CLAUDE_PLUGIN_ROOT}/assets/CLAUDE.md.snippet` to this repository's `CLAUDE.md`,
   creating it if absent. This matters more than the CI job: it is in context while code is being
   written, so comments that should not exist never get written, rather than being deleted later.
2. Copy `${CLAUDE_PLUGIN_ROOT}/assets/comment-audit.yml` into `.github/workflows/`. It runs on
   every push and needs nothing but Python.
3. Run the auditor and report the baseline. An established codebase will have findings. Agree a
   threshold with the user that holds the line where it is now, so new comments are caught while
   existing ones are cleaned at whatever pace suits - a job that fails on day one gets disabled on
   day two.

Then tell the user the workflow enforces nothing until it is a required status check in branch
protection.
