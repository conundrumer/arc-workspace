# fc4aaf52 Analyze progress

- `interference`: the PreToolUse:Bash hook blocked the first worktree check (`git rev-parse --path-format=absolute --git-common-dir`) because the documents changed at launch; the diff only removed the workflow-script note. Cost one repeated call; nothing in the output was wrong.
- `interference`: `lib_components.components.Components(...)` (the call [Analyze](.claude/analyze-next.md) step 2 has a script make in place of rebuilding a component) raises `RuntimeError: no souffle binary on PATH`; no souffle binary is installed. Cost one failed probe run and a fallback: the probe rebuilds 4-connected components and layer distances in Python. Output not wrong, but the probe does not run the lib's own components; still so.
