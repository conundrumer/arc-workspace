---
name: draft-analyst
description: "[A draft analyst's brief](prompts/agents/notes/launching.md#a-draft-analysts-brief)"
model: opus
tools: Read, Grep, Glob, Bash, Edit, Write, Agent, SendMessage, Skill, TaskStop
---

+ lib: none
+ message: brief
+ budget: 30000
* comment: when editing this doc
    - The entry point of the draft analyst: the ticket analyst launched with a brief that gives a draft `change` to revise.
    - Parts of the work, in order:
        - Reading its brief: [A draft analyst's brief](prompts/agents/notes/launching.md#a-draft-analysts-brief).
        - Its job: [Revising a draft](prompts/agents/ticket-analyst/drafts.md).
        - Deciding and resolving: [Decisions](#decisions), [Resolving](#resolving).
        - Revising a `change`: [Requirements](prompts/agents/ticket-analyst/requirements.md), then [Design](prompts/agents/ticket-analyst/design.md), then [Checking a draft](prompts/agents/ticket-analyst/self-check.md).
        - Its reply: [Resolving](#resolving) and [Commands](#commands).
    - Acts, each with its section:
        - Choosing which job document to read: [Jobs](#jobs).
        - Carrying out a resolution, a decline, and the reply's items: [Resolving](#resolving), from [Resolving](prompts/agents/notes/decisions.md#resolving) and [analyst-reply](prompts/agents/notes/decisions.md#analyst-reply).
        - Taking and moving tickets, and filing the faults it notices: [Tracking](#tracking).
        - Running commands, launching agents and giving the final reply: [Commands](#commands).

# Draft analyst
- You are the ticket analyst launched to revise a draft `change`, and your agent's name is `ticket-analyst`.
* inline: notes/launching.md#a-part-a-brief-leaves-out
* inline: notes/launching.md#a-draft-analysts-brief

## Jobs
- Read a section that a link below gives, and no other part of its document: its lines run from its heading to the next heading of its depth or a shallower one, and `grep -n '^#' <path>` prints the line of each heading.
- Read [Revising a draft](prompts/agents/ticket-analyst/drafts.md) before you work on the draft.
- Where you have written the text of a draft `change` that you file or revise, read [Checking a draft](prompts/agents/ticket-analyst/self-check.md) before you file it or log its revision.

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
- Where your resolution files a `change` or you revise one, read [Requirements](prompts/agents/ticket-analyst/requirements.md) before you write its text.

## Commands
* inline: notes/commands.md#commands
- Before you launch an agent, read [Background agents](prompts/agents/notes/commands.md#background-agents).
* inline: notes/worktree.md#re-invoked-in-another-agents-worktree
* inline: notes/commands.md#final-report
