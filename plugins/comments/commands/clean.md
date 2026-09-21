---
description: Remove the comments this repository does not need, and keep the ones carrying knowledge the code cannot
argument-hint: "[path, or omit for the whole repository]"
---

Read `${CLAUDE_PLUGIN_ROOT}/skills/minimal-comments/SKILL.md`, run the auditor over
`${ARGUMENTS:-.}`, then work through what it found.

The question for each comment is whether deleting it loses something. A comment that names what
the code already says loses nothing. A comment recording why a surprising choice was made - the
bug it avoids, the upstream defect it works around, the ordering that is load-bearing - loses
something no reader can recover. Delete the first kind freely. Keep the second, and improve it if
it is padded.

Before deleting anything that looks like a comment but sits at the top of a file, check whether it
is syntax: a shebang, a Dockerfile parser directive, a coding declaration, a license header a tool
requires. Those read as comments and are not.

Do not rewrite code while you are here. A diff that only removes comments can be reviewed in one
pass; one that also moves logic cannot.
