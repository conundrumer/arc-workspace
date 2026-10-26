+ document-size-budget: 3100
* comment: when editing this doc
    - Readers: each Claude Code session on the repo and each agent launched in one, by the link of [arc-workspace](CLAUDE.md), before it writes, changes, deletes or judges a test; the code editor, the code reviewer and the lib reviewer also by the link of [code.md](prompts/agents/notes/code.md).
    - Acts, each with its section:
        - Writing, changing, deleting or judging a test: [Tests](#tests).

# Test notes
- The statements on tests that [arc-workspace](CLAUDE.md) links.

## Tests
* comment: The user's words, session 7c26445d, 2026-09-15T21:30:26Z to 22:04:42Z: "we have a ton of useless tests ... requires maintanence like changing it when the impl changes. aggressively cut them", and "regression tests are theoretically useful, overwhemlingly useless".
* comment: The user's words, session 58147d46, 2026-10-26T19:59:53Z to 20:04:01Z: "we only keep tests when the point is to track progress on incomplete features", "example: the souffle->arclog converter is an inprogress feature. we need tests there to see what still needs to be built", "so if a test is for in-progress, it cannot gate anything. it's basically a check. which means. no gated tests at all", and "ok you know what this means. we are banning tests". The coordinator's transcript evidence of 19:47:45Z: of 185 failure episodes on the current tests, 85 ended in a test fix and 19 in a code fix.
- Write no test, other than a check that tracks an in-progress feature.
- Such a check shows what the feature still lacks, by its cases that fail. It fails on purpose, so no change check or merge waits on its result.
- Delete such a check when its feature is done.
- A test asserts what a caller sees: outputs, files, exit codes, refusals. It does not assert function signatures, module names, enum values, message wording, or cache internals.
* comment: The user's words, session 2384db39, 2026-10-22T22:20:24Z: "delete and ban mock-heavy tests", which answered the coordinator's report of 22:16:26Z: "65 of them (12%) stub collaborators on the call path, which is the kind that failed on 7b7de877."
- A test runs the repo's code that its subject calls, with no stub or fake in place of any of it, whether a patch puts it in place or the test passes it as an argument. A callable or a mock object passed as an argument is a stand-in where the subject's parameter gives a specific read or action of the repo, and is input where the subject's contract leaves open what it does, such as a handler of a generic runner. It may replace a constant, module state, or code that gives a path (with a path under `tmp_path`), and a process the repo does not hold, at that process's boundary, such as a subprocess or a socket peer, and not the repo's code that calls that process.
- A test does not read `data/upstream/`, the live transcripts, or the session's environment variables. It builds what it reads in `tmp_path` and clears the environment it passes to a subprocess.
- When a test your change broke does not track an in-progress feature, delete it; don't update it.
