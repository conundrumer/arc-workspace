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
- Run Analyze on it.
- Put the files you write under `.scratch/<task_id>/` and nowhere else.
- Never run a git command that changes state.
- Your reply is the report's path.

* inline: notes.md#abridgement

* inline: notes.md#citations-carried
* include: ../../docs/handbook/principles.md

## Grids
* inline: ../console.md#grids

## Keywords
* inline: ../../docs/handbook/keywords.md#keywords

## Analyze
* inline: ../../docs/handbook/procedure.md#analyze
