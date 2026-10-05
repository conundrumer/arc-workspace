---
name: create
description: Runs Create on the task the brief names: writes the solver from the Analyze files, develops it, and pins its cases to witnesses.
model: opus
effort: high
tools: Read, Grep, Glob, Bash, Edit, Write
---

+ lib: interface
+ message: brief

# Create agent
- Your brief names one task, whose Analyze files stand under `work/task/<task_id>/`.
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

* include: ../../docs/handbook/lib-protocol.md
    + exclude: draft, gloss, deferred

## Grids
* inline: ../console.md#grids

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

## Issues
* inline: notes/issues.md#pass-issues

* inline: notes/issues.md#issue-files

## Report
- Write the report to `work/task/<task_id>/create.md`.
* inline: notes/solver-pass.md#report-form

## The lib
* inline: notes/reading.md#lib-interface
