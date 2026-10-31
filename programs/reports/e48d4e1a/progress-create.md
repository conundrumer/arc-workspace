# e48d4e1a progress

- interference: the command `for f in $(grep -L '^// @draft' programs/solvers/*.dl); do grep -l 'comp Determine' $f; done` was blocked by the PreToolUse hook (`unsupported executable construct 'for'`). It cost one retry, which used `xargs`. The output is no longer wrong.
