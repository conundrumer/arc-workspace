- You make the fixes the brief lists in the files it names, then prune the text those fixes added or changed.
- You make no other change.
- Your final text is data for a script, not a message for a person.

# The fix
- Read the region first.
- Keep the file's conventions.
- A file that opens with a `* comment: when editing this doc` block takes the notes under it; read them before editing that file.
- Apply each fix at every site it affects, in the files the brief names and in any other file: a rename at every occurrence, a changed rule at every text that restates it, a changed field or form at every reader of it.
- A general fix replaces the specific text it covers.
- An addition that answers text the file already contains replaces that text.
- In `programs/lib.dl` and the modules under `programs/lib/` change comments only.
- An entry fix writes the entry with the fields [The entry](docs/handbook/lib-protocol.md#the-entry) gives, its `Survey:` line stamped with the current time to the minute, and stops there.
    - It does not change the lib.
- A citation of a draft solver waits: write it at its place in the pending form that file's editing note gives.
- Where the brief's issue is a rule of [Principles](docs/handbook/principles.md), examine each of the brief's tasks.
    - If the fix leaves that task's solver something to act on, such as a case to add or drop, write `// review principle: <section heading> — <that point>` as the solver's last header line.
    - A solver the fix confirms as it stands takes no line.
    - Then run `uv run python scripts/run_dl.py lint <task_id>` on each solver that takes a line, and fix what the `header` category reports.
    - What the docs settle is settled in this run: the line hands the point to this run's resolve stage, and it stays only where that stage leaves it unfinished.
- Write the diff of this step, verbatim, to each file's `diff_path`.

# The prune
- The prune runs over the diff the fix made, and it takes the fixes above as the edits that diff was meant to make.
- The brief names the reader of each file.
- Ask what that reader needs the text for, and keep what serves that.
- Read each edit against the diff.
* comment:
    - A cut then takes nothing the edit called for.
- Cut every idea, clause, and phrase the reader does not need for that.
- Think in terms of necessity, not usefulness.
- Do not compress into a telegraphic style.
- Read the paragraph or entry around each edit.
- Where the addition answers text already there, replace the older text.
- Keep a task-id example only when it makes the rule concrete in a way the sentence alone does not.
- Revise the added text to the file's own style: what its editing note gives, and elsewhere plain sentences with simple words, the given before the new, and no contrastive structure unless the alternative must be addressed.
- A negated alternative that the positive excludes is cut.
- Where the positive does not exclude it, the positive is restated as the form itself, and the negative is cut.
- Keep the meaning.
- A cut or a rewording changes no rule.
- When the brief says the user ruled for the fixes, keep the rule each edit states.
- A pointer to another doc, a ground, or a consequence is not the rule.
- Write the diff of this step, verbatim, to each file's `prune_path`.

# Verification
- Verify prose under `docs/` with `uv run python scripts/context.py > /dev/null`.
- Verify a lib comment with `uv run python scripts/run_dl.py <stem>` on every solver that instantiates the comp.
- Run the verification once over the fix edits together, and once over the prune edits together. It does not run per file.
- A failure in the suite is reported as a failure.
- Do not attribute it to other work, and do not report it as passing.
- Never run a git command that changes state.
- Create no new file outside `.scratch/retro/`.

# Report
- Report both steps.
- One `diffs` entry per file you changed, the files the brief names and the others alike: the file, and its `prune_path`, since the prune step left the final state.
    - A file you changed that the brief does not name takes a diff of its own under `.scratch/retro/diffs/`, at a path you pick, and that path is its entry's.
- The `notes` field carries one line per cut, and the meaning before and after of each rule the diff touches.
- Then what was run and its result, any citation left pending, and the net word count, words added minus words removed.
