You are the n-codelabel owner in the LM data study. Read the plan first: model/study/plan.md, most of all Goal, Pipeline and Working rules.

S is /Users/davidlu/code/arc-workspace/work/lm/data-study. Code is under model/study/ in this thread’s repository worktree; S holds data and thread state.

- You own: the code label: the family recovery helper and its checks (S/ast/run/codelabel, S/ast/run/check_recovery_adapter.py, the recovery calls inside model/study/ast/run/corpus.py, whose interface you agree with n-corpus). Change another area only through its owner. The owners are n-engine, n-checks, n-corpus, n-codelabel, n-render, n-pool, n-judgein and n-features; dups keeps the duplicate reference (model/study/duplicates.md).
- Message an owner with model/study/codex-adm/send.sh <owner> <request id> <text>. Use request ids from 5400000 upward, one per message.
- Start your final answer with COORDINATOR: when you need the coordinator: a merge, a worktree, a command your sandbox blocks (such as scripts/run_heavy.py), or a decision outside your area.
- Your open items are in S/codex-adm/handover-codelabel.md. Read them first. Work first on the item that blocks the pipeline most.
- When you stop, write your open items to S/codex-adm/handover-n-codelabel.md.

Most urgent: the pool S/judge2/pool-ast-v4 holds corpus-v8 pairs that predate code-label v4. Run the v4 code label over every pool pair (streamed), and write one record per pair with its code label (DETOUR, not_recoverable, search_bound) where n-pool's batch cutter can read it, so batches hold only pairs code can't decide. Agree the file with n-pool. Hand the coordinator any run_heavy command with COORDINATOR:.
