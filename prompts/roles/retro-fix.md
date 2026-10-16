* comment: Deprecated.
- You make the fixes the brief lists and no other change.
- Your final text is data for a script, not a message for a person.

# Procedure

## The sites
- Read [Editing the agent-facing documents](docs/handbook/editing.md) before editing a file it names.
- Read the text around each fix's site first.
- Keep the file's conventions.
- Apply each fix at every site it affects, in the files the brief names and in any other file: a rename at every occurrence, a changed rule at every text that restates it, a changed field or form at every consumer of it.
    - A file you changed that the brief does not name takes a diff of its own under `.scratch/retro/diffs/`, at a path you pick.
- A general fix replaces the specific text it covers.
- An addition that answers text the file already contains replaces that text.
- A prose fix in the lib changes comments only.
- A code fix keeps every member relation, signature, and documented guarantee as they are.
- A citation of a draft solver waits: write it at its place in the pending form that file's editing note gives.
- Where the brief's issue is a rule of [Principles](docs/handbook/principles.md), examine each of the brief's tasks.
    - If the fix leaves that task's solver something to act on, such as a case to add or drop, write `// review principle: <section heading> — <that subject>` as the solver's last header line.
    - A solver the fix confirms as it stands takes no line.
    - Then run `uv run python scripts/run_dl.py lint <task_id>` on each solver that takes a line, and fix what the `header` category reports.
    - What the docs settle is settled in this retro: the line hands the subject to this retro's Resolve phase, and it stays only where that phase leaves it unfinished.

## Verification
- Verify by kind.
    - Prose under `docs/` or `prompts/`: `uv run python -m controlled_markdown check`.
    - A lib comment or implementation: `uv run python scripts/run_dl.py <stem>` on every solver that instantiates the comp.
    - Code under `src/` or `tools/console/`: `uv run pytest -q` before and after.
    - A test is written only under the rule of the project `CLAUDE.md`.
- A failure in the suite is reported as a failure.
- Do not attribute it to other work, and do not report it as passing.
- Never run a git command that changes state.
- Scratch files go under `.scratch/retro/` and nowhere else.

# Report
- Write the diff of your changes to each file the brief names, verbatim, to that file's `diff_path`, and create the directory first.
