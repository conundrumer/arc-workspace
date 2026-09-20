- You make the fixes the brief lists in the files it names, then prune the text those fixes added or changed.
- You make no other change.
- Your final text is data for a script, not a message for a person.

# The fix
* inline: retro-fix.md#the-sites
- Write the diff of this step, verbatim, to each file's `diff_path`, and create the directory first.

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
- Keep a task-id example only when it makes the rule concrete in a way the sentence alone does not.
- Revise the added text to the file's own style: what [Writing a file](docs/handbook/editing.md#writing-a-file) and its editing note give, in plain sentences with simple words, the given before the new.
- A negated alternative that the positive excludes is cut.
- Where the positive does not exclude it, the positive is restated as the form itself, and the negative is cut.
- Keep the meaning.
- A cut or a rewording changes no rule.
- When the brief says the user ruled for the fixes, keep the rule each edit states.
- A pointer to another doc, a ground, or a consequence is not the rule.
- Write the diff of this step, verbatim, to each file's `prune_path`.

# Verification
* inline: retro-fix.md#verification
- Run the verification once over the fix edits together, and once over the prune edits together.

# Report
- A file's `diffs` entry carries its `prune_path`.
