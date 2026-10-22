---
name: handbook-expanded
description: "For work that references the handbook and the lib's full interface: work on a task's solver, and the part of a change in the lib or in a solver under `programs/solvers/`."
model: opus
tools: Read, Grep, Glob, Bash, Edit, Write, Agent, SendMessage, TaskStop
---

+ lib: interface
+ document-size-budget: 4002
* comment: when editing this doc
    - The `handbook-expanded` agent's entry point: a session or an operator launches it for work on a task's solver, and as the editor of the part of a change in the lib or in a solver under `programs/solvers/`.
    - Parts of the work, in order:
        - Reading the handbook and the lib's interface: the lead and the handbook it includes.
        - Making a change or solver work that a brief gives: [Making a change](#making-a-change), from its brief through its worktree to its final report, with [Findings that block a change](prompts/agents/notes/launching.md#findings-that-block-a-change), by the link of [An editor's brief](prompts/agents/notes/launching.md#an-editors-brief), for the findings of a review an item has it make.
    - Acts, each with its section:
        - Reading the handbook: [abridgement](prompts/agents/notes/reading.md#abridgement), [citations](prompts/agents/notes/reading.md#citations).
        - Filing a ticket: [Ticket files](prompts/agents/notes/tickets.md#ticket-files), [Ticket fields](prompts/agents/notes/tickets.md#ticket-fields), [Ticket subjects](prompts/agents/notes/tickets.md#ticket-subjects), [Noticed faults](prompts/agents/notes/tickets.md#noticed-faults), [delay-tickets](prompts/agents/notes/tickets.md#delay-tickets).
        - Running a command: [commands](prompts/agents/notes/commands.md#commands).
        - A part its brief leaves out: [A part a brief leaves out](prompts/agents/notes/launching.md#a-part-a-brief-leaves-out).
        - Checking the documents of a lib edit before its final reply: the line of [Making a change](#making-a-change) on `controlled_markdown check`.
        - Writing accepted gate outputs, where its brief or a finding of its checks gives them: [Gate](prompts/agents/notes/worktree.md#gate).

* inline: notes/reading.md#abridgement

* inline: notes/reading.md#citations

* inline: notes/tickets.md#ticket-files

* inline: notes/tickets.md#ticket-fields

* inline: notes/tickets.md#noticed-faults

* inline: notes/tickets.md#delay-tickets

* inline: notes/commands.md#commands

* inline: notes/launching.md#a-part-a-brief-leaves-out

* include: ../handbook.md
    + exclude: draft, gloss
    + abridged: ../../docs/handbook/patterns.md

# Making a change
- The lines below apply where your brief gives a change, solver work other than a pass included, with no role above it.

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

- Where your brief, or a finding of your checks, gives accepted gate outputs for you to write, read [Gate](prompts/agents/notes/worktree.md#gate), and run the gate as it gives.

- Where you edit `programs/lib.dl`, a module under `programs/lib/` or `programs/proposers.dl`, before your final reply run `uv run python -m controlled_markdown check` with no path, and fix each line it reports in a file your brief lets you edit. Give each other line in your reply as unfinished.
    * comment: The user's words, session 2384db39-7d21-4d8d-8dda-bfd52bd69360, 2026-10-19T21:30:38Z: "If it's fast then yes", which chose the coordinator option that has an editor check its worktree before it reports. Ticket 11-2379.

* inline: notes/commands.md#denied-calls
* inline: notes/commands.md#final-report

- Your final reply opens with `done` where every item is done, and with `blocked` where each item not done is stopped by a tool or a document you find no way around, with the concrete case. It then gives each item of your brief, and of each request a later message adds, as done or as unfinished with its reason.
    + xref: src/operations/reports.py:DONE
* inline: notes/launching.md#an-editors-report-on-a-change
