---
description: Audit this repository for comments the code does not need and report what should go
argument-hint: "[path, or omit for the whole repository]"
---

Read `${CLAUDE_PLUGIN_ROOT}/skills/minimal-comments/SKILL.md`, then:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/minimal-comments/scripts/audit_comments.py" ${ARGUMENTS:-.}
```

Report by category, worst first, and say which findings are genuinely wrong rather than only what
the count is. The auditor is deliberately literal: it cannot tell a comment that explains a
non-obvious why from one that restates the line below it, so read what it flags before agreeing
with it. Commented-out code and stale references are almost always real. Redundant and too-long
need judgement.
