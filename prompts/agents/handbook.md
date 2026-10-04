---
name: handbook
description: For work that references the handbook. The handbook, with the lib as an index, one line per declaration.
model: opus
tools: Read, Grep, Glob, Bash, Edit, Write
---

+ lib: index

* inline: notes/reading.md#abridgement

* inline: notes/reading.md#citations

* inline: notes/reading.md#lib-index

* include: ../handbook.md
    + exclude: draft, gloss
    + abridged: all
