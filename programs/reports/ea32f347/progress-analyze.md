# ea32f347 — Analyze progress

## Notes
- `interference`: the PreToolUse Bash hook blocked a `for` loop over `grep -l '^// @keywords:.*rank' programs/solvers/*.dl` that printed each listed solver's header ("unsupported executable construct 'for'"). Cost: one extra call; the headers were then printed one `awk` call per solver. Nothing in the output was wrong.
