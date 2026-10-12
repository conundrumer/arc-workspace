---
name: handbook
description: For work that references the handbook. The handbook, with the lib as an index, one line per declaration.
model: opus
tools: Read, Grep, Glob, Bash, Edit, Write, Artifact, TaskStop
---

+ lib: index
+ budget: 800

* inline: notes/reading.md#abridgement

* inline: notes/reading.md#citations

* inline: notes/tickets.md#ticket-files

* inline: notes/tickets.md#ticket-fields

* inline: notes/tickets.md#noticed-faults

- File a `delay` ticket for each step of your work whose run time is far out of proportion to the work the step does.

* inline: notes/commands.md#commands

* inline: notes/reading.md#lib-index

* include: ../handbook.md
    + exclude: draft, gloss
    + abridged: all
