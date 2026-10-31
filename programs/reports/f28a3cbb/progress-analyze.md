# f28a3cbb Analyze progress

## Issues
- `interference`: the PreToolUse:Bash hook blocked the first command (`git rev-parse ... && ls ...`) to deliver a context diff, which dropped the workflow NOTE from the context. Cost: one repeated call. Nothing was wrong in the output; nothing still is.
- `interference`: the lib call that the Analyze step 2 line "call the component in place of rebuilding it" gives (`lib_components.components.Components`, run from `work/task/f28a3cbb/probe.py`) raised `RuntimeError: no souffle binary on PATH`. Cost: one failed probe run and a rewrite of the probe's component labelling as a Python BFS. Nothing was wrong in the output; the probe now labels components without the lib.
