---
name: handbook
description: The handbook, with the lib as an index: one line per component.
model: opus
effort: high
tools: Read, Grep, Glob, Bash, Edit, Write
---

+ lib: index

* inline: notes.md#citations

* include: ../handbook.md
    + exclude: draft, gloss
    + abridged: all
