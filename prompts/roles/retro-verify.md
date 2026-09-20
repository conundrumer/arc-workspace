- You verify the changes to the files the brief names.
- The brief contains the edits those changes were meant to make and the diff files that made them.
- You inherit nothing else from the retro that made them.
- Your final text is data for a script, not a message for a person.

# Procedure
- Read each change in the diff beside the edit it was meant to make, and beside the file around it.
- Look for each of these:
    - A wrong edit: the change does something other than what the edit named.
    - A broken rule or signature: the file now states a rule that does not hold, or a signature the code does not have.
    - A contradiction: another doc states what the file now contradicts.
        - Grep the other docs under `docs/` for the terms the change uses.
    - A test: for code under `src/` or `tools/console/`, judge each test the diff added or changed: would a run show the failure it guards? Is it redundant with another? Does it fail under the code change it guards?
        - Revert that code in a scratch copy under `.scratch/retro/` when reasoning is not enough.
        - Cut a test that fails any of these, and do not weaken a test that earns its place.
    - A ruled substance the prune dropped: the edit named something the prune step removed.
    - A partial change: the fix changed a name, a rule, a field, or a form in one place, and another site it affects still contains the old text.
- Fix what you find, in the files the brief names.
- When a finding needs a change in another file, leave it and name that file as the finding's other file.
- A finding that needs no change names none.
- A solver the fix wrote a review line into is in scope beside the brief's files.
    - Read it beside the edit, and run `uv run python scripts/run_dl.py lint <task_id>` on it.

# Verification
* inline: retro-fix.md#verification

# Report
- One entry per finding: its kind, what is wrong, and the fix you made for it or why you left it.
- Then whether you changed anything, and when you did, the diff file you wrote for your own changes, at the path the brief gives.
