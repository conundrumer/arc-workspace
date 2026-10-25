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
        - The operations: [Every pass](#every-pass), [Pace](#pace), [Write](#write), [Develop](#develop), [Determine](#determine), [Witness](#witness), [Simplify](#simplify), [Prune](#prune).
        - Writing the report: [Report](#report).
    - Acts, each with its section:
        - Drawing a grid: [Grids](#grids).
        - Running a command: [Commands](#commands), and [Rules for one long command](#rules-for-one-long-command) for a `run_dl.py` command.
        - Keeping to the run's time: [Pace](#pace), which `scripts/create_pace.py` serves; the budgets and the at-budget actions are that script's, and each rule that holds at any time in a step stands under that step's section.
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

## Pace
- At the start of each of these steps, run `uv run python scripts/create_pace.py <task_id> <step>`, and do what it prints:
    - `read`: before you read the Analyze files.
    - `precedent-and-design`: once you have read the Analyze files, before you read another solver.
        - Read at most 3 other solvers, and build no scratch model.
            * comment: In the 27 usable V5 to V7 create transcripts this step is the largest, a median of 2.9 minutes and 35% of the new tokens, and its long turns cost 2 to 5 minutes and 10 to 27 thousand output tokens each (request 23-1, step-budget analysis). The user's approval, session 9f8cdc6e-5ae4-4a4e-bf60-4a372229a6e6, 2026-10-25T16:48:38Z.
    - `write`: before you write the solver file.
    - `develop`: before the first run of the solver.
    - `determine`: at the start of [Determine](#determine).
    - `witness`: at the start of [Witness](#witness).
    - `simplify-and-prune`: at the start of [Simplify](#simplify).
    - `report`: at the start of [Report](#report).
    * comment: Create passes have no clock. On branch `origin/claude/practical-gauss-b8f57v`, task d8e07eb2's solver passed all 7 pairs early and the pass went on to about 110 minutes, and task da515329's went on to about 60 minutes. The user's words, session 9f8cdc6e-5ae4-4a4e-bf60-4a372229a6e6, 2026-10-25T16:48:38Z: "approve", of a script that "a create agent runs at the start of each step".
- In the same Bash command as each `run_dl.py` command, right after it, run `uv run python scripts/create_pace.py <task_id> <step> --status $?` with the step in progress, and do what it prints: `timeout 120 uv run python scripts/run_dl.py ...; uv run python scripts/create_pace.py <task_id> <step> --status $?`.
    * comment: Design review decision 23-4 of request 23-1: a command that outlasts its `timeout` or is killed ends the step's work before the next step's start call, so the script is called after the command.
- In the Bash command of each pairs run, `run_dl.py <task_id>`, join to it by `&&` a copy of the solver and the witness file, before the `create_pace.py` call, so that the copy runs only where the run exits 0: `timeout 120 uv run python scripts/run_dl.py <task_id> && cp programs/solvers/<task_id>.dl work/task/<task_id>/last-pass.dl && cp programs/witnesses/<task_id>.wit.json work/task/<task_id>/last-pass.wit.json; uv run python scripts/create_pace.py <task_id> <step> --status $?`.
    * comment: Task da515329's pass had a variant that passed all four pairs in 16 s, kept it in a scratch file, and ended with no passing solver. The user's approval, session 9f8cdc6e-5ae4-4a4e-bf60-4a372229a6e6, 2026-10-25T16:48:38Z, of "saving the last passing solver". The Create pass on d8e07eb2 (transcript agent-a0a2ca391eddabb1f, session 9f8cdc6e-5ae4-4a4e-bf60-4a372229a6e6, 2026-10-25) copied the solver at 17:52:28Z before any pairs run checked it, which overwrote the last checked copy, and left a passing run at 17:43:14Z unsaved. `run_dl.py <task_id>` exits 1 where a pair or the determination fails, and otherwise with the lint's code (`src/cli/check.py:89`). The user's approval, same session, 2026-10-25T18:04:12Z.

## Write
* inline: ../../docs/handbook/procedure.md#write

## Develop
* inline: ../../docs/handbook/procedure.md#develop

- Add only the branches that [Develop](#develop) steps 3 and 4 name, and add none for any other reason.
    * comment: 7 of the 28 V5 to V7 runs used 49% of all their wall time, with longer solvers, and the extra time gave no better result (request 23-1, step-budget analysis). The user's approval, session 9f8cdc6e-5ae4-4a4e-bf60-4a372229a6e6, 2026-10-25T16:48:38Z.
- Where `store` prints no line to add for a value, mark that value with a `@workaround` directive, and go on without a redesign of it.
    * comment: Task d8e07eb2's pass spent about 20 minutes on a `store` redesign of such a value, and six tasks on the branch `origin/claude/practical-gauss-b8f57v` met this case. The user's approval, session 9f8cdc6e-5ae4-4a4e-bf60-4a372229a6e6, 2026-10-25T16:48:38Z, of the rule that "if store prints no line to add, the agent marks the value as @workaround and moves on".

## Determine
* inline: ../../docs/handbook/procedure.md#determine

- Run `determination-plan` at most 3 times for one entry, and apply the same cap where the plan prints `over the enumeration limit`; after that, the entry stands, and you write it under Unsettled.
    * comment: Task c803e39c's pass spent 17 minutes in Determine over 7 plan runs, and task d304284e's lost about 25 minutes to a determination that could not hold. The user's approval, session 9f8cdc6e-5ae4-4a4e-bf60-4a372229a6e6, 2026-10-25T16:48:38Z: "a cap of 3 plan runs. After that, the entry stands as Unsettled."

## Witness
* inline: ../../docs/handbook/procedure.md#witness

- Build each witness in one `record` call, and write no grid by hand over 5 thousand output tokens.
    * comment: The pass on cbebaa4b wrote a grid by hand of 16 thousand output tokens and failed both tests (request 23-1, step-budget analysis). The user's approval, session 9f8cdc6e-5ae4-4a4e-bf60-4a372229a6e6, 2026-10-25T16:48:38Z.

## Simplify
* inline: ../../docs/handbook/procedure.md#simplify

- Run `deletions` once, after the last solver edit before the report.
    * comment: The pass on c663677b waited 289 s for one `deletions` run (request 23-1, step-budget analysis). The user's approval, session 9f8cdc6e-5ae4-4a4e-bf60-4a372229a6e6, 2026-10-25T16:48:38Z.

## Prune
* inline: ../../docs/handbook/procedure.md#prune

- The last pairs run of the pass comes after the last solver edit, before the report.
    * comment: The Create pass on d8e07eb2 (transcript agent-a0a2ca391eddabb1f, session 9f8cdc6e-5ae4-4a4e-bf60-4a372229a6e6) edited the solver at 17:52:28Z and ran no pairs run after it, and its report says every pair passes. The user's approval, same session, 2026-10-25T18:04:12Z.

## Commands
* inline: notes/commands.md#commands

## Rules for one long command
- Run each `uv run python scripts/run_dl.py` command under `timeout 120`.
    * comment: One audit in the pass on d8e07eb2 took 2000 s, and the pass on da515329 spent about 30 minutes profiling a `-9` kill. The user's approval, session 9f8cdc6e-5ae4-4a4e-bf60-4a372229a6e6, 2026-10-25T16:48:38Z, of "a timeout on long commands".
- Where a pairs run is stopped by that timeout (exit 124) or is killed with `-9` (exit 137), copy `work/task/<task_id>/last-pass.dl` and `work/task/<task_id>/last-pass.wit.json` back to the solver and the witness file; where `last-pass.dl` does not exist, keep the current solver. Do not profile the command. Add no `@store` line, `@derive` line or choice point afterwards, and write each branch you leave out under Unsettled.
- Where an `audit` or a `deletions` run is stopped by that timeout or is killed, keep the solver and the witness file, write that check under Unsettled, and go on.
    * comment: The `audit` in the Create pass on d8e07eb2 (transcript agent-a0a2ca391eddabb1f, session 9f8cdc6e-5ae4-4a4e-bf60-4a372229a6e6) timed out at 17:55:10Z while its solver passed every pair; a restore would have put back an older or unchecked solver. The user's approval, same session, 2026-10-25T18:04:12Z.
- Where the pairs run takes 60 s or more, this rule takes precedence over [Develop](#develop) steps 3 and 4: add no `@derive` line or choice point, hold at most 2 `@store` lines, for the stored interpretations the concept needs, mark each other store point `@workaround`, and write each under Unsettled.
    * comment: Request 23-1, step-budget analysis: the usable V5 to V7 solvers hold 0 or 1 `@store` lines, and d8e07eb2 reached 13 and then fell back to 3.
- Where the pairs run takes 30 s or more, or another `run_dl.py` command takes 60 s or more, run that command at most once more in the run, after the last edit that concerns it. Redirect the output of an `audit` or `deletions` of that length to a file, and read the file whole.
    * comment: Audit, `store` and sweep time grow with each case that a stored value, a derived value or a choice point adds. In the pass on d8e07eb2 (branch `origin/claude/practical-gauss-b8f57v`), the first `store` run took 136 s and printed 13 lines, `store` took 126 s with 3 of them held, and past 900 s with all 13. The create transcript of agent c663677b (request 23-1, step-budget analysis) ran `audit` 4 times (167 s, a timeout at 235 s, 20 s, 206 s) and waited 289 s for one `deletions` run.

## Issues
* inline: notes/tickets.md#pass-issues

## Report
- Write the report to `programs/reports/<task_id>/create.md`.
* inline: notes/solver-pass.md#report-form

## The lib
* inline: notes/reading.md#lib-interface
