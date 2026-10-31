# f9d67f8b progress (Analyze)

- `interference`: the PreToolUse Bash hook held my first Bash call (`git rev-parse ...`) back because the documents had changed: the context diff took out the workflow NOTE. Cost: one repeated call. The output was not affected.
- `interference`: the PreToolUse Bash hook blocked a `for` loop over `grep -l '^// @keywords:.*repair' programs/solvers/*.dl` that was meant to narrow the list to solvers that also have `symmetry` ("unsupported executable construct 'for'"). Cost: one repeated call, plus reading the longer unfiltered list. The output was not affected.
