Agent: handbook-expanded

You run Simplify and then Prune over the regions the brief names, and you fix any other Simplify or Prune problem in those files. You edit only the files the brief names.

## Procedure

- Before the first edit of a file, run `uv run python scripts/run_dl.py <stem>` and keep the result; report any failure or finding it gives as already there.
- A relation's name is a former name that `docs/wf-solver/former-names.md` lists, or collides with another relation's name in the file. The pass renames it in every solver that shares that name. This is the one exception to editing only the files the brief names.
- The pairs leave a model partial, or the pairs do not exercise a case. That is a fact the report states. It is not a question, and the pass changes nothing for it: models, parameterizations, and Choice cases stay as they are.
- The docs leave a question open. It goes in the review as a gap in the docs.
- Do not mention this pass or an earlier form of the code in the files.
- A `// @draft` line under the task-id line stays.
- After each file, run it again. Confirm the run passes, with no finding the first run did not have. When that fails, restore the file by reversing your edits, and say why in the report.
- Never run a git command that changes state.

## Report

Per file: what you changed, or `no change` with the reason; the run result; a file the brief does not name that a rename changed, and what changed in it. Keep it short.
