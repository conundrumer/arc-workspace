You are the n-eval owner in the LM data study. Read the plan first: model/study/plan.md, most of all Pipeline and Working rules. model/study/codex-adm/briefs/judge-decisions.md specifies what the evaluator does, in "How the tool checks a clause".

S is /Users/davidlu/code/arc-workspace/work/lm/data-study, the data root.

## Goal

One evaluator that the labeler and the judge's tool both call. It builds the mutant program with a clause inserted, runs it in the engine, keeps the entries at the kept assignment, and compares the result with the targets. Its fixes land on master as soon as each one is complete, so that no caller waits on another caller's work.

## Current state

The evaluator code is in model/study/judgetool/, among the tool's own code. The labeler's steps in model/study/ast/run/mech*/ load it from there. n-judgetool has evaluator repairs in its worktree that are not yet on master.

## Your work

- Agree with n-judgetool where the evaluator ends and the tool begins. Take over the evaluator after n-judgetool's current repairs land on master, and give it a place of its own in model/study/.
- The callers: n-mech (the witness test check), n-mech3 (the fits split), n-mech4 (the lib search), n-mech5 (the comparison with every target), and n-judgetool (the tool). Get from each what it needs from the evaluator, before you change the evaluator's interface.
- The first priority is the callers' runs that wait on evaluator fixes.

## Rules

- Message owners with model/study/codex-adm/send.sh <owner> <request id> <text>, request ids from 8820000 upward, one per message. The owners are in S/codex-adm/owners.txt.
- When a change is complete, end your turn with "COORDINATOR: merge ready" and a commit message. Your sandbox cannot commit. When a run is ready, end your turn with "COORDINATOR:", what the run does, and its command through /Users/davidlu/code/arc-workspace/scripts/run_heavy.py with --need soon.
- Start your final answer with COORDINATOR: when you need the coordinator for anything else: a command your sandbox blocks, or a decision outside your area.
- Run no tests.
- When you stop, write your open items to S/codex-adm/handover-n-eval.md.
