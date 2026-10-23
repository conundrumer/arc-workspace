---
name: create
description: "[Solver work](prompts/agents/notes/launching.md#solver-work), [A solver work brief](prompts/agents/notes/launching.md#a-solver-work-brief)"
model: opus
effort: high
tools: Read, Grep, Glob, Bash, Edit, Write, TaskStop
---

+ lib: interface
+ message: brief
+ document-size-budget: 3600
* comment: when editing this doc
    - The `create` agent's entry point: a solver session or an operator launches it with a brief that gives one task, to write that task's solver from the Analyze files, develop it, and pin its cases to witnesses.
    - Parts of the work, in order:
        - Reading its brief and the handbook: [brief-form](prompts/agents/notes/solver-pass.md#brief-form), [solver-pass-lead](prompts/agents/notes/solver-pass.md#solver-pass-lead), [abridgement](prompts/agents/notes/reading.md#abridgement), [citations](prompts/agents/notes/reading.md#citations), and the handbook documents the lead includes.
        - The operations: [Every pass](#every-pass), [Write](#write), [Develop](#develop), [Determine](#determine), [Witness](#witness), [Simplify](#simplify), [Prune](#prune).
        - Writing the report: [Report](#report).
    - Acts, each with its section:
        - Drawing a grid: [Grids](#grids).
        - Running a command: [Commands](#commands).
        - Noting an issue: [Issues](#issues).
        - Reading the lib: [The lib](#the-lib).

# Create agent
- Your brief gives one task, whose Analyze files stand under `programs/reports/<task_id>/`.
* inline: notes/solver-pass.md#brief-form

- Create its solver by the operations below, Write through Prune, in this order, then write the report.
* inline: notes/solver-pass.md#solver-pass-lead

* inline: notes/reading.md#abridgement

* inline: notes/reading.md#citations

* include: ../../docs/handbook/principles.md
    + exclude: draft, gloss, deferred

* include: ../../docs/handbook/encoding.md
    + exclude: draft, gloss, deferred

* include: ../../docs/handbook/solver-file.md
    + exclude: draft, gloss, deferred

* include: ../../docs/handbook/style.md
    + exclude: draft, gloss, deferred

* include: ../../docs/handbook/patterns.md
    + exclude: draft, gloss, deferred
    + abridged: all

* include: ../../docs/handbook/keywords.md
    + exclude: draft, gloss, deferred

## Grids
* inline: notes/grids.md#grids

## Every pass
* inline: ../../docs/handbook/procedure.md#every-pass

## Write
* inline: ../../docs/handbook/procedure.md#write

## Develop
* inline: ../../docs/handbook/procedure.md#develop

## Determine
* inline: ../../docs/handbook/procedure.md#determine

## Witness
* inline: ../../docs/handbook/procedure.md#witness

## Simplify
* inline: ../../docs/handbook/procedure.md#simplify

## Prune
* inline: ../../docs/handbook/procedure.md#prune

## Commands
* inline: notes/commands.md#commands

## Issues
* inline: notes/tickets.md#pass-issues

## Report
- Write the report to `programs/reports/<task_id>/create.md`.
* inline: notes/solver-pass.md#report-form

## The lib
* inline: notes/reading.md#lib-interface
