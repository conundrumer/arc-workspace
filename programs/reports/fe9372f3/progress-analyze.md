# progress-analyze fe9372f3

- `interference`: the PreToolUse document-update hook on the first Bash call (`git rev-parse ... && ls ...`) blocked the call to give a context diff, which only removed the workflow NOTE. Cost: one repeated call. Output not wrong.
- `interference`: the PreToolUse Bash hook blocked a `for` loop that printed solver headers ("unsupported executable construct 'for'"). Cost: one call, rewritten as one `awk` over the files. Output not wrong.
