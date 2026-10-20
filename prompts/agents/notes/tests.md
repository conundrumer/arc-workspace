+ document-size-budget: 3100
* comment: when editing this doc
    - Readers: each Claude Code session on the repo and each agent launched in one, by the link of [arc-workspace](CLAUDE.md), before it writes, changes, deletes or judges a test; the code editor, the code reviewer and the lib reviewer also by the link of [code.md](prompts/agents/notes/code.md).
    - Acts, each with its section:
        - Writing, changing, deleting or judging a test: [Tests](#tests).

# Test notes
- The statements on tests that [arc-workspace](CLAUDE.md) links.

## Tests
* comment: The user's words, session 7c26445d, 2026-09-15T21:30:26Z to 22:04:42Z: "we have a ton of useless tests ... requires maintanence like changing it when the impl changes. aggressively cut them", and "regression tests are theoretically useful, overwhemlingly useless".
* comment: The user's words, session 7fd429fb, 2026-10-16T16:18:26Z: "the rule should also be updating according to the evidence, like how to classify tests", and 16:29:03Z: "approve", which chose the coordinator's option "Yes" of 16:24:31Z, the cut and the rule wording of ticket 6-1450.
- A test costs an edit each time the code it pins changes, and a later session pays it.
- So the default is no test, and a test has to earn its place.
- A test stays only when its failure would be silent in use, and it is of one of these kinds:
    - An invariant over the real repo whose break makes another check skip something, like a lib component that no gate stem runs.
    - A stored result that must be computed again when a file it rests on changes.
    - A race or a half-written file: two writers, a lock, a rename.
    - A parser or a reader that must refuse wrong input.
    - A check, hook, or gate that must refuse or report: the test feeds it the bad case and asserts the refusal.
- When a run would show the failure (a wrong grid, a failed command, an error message, a changed line in a file, the page or the feed), the run is the check, and the test is not written.
- A test asserts what a caller sees: outputs, files, exit codes, refusals. It does not assert function signatures, module names, enum values, message wording, or cache internals.
- A test does not read `data/upstream/`, the live transcripts, or the session's environment variables. It builds what it reads in `tmp_path` and clears the environment it passes to a subprocess.
- A concurrency test does not depend on timing. It forces the interleaving with a barrier or a held lock.
- A test written to fail before the code exists is not by that fact a test that stays.
- When a test your change broke is not of a kind above, delete it; don't update it.
- Assertions you need while you work go under `tests/scratch/`.
- It is collected and not committed.
