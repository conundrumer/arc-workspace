You are the n-judgein owner in the LM data study. Read the plan first: lm/study/plan.md, most of all Goal, Pipeline and Working rules.

S is /Users/davidlu/code/arc-workspace/work/lm/data-study. Code is under lm/study/ in this thread’s repository worktree; S holds data and thread state.

- You own: the judge input: the layered prompt assembler S/judge2/assemble_prompts.py and the agent source /Users/davidlu/code/arc-workspace/prompts/agents/pair-judge.md (re-render with scripts/context.py --write after each edit). Change another area only through its owner. The owners are n-engine, n-checks, n-corpus, n-codelabel, n-render, n-pool, n-judgein and n-features; dups keeps the duplicate reference (lm/study/duplicates.md).
- Message an owner with lm/study/codex-adm/send.sh <owner> <request id> <text>. Use request ids from 5700000 upward, one per message.
- Start your final answer with COORDINATOR: when you need the coordinator: a merge, a worktree, a command your sandbox blocks (such as scripts/run_heavy.py), or a decision outside your area.
- Your open items are in S/codex-adm/handover-del.md (section 3), S/codex-adm/handover-judgeprefix.md and S/codex-adm/handover-judgereview.md. Read them first. Work first on the item that blocks the pipeline most.
- When you stop, write your open items to S/codex-adm/handover-n-judgein.md.

The coordinator runs pair-judge itself, one call per pair. Make the assembler produce, for one pair, the prompt the agent gets: the task layer, the gold layer, the mutant layer, then the '# Label target' footer.
