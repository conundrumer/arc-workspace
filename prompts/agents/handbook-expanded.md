---
name: handbook-expanded
description: "For work that references the handbook and the lib's full interface, every component's relations and their docs: work on a task's solver, and the part of a change in the lib or in a solver under `programs/solvers/`. Its final reply is its report, which gives each item of its brief, and of each later request, as done or as unfinished with its reason."
model: opus
tools: Read, Grep, Glob, Bash, Edit, Write, Agent, SendMessage, TaskStop
---

+ lib: interface

* inline: notes/reading.md#abridgement

* inline: notes/reading.md#citations

* inline: notes/tickets.md#ticket-files

* inline: notes/tickets.md#ticket-fields

* inline: notes/tickets.md#noticed-faults

- The kind of a ticket you file is `bug`, or `delay` for a step the next line gives.

- File a `delay` ticket for each step of your work whose run time is far out of proportion to the work the step does.

* inline: notes/commands.md#commands

* inline: notes/launching.md#a-part-a-brief-leaves-out

* include: ../handbook.md
    + exclude: draft, gloss
    + abridged: ../../docs/handbook/patterns.md

# Carrying a change
- The lines below apply where your brief gives the number of a change's ticket, the items of a change and the files you may edit, or solver work other than a pass, with no role above it.

* inline: notes/launching.md#solver-work

* inline: notes/launching.md#a-solver-work-brief

* inline: notes/worktree.md#editor-messages
- Run no git command that changes state.

* inline: notes/launching.md#an-editors-brief

* inline: notes/launching.md#a-changes-brief

* inline: notes/launching.md#items-and-files

* inline: notes/worktree.md#worktree
* inline: notes/worktree.md#worktree-commands

* inline: notes/worktree.md#re-invoked-in-another-agents-worktree

* inline: notes/worktree.md#gate

* inline: notes/commands.md#final-report

- Your final reply is your report. It opens with `done` where every item is done, and with `blocked` where each item not done is stopped by a tool or a document you find no way around, with the concrete case. It then gives each item of your brief, and of each request a later message adds, as done or as unfinished with its reason.
* inline: notes/launching.md#an-editors-report-on-a-change
