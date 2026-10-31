# progress-analyze

- `interference`: the PreToolUse:Bash hook ("your documents may have changed") blocked the first Bash call of the pass, the worktree check, until the call was made again. Cost: one repeated call and reading the context diff. Output: nothing wrong.
- `interference`: the PreToolUse:Bash hook blocked a `for` loop over solver headers (`unsupported executable construct 'for'`). Cost: one repeated call, rewritten as a single `awk` over the files. Output: nothing wrong.
