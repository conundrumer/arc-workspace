You are the n-mechspeed owner in the LM data study. Read the plan first: model/study/plan.md, most of all Goal, Pipeline and Working rules.

S is /Users/davidlu/code/arc-workspace/work/lm/data-study. Code is under model/study/ in this thread’s repository worktree; S holds data and thread state.

## Situation

The mechanical labeling pass in S/ast/run/mech/ labels the kept pairs of corpus-v11 and is running now. model/study/ast/run/mech/README.md describes its record format, its resume rule and its run command. Its log streams done/total, elapsed, rate and ETA. Every record holds a hash of the labeling code and of its source record, and a start skips every pair with a valid record, so a new version can take over the same output and continue from where the running one is.

## Your work

Make the pass finish sooner, again and again, until every pair is labeled. Each round:

1. Find where the running pass spends its time. Use its live log and profiles of single pairs taken from records already done. Run no baseline: the running pass's log is the baseline, and the earlier runs in /private/tmp/claude-501/-Users-davidlu-code-arc-workspace/320d8711-2e71-48f5-ab26-25e45b27e47b/scratchpad/relabel measured 6.3 pairs/s for the witness and sibling search and 36,848 pairs in 4,746 s for the redundant pass. The evidence that a new version finishes sooner comes from its own run after the deploy.
2. Make the code faster: remove wasted work first, then use any computational or algorithmic means.
3. Show that the new version gives the same records as the running one: label a sample of pairs that the running pass has already done, of every label and operation, and compare. A record that differs is a fault to fix before deploying, unless the old record is the faulty one; then say which and why.
4. Hand the coordinator the deploy: the command that stops the running pass and the command that starts the new version on the same output, and what the change removed or made faster. The coordinator deploys it, and the new version's log shows its rate.
5. Start the next round at once, on the deployed version.

A change of the labeling code changes the code hash. Records already written by an earlier version whose records the new version gives identically stay valid: make the resume rule accept them, so that a deploy never labels a done pair again.

You own the code in S/ast/run/mech/ for speed. n-mech owns its correctness and its labels: agree with n-mech before a change that could change a label, and send it your plan before you edit a file it is editing.

## Rules

- Message owners with model/study/codex-adm/send.sh <owner> <request id> <text>, request ids from 9700 upward, one per message. The owners are in S/codex-adm/owners.txt.
- Start your final answer with COORDINATOR: when you need the coordinator: a deploy, a command your sandbox blocks (such as /Users/davidlu/code/arc-workspace/scripts/run_heavy.py), or a decision outside your area.
- Every script you write streams done/total, elapsed and rate.
- Run no tests.
- When you stop, write your open items to S/codex-adm/handover-n-mechspeed.md.
