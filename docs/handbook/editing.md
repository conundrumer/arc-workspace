# Editing the agent-facing documents
- The handbook, the console's messages to a worker, the documents that say what each agent reads, and what the tools print to a session.

## What a file holds
- A file holds what the reader of its entry point needs for the work it does there, and nothing more.
- Add or keep a line only where its reader could not infer what it says, or would misread its context without it.
- Choose an edit in this order of preference: a deletion; no change, where a tool or another line already covers it; a change to existing words; and new words only where none of those is enough.
- Fix a finding by changing the line that caused it, and add no exception to a rule for a small inconsistency.
- When the premise of a line is wrong, change the line that states that premise.
- A line kept against a rule of this document, or put back after a cut, has a `comment`, as [Directives](src/controlled_markdown/writing.md#directives) gives it, that says why it stays. A comment on a kept restatement lists the sessions that needed it, by task and pass, when a session did.

## Where each text is
- The handbook's documents: [Handbook](prompts/handbook.md) includes them in order, and holds no text of its own.
- The operations: [Procedure](docs/handbook/procedure.md).
- The lib's sections: the `//!` and `///` comments of [lib.dl](programs/lib.dl) and of the modules under [lib](programs/lib).
- What every session in the repo reads: [arc-workspace](CLAUDE.md).
- What a session at a terminal reads, and the passes it runs: [Session](.claude/skills/session/SKILL.md), then [Solver session](prompts/session.md).
    - [Session](.claude/skills/session/SKILL.md) has no `comment` directive.
    - Its context: `context session`, then the output of each command the text gives.
- What a codex session on the repo reads: [Codex on arc-workspace](prompts/codex.md).
    - Its context: `context codex`, then the user's message.
- What each agent reads: the prompt of its name under [agents](prompts/agents).
    - Its context: `context agent <name>`.
    - The `analyze` agent reads [Analyze after the concept](prompts/agents/analyze-next.md) after it writes the concept.
- The statements more than one entry point inlines: [Shared notes](prompts/agents/notes.md).
- The console messages: [Console messages](prompts/console.md).
    - A worker's context: the appendix, the message the stage opens with, then each message a condition sends, under that condition: `context console <stage>`.
    - A survey session's context: the appendix, its role, then the `survey` message: `context survey`.
    - The system reminders the console prefixes to a message: [workers.py](tools/console/solver_console/workers.py).
    - The committer's brief: `commit_brief` in [config.py](tools/console/solver_console/config.py).
- The roles: [roles](prompts/roles), one document per role. A role's `agent` attribute says which agent runs it, and a role with none runs as `handbook`.
    - Its context: `context role <name>`.
    - A role's brief comes from the script or the session that spawns it, and the `context role` output gives that file's path.
- The `deletions` report: [Deletion report](prompts/run_dl.md).
- The other sentences a runner tool prints: the `mctx` strings of the modules under [render](src/checker/render) and of [text.py](src/cli/text.py), and the help text in [parser.py](src/cli/parser.py) and [context.py](scripts/context.py).
- What the callout-rate classifier reads: [Classification rubric](tools/console/recal/RUBRIC.md).
- The classifier: [Callout rate recalibration](tools/console/recal/README.md).
- The workflow briefs and the schema descriptions: the scripts under [workflows](.claude/workflows).
    - A workflow agent that runs a role reads `context workflow <name>`, and an agent with no role reads its brief alone.
    - `readerFor` in [retro.js](.claude/workflows/retro.js) gives the reader of each document a retro fix touches.
- `uv run python scripts/context.py --write` generates files git does not track, and `uv run python scripts/context.py --help` lists them.

## What goes where
- A document the handbook includes says nothing that holds for one entry point and not another.
- An entry point inlines each operation it runs, in order, under a heading of its name.
    - A session's entry point inlines [Every pass](docs/handbook/procedure.md#every-pass) as well.
- An entry point's `+ lib:` attribute says how it reads the lib.
    - A reader whose `+ lib:` is `index` reads a declaration's interface when it needs one.
- A document mentions a file under [src](src) only where its reader runs or reads the file.
- State a fact or a rule once, in the document and the section whose subject it is, and link it from every other place.
- A line that links a section relies on that section's heading alone.
- No document restricts, replaces or redirects an operation another document states.
- A document the handbook includes links only to a document an entry point in `HANDBOOK_ENTRIES` in [__main__.py](src/controlled_markdown/__main__.py) includes, or to a file outside the document set.
- A document rendered on its own is an entry point, and its lead says what the render leaves out when a link in the render leads there.
- A render leaves out the lines that have an attribute its entry point excludes. Outside an entry point's lead, no heading of the render is left with nothing under it, and no line of it refers to a section the render leaves out.
    - `deferred` marks a section of a pass no entry point runs yet.
    - The session render includes them, and so does `uv run python scripts/context.py section`.

## Writing a file
- In an edit, follow the form the file's other lines show.
- A file that has editing notes opens with them, under a `* comment: when editing this doc` line. Read them before you edit the file.
- A line uses precise and conventional words, each term in the meaning the documents give it, and no contrastive structure unless the alternative must be addressed.
    - A line uses each word in its literal sense: `name` as a verb is for giving a thing a name, and nowhere else.
- Write that a thing always holds or never holds only where you know it does. Where a check is what the claim rests on, state the claim over the instances the check covered, such as the task's inputs.
    - Such a claim most often uses `never`, `every`, `no` or `nothing`.
- Write a statement in the imperative mood where it tells its reader to do something or sets a rule on an act its reader does, and every other statement in the indicative mood.
- A reference to a document or a section is a link, as [Links](src/controlled_markdown/writing.md#links) gives it.
- A bare path stands in code that compares it, and nowhere else.
- A document tells no agent to write a file named `report.md`.
    * comment:
        - The harness refuses a write to that name.

## Checking
- `uv run python -m controlled_markdown check` reports each line that breaks a rule, with the rule's message.
- `fmt` in place of `check` rewrites a file in canonical form.
- The document set is the paths under `[tool.controlled_markdown]` in [pyproject.toml](pyproject.toml).
- [Writing a document](src/controlled_markdown/writing.md) states a rule where the message is not enough, or where the file shows no instance of the construct you need.

## Reviewing a change
- A reader's context is everything it receives, from its entry point to the last message, in the order it arrives.
- `uv run python scripts/context.py contexts` lists the readers, and `uv run python scripts/context.py context <reader> [args]` prints one reader's context, with the argument the listing gives for that reader.
- The `context` output leaves out [arc-workspace](CLAUDE.md) and the system reminders [workers.py](tools/console/solver_console/workers.py) prefixes to a console message.
- Review a change by reading each context that contains the changed lines, from its entry point to the end, as the reader of that context.
    - Read the `context` output for that reader, with [arc-workspace](CLAUDE.md), and judge each line as a reader that has only that context.
    - Follow the reader through each operation its context gives, in order. At each operation, ask what the reader is focused on, what it holds, where each output it makes goes (a file, its report, or its reply), and whether the context gives what the operation needs.
    - Where one pass takes another pass's output, check that the form the first pass's context gives that output is the form the second pass's context reads.
    - Check each line against [What a file holds](#what-a-file-holds) and [What goes where](#what-goes-where).
    - Report each line that gives an agent a power it did not have, such as deleting, overwriting, renaming, reverting, or deciding what the user decides, and each line that moves a step between the user, the session at a terminal, and an agent. Report each such line as an item of its own, to the one who asked for the change.
    - Start from the assumption that defects are there, and trace each one to the line that caused it, or to the premise that is wrong.
    - Treat a finding as one instance of a kind, and search every context for the other instances of that kind.
    - After each fix, read the contexts the fix touches again for contradictions.
- After a change that moves or reshapes the lines of a document, diff the handbook render and the console messages against HEAD, and read the diff for dropped lines.
    * comment:
        - A worktree of HEAD gives the old render.
