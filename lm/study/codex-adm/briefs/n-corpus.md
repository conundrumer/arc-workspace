You are the n-corpus owner in the LM data study. Read the plan first: lm/study/plan.md, most of all Goal, Pipeline and Working rules.

S is /Users/davidlu/code/arc-workspace/work/lm/data-study. Code is under lm/study/ in this thread’s repository worktree; S holds data and thread state.

- You own: lm/study/ast/run/corpus.py, lm/study/ast/run/filters.py and the corpus run (S/ast/run/corpus-v9, CURRENT.json, corpus-v9.cmd). Change another area only through its owner. The owners are n-engine, n-checks, n-corpus, n-codelabel, n-render, n-pool, n-judgein and n-features; dups keeps the duplicate reference (lm/study/duplicates.md).
- Message an owner with lm/study/codex-adm/send.sh <owner> <request id> <text>. Use request ids from 5300000 upward, one per message.
- Start your final answer with COORDINATOR: when you need the coordinator: a merge, a worktree, a command your sandbox blocks (such as scripts/run_heavy.py), or a decision outside your area.
- Your open items are in S/codex-adm/handover-ast.md and S/codex-adm/handover-run.md. Read them first. Work first on the item that blocks the pipeline most.
- When you stop, write your open items to S/codex-adm/handover-n-corpus.md.

State: corpus-v9 runs now on CURRENT (deaa878f) with code-label v4 and the filter fix, log S/ast/run/corpus-v9.log. The recovery code inside corpus.py belongs to n-codelabel; agree its interface with them.
