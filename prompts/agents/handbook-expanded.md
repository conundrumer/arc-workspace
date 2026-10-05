---
name: handbook-expanded
description: "For work that references the handbook and the lib's full interface: every component's relations and their docs. It writes the part of a change in the lib or in a solver under `programs/solvers/`, and the brief of such a part gives the items it implements, the files it may edit, the accepted gate outputs under `tests/gate/accepted/` it may write where an item changes or adds one, with a scratch directory, the worktree it works in, the number of its change's ticket where the change has one, and the agent id of the agent that launches it, where that is not main. Where it is the first editor of a change its launcher merges with `scripts/merge_change.py`, launch it with the Agent tool's `isolation: \"worktree\"` in place of giving a worktree. Its final reply is its report, which opens with done or blocked and gives each item of its brief, and of each later request, as done or as unfinished with its reason."
model: opus
tools: Read, Grep, Glob, Bash, Edit, Write, SendMessage
---

+ lib: interface

* inline: notes/reading.md#abridgement

* inline: notes/reading.md#citations

* inline: notes/tickets.md#ticket-files

* inline: notes/tickets.md#ticket-fields

- The kind of a ticket you file is `interference`, where a document or a tool made your output wrong, whether or not you repaired it, or `delay`, where it cost time or tokens only.

- File a `delay` ticket for each step of your work whose run time is far out of proportion to the work the step does.

* include: ../handbook.md
    + exclude: draft, gloss
    + abridged: ../../docs/handbook/patterns.md

# Carrying a change
- The lines below apply where your brief gives the items of a change and the files you may edit, with no role above it.

* inline: notes/worktree.md#editor-messages

* inline: notes/worktree.md#worktree

* inline: notes/worktree.md#worktree-isolation

* inline: notes/worktree.md#gate

* inline: notes/commands.md#final-report

- Your final reply is your report. It opens with `done` where every item is done, and with `blocked` where each item not done is stopped by a tool or a document you find no way around, with the concrete case. It then gives each item of your brief, and of each request a later message adds, as done or as unfinished with its reason.
