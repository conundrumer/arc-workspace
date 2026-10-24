# ff805c23 Analyze progress

- `interference`: the PreToolUse Bash hook blocked the pass's first command (`git rev-parse ...; ls ...`) to show a context diff. The diff only dropped the workflow note, so I ran the same call again. Cost: one repeated call. Nothing in the output was wrong.
- `interference`: the PreToolUse Bash hook blocked a `for` loop over `awk '/^$/{exit} 1' programs/solvers/<id>.dl` with "unsupported executable construct 'for'". I printed the headers with one `awk` over all the files instead. Cost: one repeated call. Nothing in the output was wrong.
