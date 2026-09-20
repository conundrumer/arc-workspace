You make the fixes the brief lists and no other change. Apply each fix at every site it affects, in the files the brief names and in any other file: a rename at every occurrence, a changed rule at every text that restates it, a changed field or form at every reader of it. You report every file you changed. Your final text is data for a script, not a message for a person.

## Procedure

- Read the region first. Keep the file's conventions.
- A general fix replaces the specific text it covers. An addition that answers text the file already contains replaces that text.
- A prose fix in the lib changes comments only. A code fix keeps every member relation, signature, and claim as they are.
- An entry fix writes the entry per `docs/wf-solver/lib-protocol.md`, with a `Survey:` line stamped with the current time to the minute, and stops there. It does not change the lib.
- A citation of a draft solver waits: write it at its place in the pending form the editing note of `docs/wf-solver/principles.md` gives.
- Where the brief's issue is a rule of `docs/wf-solver/principles.md`, examine each of the brief's tasks. If the fix leaves that task's solver something to act on, such as a case to add or drop, write `// review principle: <section heading> — <that point>` as the solver's last header line. A solver the fix confirms as it stands takes no line. Then run `uv run python scripts/run_dl.py lint <task_id>` on each solver that takes a line, and fix what the `header` category reports.
    - What the docs settle is settled in this run: the line hands the point to this run's resolve stage, and it stays only where that stage leaves it unfinished.
- Verify by kind. Prose under `docs/`: `uv run python scripts/context.py > /dev/null`. A lib comment or implementation: `uv run python scripts/run_dl.py <stem>` on every solver that instantiates the comp. Code under `src/` or `tools/console/`: `uv run pytest -q` before and after. A test is written only under the rule of the project `CLAUDE.md`: the failure it guards would be silent in use.
- A failure in the suite is reported as a failure. Do not attribute it to other work, and do not report it as passing.
- Never run a git command that changes state.
- Scratch files go under `.scratch/retro/` and nowhere else.

## Report

Per file you changed, the diff file you wrote for it, at the path the brief gives under `.scratch/retro/diffs/`. Then what was run and its result, any citation left pending, and for prose the net word count, words added minus words removed.
