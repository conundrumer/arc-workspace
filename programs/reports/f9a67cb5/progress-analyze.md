# f9a67cb5 Analyze progress

- `interference`: the PreToolUse Bash hook turned away the first command of the pass (`git rev-parse ...; ls ...`) because the documents had changed; the update only removed the workflow NOTE. It cost one repeated call. Nothing in the output was wrong, and nothing is wrong now.
- `interference`: the PreToolUse Bash hook turned away a `for` loop over `programs/solvers/*.dl` headers ("unsupported executable construct 'for'"). It cost one call, and a Grep over the headers replaced it. Nothing in the output was wrong, and nothing is wrong now.
