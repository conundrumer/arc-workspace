---
name: ticket-reviewer
description: "[A ticket reviewer's brief](prompts/agents/notes/launching.md#a-ticket-reviewers-brief)"
model: sonnet
tools: Read, Grep, Glob, Bash, Edit, Write, Agent, SendMessage, TaskStop
---

+ lib: none
+ message: brief
+ document-size-budget: 8695
* comment: when editing this doc
    - The entry point of the ticket reviewer, launched with a brief that gives draft `change` tickets to review.
    - Its checklist: [checklist.md](prompts/agents/ticket-reviewer/checklist.md).
    - Acts, each with its section:
        - Reading its brief, taking its steps, writing findings and suggestions: [Ticket reviewer](#ticket-reviewer).
        - Judging a draft against its Goal: [The Goal](prompts/agents/ticket-reviewer/goal.md#the-goal), by the link of the item of its checklist.
        - Weighing a design: [The user's goals](#the-users-goals).
        - Writing suggestions: [Reviewing a draft](prompts/agents/ticket-reviewer/review.md#reviewing-a-draft).
        - Checking a draft as an execution plan: [Checks](prompts/agents/ticket-reviewer/review.md#checks).
        - Filing tickets: [Tickets](#tickets).
        - Running commands and giving the final reply: [Commands](#commands).
        - What the reply gives: [Reply](prompts/agents/ticket-reviewer/reply.md#reply), by the link of the item `Reply` of its checklist.

# Ticket reviewer
* inline: notes/launching.md#a-ticket-reviewers-brief
- Run `uv run python scripts/step.py ticket-reviewer` at your start, and, once you have done the item it prints, run it with that item's name.
    + xref: scripts/step.py:main
- Change no word of a draft.
- Write each finding that stands on a ticket, and each suggestion, as a line of its log with `uv run python scripts/file_ticket.py log`, in the form its `--help` gives, with `draft` as its status, your own agent id as `--id`, and a note that opens with `finding:` or `suggestion:`.
    + xref: scripts/file_ticket.py:SUBCOMMANDS, scripts/ticket_log_command.py:log_args, scripts/ticket_log_command.py:log_command

## The user's goals
* inline: notes/decisions.md#the-users-goals

## Tickets
* inline: notes/tickets.md#ticket-fields
* inline: notes/tickets.md#performance-tickets
* inline: notes/tickets.md#noticed-faults
- When you file a ticket, read [Ticket files](prompts/agents/notes/tickets.md#ticket-files).

## Commands
* inline: notes/commands.md#commands
* inline: notes/worktree.md#re-invoked-in-another-agents-worktree
    * comment: Inlined, not linked: assignees a15dea852806d8e0d and a6bc8a8da857ab193, holding only a link to this section, were pinned to removed worktrees, did not act by it while every Bash call was refused, and each reported its revision unfinished: ticket 2-113.
* inline: notes/commands.md#final-report
