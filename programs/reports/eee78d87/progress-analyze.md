# eee78d87 — Analyze progress

- `interference`: the PreToolUse Bash hook held back the first two calls (`cat data/tasks/eee78d87.json` and a listing of the report dirs) to deliver a context diff, which removed only the workflow NOTE paragraph. Cost: both calls had to be issued again. Output was not wrong; nothing remains affected.
- `interference`: the PreToolUse Bash hook refused a `for` loop that would print the headers of several `wallpaper` solvers ("unsupported executable construct 'for'"). Cost: one wasted call. The solver headers were not surveyed further, because the branches came from the pairs and the proposers. Output was not wrong.
