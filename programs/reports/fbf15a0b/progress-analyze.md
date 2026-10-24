# fbf15a0b Analyze progress

- `interference`: PreToolUse:Bash hook, first Bash call (the worktree check). The hook held the call back because the documents might have changed since launch. The diff it gave only removed the workflow NOTE from the context. Cost: one repeated call and reading the diff. Nothing in the output was wrong.
- `interference`: PreToolUse:Bash hook, a `for` loop that printed solver headers (`awk '/^$/{exit} 1'` over the files that `grep -l '^// @keywords:.*markers'` lists). The hook blocked it as an "unsupported executable construct 'for'". Cost: one blocked call, plus a Grep fallback that listed more than 250 keyword lines and used up context. Nothing in the output was wrong.
