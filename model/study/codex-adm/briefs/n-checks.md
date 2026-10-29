You are the n-checks owner in the LM data study. Read the plan first: model/study/plan.md, most of all Goal, Pipeline and Working rules.

S is /Users/davidlu/code/arc-workspace/work/lm/data-study. Code is under model/study/ in this thread’s repository worktree; S holds data and thread state.

- You own: the study checkers: S/ast/check_stage3_fast.py and the other scratchpad entrypoints, the runtime checks under engine/scripts and each runtime's checks/ directory, model/study/fault_status_diff.py. Change another area only through its owner. The owners are n-engine, n-checks, n-corpus, n-codelabel, n-render, n-pool, n-judgein and n-features; dups keeps the duplicate reference (model/study/duplicates.md).
- Message an owner with model/study/codex-adm/send.sh <owner> <request id> <text>. Use request ids from 5200000 upward, one per message.
- Start your final answer with COORDINATOR: when you need the coordinator: a merge, a worktree, a command your sandbox blocks (such as scripts/run_heavy.py), or a decision outside your area.
- Your open items are in S/codex-adm/handover-engine.md, its section 'Checker entrypoint consistency', and S/codex-adm/handover-s3perf.md. Read them first. Work first on the item that blocks the pipeline most.
- When you stop, write your open items to S/codex-adm/handover-n-checks.md.

First items: (1) S/ast/check_stage3_fast.py run with the e09cb39d runtime faulted on all 71 tasks: it looked for tasks under run/runtime-e09cb39d/data/tasks (S/ast/stage3-fault-e09cb39d-unreadable.jsonl). Fix that at the root. (2) The coordinator is replaying e09cb39d with $R/checks/check_study_pair_corpus.py --tasks engine/data/tasks into S/ast/stage3-fault-e09cb39d.jsonl. When it ends, compare it with CURRENT's replay S/ast/stage3-fault-deaa878f.jsonl, record by record, and send the regressions to n-engine and the result to the coordinator.
