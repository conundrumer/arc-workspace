# Progress: analyze ec883f72

- `interference`: the PreToolUse:Bash hook blocked the first Bash call of the pass (the worktree check, `git rev-parse --path-format=absolute --git-common-dir`) and sent a context diff instead, so the call had to be run again. Cost: one extra call and a re-read of the diff. Output was not affected and is still correct.
