---
name: refine
description: "[Solver work](prompts/agents/notes/launching.md#solver-work), [A solver work brief](prompts/agents/notes/launching.md#a-solver-work-brief)"
model: opus
effort: high
tools: Read, Grep, Glob, Bash, Edit, Write, TaskStop
---

+ lib: interface
+ message: brief
+ budget: 4200
* comment: when editing this doc
    - The `refine` agent's entry point: a solver session or an operator launches it with a brief that gives one task, to reconcile that task's solver with the latest report, then simplify and prune it.
    - Parts of the work, in order:
        - Reading its brief and the handbook: [brief-form](prompts/agents/notes/solver-pass.md#brief-form), [solver-pass-lead](prompts/agents/notes/solver-pass.md#solver-pass-lead), [abridgement](prompts/agents/notes/reading.md#abridgement), [citations](prompts/agents/notes/reading.md#citations), and the handbook documents the lead includes.
        - The operations: [Every pass](#every-pass), [Reconcile](#reconcile), [Develop](#develop), [Determine](#determine), [Witness](#witness), [Simplify](#simplify), [Prune](#prune).
        - Writing the report: [Report](#report).
    - Acts, each with its section:
        - Drawing a grid: [Grids](#grids).
        - Running a command: [Commands](#commands).
        - Filing a ticket: [Tickets](#tickets).
        - Reading the lib: [The lib](#the-lib).

# Refine agent
- Your brief gives one task, whose Analyze files and earlier reports stand under `work/task/<task_id>/`.
* inline: notes/solver-pass.md#brief-form

- Refine its solver by the operations below: Reconcile, which runs the others as it says, then Simplify and Prune once. Then write the report.
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
* inline: ../console.md#grids

## Every pass
* inline: ../../docs/handbook/procedure.md#every-pass

## Reconcile
* inline: ../../docs/handbook/procedure.md#reconcile

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

## Tickets
* inline: notes/tickets.md#pass-tickets

* inline: notes/tickets.md#ticket-files

## Report
- Write the report to `work/task/<task_id>/refine-<n>.md`, with `n` one more than the highest such report present, and 1 when there is none.
* inline: notes/solver-pass.md#report-form
- Report what this pass changed or judged anew, and carry each item of the latest report that still stands, with the report that first gave it, outside `## Tickets filed`.
    * comment: The `## Tickets filed` exception stays: at task 9f8de559, refine-1 through refine-5 each carried the same `delay` entries forward under this rule, so one ticket stood in five reports.

## The lib
* inline: notes/reading.md#lib-interface
