You are the n-mech owner in the LM data study. Read the plan first: lm/study/plan.md, most of all Goal, Pipeline and Working rules.

S is /Users/davidlu/code/arc-workspace/work/lm/data-study. P is /Users/davidlu/code/arc-workspace/work/lm/data-study/ref/progsynth-relabel, a copy of another session's work.

## Situation

The study replaces its judge labels and its code labels with mechanical labels made by another session. Their code is in P:

- `rerun_witness.py`: the one-step witness search with the grammar arclog admits, the test-input check of a witness, and a null baseline from each available table with the mutant left out.
- `labels6.py`: one label per pair, by precedence: `equivalent`, `fits`, `extension`, `overapproximation`, `lossy`, `undetermined`; attributes `selection_found`, `generalizes`, `sibling`.
- `redundant_pass.py`: the `redundant` attribute (an available table reaches the mutant's table).
- `pool_index.py`: an index of the kept pairs with their comparison relation, output fit and code search status.

These read only `recoverable.jsonl.gz`. They import the study's own modules from S/ast/run through the `STUDY_RUN` environment variable (`native_storage`, `filters`, `next_revision/family_recovery`). Their outputs on the recovered pairs are in P (`labels6.jsonl` and others). P belongs to the other session: read it, write nothing there.

The kept pairs are the pairs with `retained` true in `S/ast/run/corpus-v11/<task>/pairs.jsonl.gz`: 59,587 pairs in 607 tasks, plus four tasks whose pairs file is above 300 MB (9f669b64, 15113be4, 4e7e0eb9, 136b0064). They hold the same fields the recovered records hold (`native`, `full_replay`, `kept_comparisons`, `outputs`).

## Your work

You own S/ast/run/mech/ (new). Port the code there so that it labels the kept pairs of corpus-v11 and the recovered pairs, and give it resume:

- One record per pair, written durably as soon as that pair is done, not at the end of a task.
- Each record holds what makes it valid: a hash of the labeling code and of the source record. A start skips every pair with a valid record, so that a faster version can take over the same output and continue.
- The labels and attributes stay the same as P's code gives. Where a port changes a result, say so and why.
- Reuse P's results on the recovered pairs when their validity can be shown; otherwise label them again.
- Every run streams done/total, elapsed, rate and ETA.
- Use the study's existing modules rather than copies of them. `lm/study/duplicates.md` lists known duplicates.

Then hand the coordinator the run command (it runs through `/Users/davidlu/code/arc-workspace/scripts/run_heavy.py`, which your sandbox blocks), the output path, and a short run on a few tasks to check it before the full run. A second thread will make the code faster while the full run goes; keep the record format and the resume rule stable for it, and describe both in lm/study/ast/run/mech/README.md.

## Rules

- Message owners with lm/study/codex-adm/send.sh <owner> <request id> <text>, request ids from 9600 upward, one per message. The owners are in S/codex-adm/owners.txt. The other session is reached only through the coordinator.
- Start your final answer with COORDINATOR: when you need the coordinator: a command your sandbox blocks, or a decision outside your area.
- Run no tests.
- When you stop, write your open items to S/codex-adm/handover-n-mech.md.
