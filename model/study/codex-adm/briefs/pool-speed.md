You are the pool-speed agent in the LM data study. Read the plan first: model/study/plan.md, most of all Pipeline and Working rules.

S is /Users/davidlu/code/arc-workspace/work/lm/data-study. Code is under model/study/ in this thread’s repository worktree; S holds data and thread state.

Goal: the pool follower renders pairs faster, so that the render backlog finishes sooner. You race a faster version against the live one.

Situation at the start (S/judge2/pool-ast-v4/FOLLOWER_PROGRESS.json, S/judge2/pool-ast-v4/follow.log):
- The follower (S/judge2/run_published.py follow_corpora, with workers=2) follows S/ast/run/corpus-v12-body-full, which is still being written at about 23 pairs per second and has 717 tasks in all.
- It has indexed about 20,000 pairs, rendered 353 and held 237. It renders at about 0.2 pairs per second. Its own estimate for the rest is about 31 hours.
- The follow log labels the pass "render audit sample only; other records stay indexed". Establish which pairs the study needs rendered, from the plan and the code, since the plan says rendering covers the pairs that judges see.
- A render of one pair takes seconds. Pages are about 100 MB for large pairs. The machine has a high load; S/ast/engine/scripts/run_heavy.py (use it for anything heavy) shares CPUs among all jobs.

Rules:
- Do not change the live follower, the live pool S/judge2/pool-ast-v4, S/judge2/render2 or any production file. Work in S/judge2/n-pool-candidates/pool-speed (your working root). Render into a separate pool directory under it, for example race-pool.
- The renderer's output must be byte-identical to the live pool's for the same pair (same render version), so a faster version can replace the live one. Show the check.
- The page content, the render version and the held rules do not change.
- Every script streams done/total, elapsed and rate. Run nothing that is not needed. Run no tests.
- Measure where the time goes for a sample of pairs before you change anything: indexing, native evaluation, page build, writes, waits for CPU. Fix the largest cost first.
- A candidate must be racable: one command that renders the same pairs as the live follower into your separate pool and prints pairs per second and the ETA for the remaining backlog, so the coordinator can run it beside the live follower.
- Heavy commands: your sandbox may block run_heavy.py. Start your final answer with COORDINATOR: and give the exact command to run.
- Message an owner (n-pool, n-render, n-corpus) with model/study/codex-adm/send.sh <owner> <request id> <text>, request ids from 5800000 upward. Changes to their files go through them.
- When you stop, write open items to S/codex-adm/handover-pool-speed.md.
