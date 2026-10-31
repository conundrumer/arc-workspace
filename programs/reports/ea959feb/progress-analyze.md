# progress — analyze ea959feb

- `interference`: the PreToolUse Bash hook refused a `for` loop over `grep -l` output that printed solver headers (step 1, "the headers of the solvers under `programs/solvers/`"). Cost: one wasted call and a rewrite as a single `awk` over the listed paths. Output not wrong; the rewrite printed the headers.
