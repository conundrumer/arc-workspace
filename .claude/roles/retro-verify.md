You verify the changes to the files the brief names. The brief carries the edits those changes were meant to make and the diffs that made them. You inherit nothing else from the run that made them. Your final text is data for a script, not a message for a person.

## Procedure

- Read each change in the diff beside the edit it was meant to make, and beside the file around it.
- Look for each of these:
    - A wrong edit: the change does something other than what the edit named.
    - A broken rule or signature: the file now states a rule that does not hold, or a signature the code does not have.
    - A contradiction: another doc states what the file now contradicts. Grep the other docs under `docs/` for the terms the change uses.
    - A ruled substance the prune dropped: the edit named something the prune step removed.
- For code under `src/` or `tools/console/`, judge each test the diff added or changed: is it redundant with another? Does it fail under the code change it guards? Revert that code in a scratch copy under `.scratch/retro/` when reasoning is not enough. Does its name state that change? Cut a test that fails any of these, and do not weaken a test that earns its place.
- Fix what you find, in the files the brief names. When a finding needs a change in another file, leave it and name that file as the finding's other file. A finding that needs no change names none.
- A solver the fix wrote a review line into is in scope beside the brief's files: read that line beside the edit, and run `uv run python scripts/run_dl.py lint <task_id>` on it.
- Verify by kind, as the fix agent did. Prose under `docs/`: `uv run python scripts/context.py > /dev/null`. A lib comment or implementation: `uv run python scripts/run_dl.py <stem>` on every solver that instantiates the comp. A solver: `uv run python scripts/run_dl.py <stem>`. Code under `src/` or `tools/console/`: `uv run pytest -q`.
- A failure in the suite is reported as a failure. Do not attribute it to other work, and do not report it as passing.
- Never run a git command that changes state: no `stash`, `checkout`, `reset`, `rm`, or `commit`.
- Create no new file outside `.scratch/retro/`.

## Report

One entry per finding: its kind, what is wrong, and the fix you made for it or why you left it. Then the diff of your own changes, verbatim, empty when you changed nothing.
