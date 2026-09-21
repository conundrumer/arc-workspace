+ agent: handbook-expanded
- The brief names the files and the spans in them to clean up.
- You edit only the files the brief names.

# Procedure
- Before the first edit of a file, run `uv run python scripts/run_dl.py <stem>` and keep the run result; report any failure or finding it gives as already there.
- A relation is renamed when its name is a former name [Former names](docs/handbook/former-names.md) lists, or collides with another relation's name in the file.
    - You rename it in every solver that shares that name.
    - This is the one exception to editing only the files the brief names.
- When the pairs leave a model undefined on some input, or do not exercise a case, the report states it as a fact, and not as a question.
    - You change nothing for it.
- When the docs leave a question open, it goes in your report as a gap in the docs.
- Do not mention this pass or an earlier form of the code in the files.
- A `// @draft` line under the task-id line stays.
- After each file, run it again.
- Confirm the run passes, with no finding the first run did not have.
- When that fails, restore the file by reversing your edits, and say why in the report.
- Scratch files go under the path the brief gives.
- Never run a git command that changes state.
- Run the operations below over the spans the brief names, in this order.
    - First, make the rewrites the brief lists, where it lists any.

## Simplify
* inline: ../../docs/handbook/procedure.md#simplify

## Prune
* inline: ../../docs/handbook/procedure.md#prune

# Report
- Per file: what you changed, or `no change` with the reason; the run result; a file the brief does not name that a rename changed, and what changed in it.
- Keep it short.
