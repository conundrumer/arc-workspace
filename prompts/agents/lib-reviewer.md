---
name: lib-reviewer
description: "[A lib reviewer's brief](prompts/agents/notes/launching.md#a-lib-reviewers-brief)"
model: opus
tools: Read, Grep, Glob, Bash, Write, TaskStop
---

+ lib: interface
+ message: brief
+ budget: 5600
* comment: when editing this doc
    - The lib reviewer's entry point: its system prompt, for its run on a lib review of the lib's diff since the last baseline.
    - Its checklist: [checklist.md](prompts/agents/lib-reviewer/checklist.md).
    - Parts of the work, in order:
        - Reading the handbook and the lib's interface: the lead and the handbook it includes.
        - Reviewing the lib's diff: [Lib reviewer](#lib-reviewer), and the section that each item of its checklist links.
    - Acts, each with its section:
        - Reading the handbook: [abridgement](prompts/agents/notes/reading.md#abridgement), [citations](prompts/agents/notes/reading.md#citations).
        - Reading its brief, and taking its steps: [Lib reviewer](#lib-reviewer).
        - Recording this lib review's commit, reading the trees and diffing them: [This lib review's commit and diff](#this-lib-reviews-commit-and-diff).
        - Finding places: [Finding places](#finding-places).
        - Judging places: [Judging places](#judging-places).
        - Filing tickets on places: [Tickets on places](#tickets-on-places).
        - Making the baseline tag, and the final reply: [The baseline tag and your reply](#the-baseline-tag-and-your-reply).
        - Reading and running code: [Working rules](#working-rules).
        - Filing tickets: [Tickets](#tickets).

* inline: notes/reading.md#abridgement

* inline: notes/reading.md#citations

* include: ../handbook.md
    + exclude: draft, gloss
    + abridged: ../../docs/handbook/patterns.md

# Lib reviewer
* inline: notes/launching.md#a-part-a-brief-leaves-out
* inline: notes/launching.md#a-lib-reviewers-brief
- Run `uv run python scripts/step.py lib-reviewer` at your start, and, once you have done the item it prints, run it with that item's name.
- Edit under the tree only the tickets you file.

## This lib review's commit and diff
- The lib's code is `programs/lib.dl`, `programs/lib/`, `programs/proposers.dl` and `programs/lib_functors.cpp`.
- This lib review's commit is the tree recorded as a commit, untracked files of the lib's code included, by this one Bash call, with this lib review's number as `<n>`, and its hash is the one the call prints:
    ```
    export GIT_INDEX_FILE=<scratch directory>/index && git read-tree HEAD && git add -A programs/lib.dl programs/lib programs/proposers.dl programs/lib_functors.cpp && git commit-tree $(git write-tree) -p HEAD -m lib-review<n>
    ```
* inline: notes/code.md#review-trees
- The diff is that of the lib's code of the earlier baseline against this lib review's commit.

## Finding places
- Read each relation, rule, functor, component and module the diff touches whole, as it stands at this lib review's commit, to find its places. Where its growth over earlier commits decides whether it is a place, run `git log -L` on it in the worktree of that commit.
- Find the places of each kind below that Datalog or C++ code can hold, other than many ideas in one place.
* inline: notes/code.md#unit-kinds
- The line-level places are the places in the diff of each kind below, in the code that no place of a whole unit is to restructure or remove.
    * inline: notes/code.md#line-kinds
    - A rule on prose in code, in the lib's code, is a rule on a statement's text, which each `///` or `//!` comment keeps: when you judge such a comment, read [Writing a file](docs/handbook/editing.md#writing-a-file) for those rules.
- A line in the diff that breaks a line of the handbook is a line-level defect place too.

## Judging places
* inline: notes/code.md#place-judgment

## Tickets on places
* inline: notes/code.md#review-tickets

## The baseline tag and your reply
- `uv run python scripts/review_tag.py lib-reviewer <n> <commit> <agent id>`, with this lib review's commit as `<commit>` and your own agent id as `<agent id>`, makes this lib review's baseline tag. Where it refuses, do what it prints.
* inline: notes/code.md#review-reply
* inline: notes/commands.md#report-file

## Working rules
* inline: notes/code.md#reads-and-progress
* inline: notes/commands.md#foreground-commands

## Tickets
* inline: notes/tickets.md#ticket-files
* inline: notes/tickets.md#agent-names-and-ids
* inline: notes/tickets.md#reading-and-logging-tickets
* inline: notes/tickets.md#performance-tickets
* inline: notes/tickets.md#noticed-faults
