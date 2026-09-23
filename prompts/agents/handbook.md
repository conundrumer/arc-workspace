---
name: handbook
description: The handbook, with the lib as an index: one line per declaration.
model: opus
tools: Read, Grep, Glob, Bash, Edit, Write
---

+ lib: index

* inline: notes.md#abridgement

* inline: notes.md#citations

* inline: notes.md#lib-index

* include: ../handbook.md
    + exclude: draft, gloss
    + abridged: all
