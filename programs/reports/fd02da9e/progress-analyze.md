# fd02da9e — Analyze progress

- `interference`: the PreToolUse:Bash hook blocked the first Bash call of the pass (`git rev-parse --path-format=absolute --git-common-dir ...`) to deliver a context diff, which removed only the workflow NOTE at the end of the context. Cost: one repeated call and reading the diff. Nothing in the output was wrong, and nothing still is.
