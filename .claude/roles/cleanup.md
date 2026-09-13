Agent: handbook-expanded

You run Simplify and then Prune, as the procedure defines them, over the regions the brief names, and you fix any other Simplify or Prune problem in those files. You edit only the files the brief names.

## Procedure

- Before the first edit of a file, run `uv run python scripts/run_dl.py <stem>` and keep the result; report any failure or finding it gives as already there.
- Models, parameterizations, and Choice cases stay as they are.
- Do not mention this pass or an earlier form of the code in the files.
- A `// draft` line under the task-id line stays.
- After each file, run it again. Confirm the run passes, with no finding the first run did not have. When that fails, restore the file by reversing your edits, and record why.
- Never run a git command that changes state.

## Report

Per file: what you changed, or `no change` with the reason; the run result; what looks wrong in the hypothesis and needs the caller's ruling. An observation in a file the brief does not name names the operation it belongs to (Simplify or Prune) and what acting on it would change. Keep it short.
