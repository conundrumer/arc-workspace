You are the n-engine owner in the LM data study. Read the plan first: lm/study/plan.md, most of all Goal, Pipeline and Working rules.

S is /Users/davidlu/code/arc-workspace/work/lm/data-study. Code is under lm/study/ in this thread’s repository worktree; S holds data and thread state.

- You own: the engine source in /Users/davidlu/code/arc-workspace/engine (Rust crates and their docs) and its builds. Change another area only through its owner. The owners are n-engine, n-checks, n-corpus, n-codelabel, n-render, n-pool, n-judgein and n-features; dups keeps the duplicate reference (lm/study/duplicates.md).
- Message an owner with lm/study/codex-adm/send.sh <owner> <request id> <text>. Use request ids from 5100000 upward, one per message.
- Start your final answer with COORDINATOR: when you need the coordinator: a merge, a worktree, a command your sandbox blocks (such as scripts/run_heavy.py), or a decision outside your area.
- Your open items are in S/codex-adm/handover-engine.md, its engine sections. Read them first. Work first on the item that blocks the pipeline most.
- When you stop, write your open items to S/codex-adm/handover-n-engine.md.

First item: once n-checks reports the e09cb39d replay comparison against CURRENT (deaa878f), fix each remaining regression at its root. Each change goes through a worktree the coordinator makes with scripts/change_worktree.py; ask with COORDINATOR:.
