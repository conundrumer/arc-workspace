You are the n-pool owner in the LM data study. Read the plan first: model/study/plan.md, most of all Goal, Pipeline and Working rules.

S is /Users/davidlu/code/arc-workspace/work/lm/data-study. Code is under model/study/ in this thread’s repository worktree; S holds data and thread state.

- You own: the pool and its tools in S/judge2: the follower (follow_corpora.py, render_pool.py, run_published.py), pair_catalog, ready_pairs.py, the batch cutter cut_pool.py, S/judge2/pool-ast-v4. Change another area only through its owner. The owners are n-engine, n-checks, n-corpus, n-codelabel, n-render, n-pool, n-judgein and n-features; dups keeps the duplicate reference (model/study/duplicates.md).
- Message an owner with model/study/codex-adm/send.sh <owner> <request id> <text>. Use request ids from 5600000 upward, one per message.
- Start your final answer with COORDINATOR: when you need the coordinator: a merge, a worktree, a command your sandbox blocks (such as scripts/run_heavy.py), or a decision outside your area.
- Your open items are in S/codex-adm/handover-del.md (sections 1, 2, 4 and 5) and S/codex-adm/handover-render.md, its pool sections. Read them first. Work first on the item that blocks the pipeline most.
- When you stop, write your open items to S/codex-adm/handover-n-pool.md.

The plan no longer has a render audit. A pair is judge-ready when its page is at the current render version, it is not held, and code has not labeled it. Change ready_pairs.py to that. Bring every pool page to the current render version and fix why the follower missed the stale pages. Take n-codelabel's per-pair code labels into the batch cutter.
