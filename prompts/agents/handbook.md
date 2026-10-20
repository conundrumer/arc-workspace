---
name: handbook
description: For work that references the handbook and needs the lib only as an index.
model: opus
tools: Read, Grep, Glob, Bash, Edit, Write, Artifact, TaskStop
---

+ lib: index
+ document-size-budget: 1800
* comment: when editing this doc
    - The `handbook` agent's entry point: a session launches it for work that references the handbook, with the lib as an index, and a role with no `agent` attribute runs as it.
    - Its brief gives its work. Acts, each with the section it inlines:
        - Reading the handbook and the lib: [abridgement](prompts/agents/notes/reading.md#abridgement), [citations](prompts/agents/notes/reading.md#citations), [lib-index](prompts/agents/notes/reading.md#lib-index).
        - Filing a ticket: [Ticket files](prompts/agents/notes/tickets.md#ticket-files), [Ticket fields](prompts/agents/notes/tickets.md#ticket-fields), [Noticed faults](prompts/agents/notes/tickets.md#noticed-faults), and the `delay` ticket line in the lead.
        - Running a command: [commands](prompts/agents/notes/commands.md#commands).

* inline: notes/reading.md#abridgement

* inline: notes/reading.md#citations

* inline: notes/tickets.md#ticket-files

* inline: notes/tickets.md#ticket-fields

* inline: notes/tickets.md#noticed-faults

- File a `delay` ticket for each step of your work whose run time is far out of proportion to the work the step does.
    + xref: scripts/ticket_vocabulary.py:FILER_KINDS

* inline: notes/commands.md#commands

* inline: notes/reading.md#lib-index

* include: ../handbook.md
    + exclude: draft, gloss
    + abridged: all
