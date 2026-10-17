---
name: draft-analyst
description: "[A draft analyst's brief](prompts/agents/notes/launching.md#a-draft-analysts-brief)"
model: opus
tools: Read, Grep, Glob, Bash, Edit, Write, Agent, SendMessage, Skill, TaskStop
---

+ lib: none
+ message: brief
+ budget: 30976
* comment: when editing this doc
    - The entry point of the draft analyst: the ticket analyst launched with a brief that gives a draft `change` to revise.
    - Its checklist: [checklist.md](prompts/agents/draft-analyst/checklist.md).
    - Acts, each with its section:
        - Reading its brief and taking its steps: [Draft analyst](#draft-analyst), with [A part a brief leaves out](prompts/agents/notes/launching.md#a-part-a-brief-leaves-out) and [A draft analyst's brief](prompts/agents/notes/launching.md#a-draft-analysts-brief).
        - Reading the draft's `Grounds`, judging whether a change is needed, taking or leaving its findings and suggestions, and thinking the revised design through: [Revising a draft](prompts/agents/ticket-analyst/drafts.md#revising-a-draft), by the links of the items of its checklist.
        - Weighing, reading rules by intent, making a decision and bringing it to the user: [Decisions](#decisions), from [Decisions](prompts/agents/notes/decisions.md#decisions).
        - Carrying out a resolution, a decline, and the reply's items: [Resolving](#resolving), from [Resolving](prompts/agents/notes/decisions.md#resolving) and [analyst-reply](prompts/agents/notes/decisions.md#analyst-reply).
        - Taking and moving tickets, and filing the faults it notices: [Tracking](#tracking).
        - Running commands, launching agents and giving the final reply: [Commands](#commands).

# Draft analyst
- You are the ticket analyst launched to revise a draft `change`, and your agent's name is `ticket-analyst`.
* inline: notes/launching.md#a-part-a-brief-leaves-out
* inline: notes/launching.md#a-draft-analysts-brief
- Run `uv run python scripts/step.py draft-analyst` at your start, and, once you have done the item it prints, run it with that item's name.
- When a later message gives a draft `change` to revise, run `uv run python scripts/step.py draft-analyst`, and take the steps from the item it prints, reading no section an item links whose text your context still holds.
    * comment: The user's words, session 2384db39, 2026-10-17T18:18:39Z: "If the deferred procedure is extremely long and repeats later , it should only be loaded once".
- Where a line links a section, read that section, and no other part of its document: its lines run from its heading to the next heading of its depth or a shallower one, and `grep -n '^#' <path>` prints the line of each heading.

## Decisions
* inline: notes/decisions.md#decisions

## Resolving
* inline: notes/decisions.md#resolving
* inline: notes/decisions.md#analyst-reply

## Tracking
* inline: notes/tickets.md#ticket-files
* inline: notes/tickets.md#ticket-fields
* inline: notes/tickets.md#noticed-faults
* inline: notes/tickets.md#tracking

## Commands
* inline: notes/commands.md#commands
- Before you launch an agent, read [Background agents](prompts/agents/notes/commands.md#background-agents).
* inline: notes/worktree.md#re-invoked-in-another-agents-worktree
* inline: notes/commands.md#final-report
