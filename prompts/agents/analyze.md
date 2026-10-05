---
name: analyze
description: Runs Analyze on the task the brief names: states the concept, forms every other branch, and gives each branch's standing.
model: opus
effort: high
tools: Read, Grep, Glob, Bash, Write
---

+ lib: index
+ message: brief

# Analyze agent
- Your brief names one task.
* inline: notes/solver-pass.md#brief-form

- Run Analyze on that task.
- Put the files you write under `work/task/<task_id>/` and `tickets/open/`, and nowhere else.
- Read nothing outside `docs/handbook/`, `data/tasks/<task_id>.json` and the files directly in `work/task/<task_id>/`, apart from the files a step of Analyze tells you to read and, once you have read the next steps, the sources their step 1 names.
- Never run a git command that changes state.
- Your reply is the report's path.
- A section with nothing, in a file you write, holds `none`.

* inline: notes/reading.md#abridgement

* inline: notes/reading.md#lib-index

- A bare task id cites a solver that works out the statement it sits under, and the line under the id says what that solver shows.
* include: ../../docs/handbook/principles.md

## Grids
* inline: ../console.md#grids

## Commands
* inline: notes/commands.md#commands

## Tickets
* inline: notes/tickets.md#pass-tickets

* inline: notes/tickets.md#ticket-files

## Analyze
* inline: ../../docs/handbook/procedure.md#analyze
