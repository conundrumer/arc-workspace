# f8be4b64 analyze progress

- `interference`: the PreToolUse Bash hook turned down a shell `for` loop that printed the headers of the solvers under the `cast` keyword (`unsupported executable construct 'for'`). It cost one extra call, since I printed three chosen headers with `awk`. The output was not wrong, and it is not wrong now.
- `interference`: the hook turned down the first Bash call of the pass because the documents had changed since launch (the diff only removed the workflow NOTE). It cost one repeated call. The output was not wrong, and it is not wrong now.
