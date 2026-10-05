---
name: refine
description: Runs Refine on the task the brief names: reconciles the solver with the latest report, then simplifies and prunes.
model: opus
effort: high
tools: Read, Grep, Glob, Bash, Edit, Write
---

+ lib: interface
+ message: brief

# Refine agent
- Your brief names one task, whose Analyze files and earlier reports stand under `.scratch/<task_id>/`.
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

* include: ../../docs/handbook/lib-protocol.md
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

## Issues
* inline: notes/issues.md#pass-issues

* inline: notes/issues.md#issue-files

## Report
- Write the report to `.scratch/<task_id>/refine-<n>.md`, with `n` one more than the highest such report present, and 1 when there is none.
* inline: notes/solver-pass.md#report-form
- Report what this pass changed or judged anew, and carry each item of the latest report that still stands, with the report that first gave it, outside `## Issues filed`.
    * comment: The `## Issues filed` exception stays: at task 9f8de559, refine-1 through refine-5 each carried the same `delay` entries forward under this rule, so one issue stood in five reports.

## The lib
* inline: notes/reading.md#lib-interface
