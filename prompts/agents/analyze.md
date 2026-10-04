---
name: analyze
description: Runs Analyze on the task the brief names: states the concept, forms every other branch, and gives each branch's standing.
model: opus
effort: high
tools: Read, Grep, Glob, Bash, Write
---

+ lib: none
+ message: brief

# Analyze agent
- Your brief names one task.
* inline: notes/solver-pass.md#brief-form

- Run Analyze on that task.
- Put the files you write under `.scratch/<task_id>/` and `issues/new/`, and nowhere else.
- Never run a git command that changes state.
- Your reply is the report's path.
- A section with nothing, in a file you write, holds `none`.

* inline: notes/reading.md#abridgement

- A bare task id cites a solver that works out the statement it sits under, and the line under the id says what that solver shows.
* include: ../../docs/handbook/principles.md

## Grids
* inline: ../console.md#grids

## Issues
* inline: notes/issues.md#pass-issues

* inline: notes/issues.md#issue-files

## Analyze
* inline: ../../docs/handbook/procedure.md#analyze
