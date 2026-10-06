---
name: handbook
description: For work that references the handbook. The handbook, with the lib as an index, one line per declaration.
model: opus
tools: Read, Grep, Glob, Bash, Edit, Write, Artifact
---

+ lib: index

* inline: notes/reading.md#abridgement

* inline: notes/reading.md#citations

* inline: notes/tickets.md#ticket-files

* inline: notes/tickets.md#ticket-fields

- The kind of a ticket you file is `interference`, where a document or a tool made your output wrong, whether or not you repaired it, or `delay`, where it cost time or tokens only.

- File a `delay` ticket for each step of your work whose run time is far out of proportion to the work the step does.

* inline: notes/commands.md#commands

* inline: notes/reading.md#lib-index

* include: ../handbook.md
    + exclude: draft, gloss
    + abridged: all
