# Editing the agent-facing documents
- The handbook, the console's messages to a worker, the documents that say what each agent reads, and what the tools print to a session.

## What a file holds
- A file is written for the reader of its entry point, and holds what that reader needs for the work it does there and nothing more.
- A line is added or kept only where its reader could not infer what it says, or would misread its context without it.
- An edit is, in order of preference, a deletion; no change, where a tool or another line already covers it; a change to existing words; and new words only where none of those is enough.
- A fix changes the line that caused the finding, and adds no exception to a rule for a small inconsistency.
- When the premise of a line is wrong, the fix changes the line that states that premise.
- A line kept against a rule of this document, or put back after a cut, carries a `comment`, as [Directives](src/controlled_markdown/writing.md#directives) gives it, that says why it stays. A comment on a kept restatement lists the sessions that needed it, by task and pass, when a session did.

## Where a section lives
- The handbook's documents, in order: [Handbook](prompts/handbook.md), which holds nothing of its own.
- The operations: [Procedure](docs/handbook/procedure.md).
- The `programs/` sections: the `//!` and `///` comments of `programs/lib.dl` and of the modules under `programs/lib/`.
- What every session in the repo reads: [arc-workspace](CLAUDE.md).
- What a session at a terminal reads, and the passes it runs: [Session](.claude/skills/session/SKILL.md), then [Solver session](prompts/session.md).
    - [Session](.claude/skills/session/SKILL.md) carries no `comment` directive.
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
- The audit's deletion report: [Deletion report](prompts/run_dl.md).
- The other sentences a runner tool prints: the `mctx` strings of the modules under [dl](src/dl), and the help text in [cli.py](src/dl/cli.py) and [context.py](scripts/context.py).
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
    - A reader of the index reads a declaration's interface when it needs one.
- A document mentions a file under `src/` only where its reader runs or reads the file.
- A fact or a rule is stated once, in the document and the section whose subject it is, and every other place links it.
- A link depends on a section's heading, and never on what the body says.
- No document restricts, replaces or redirects an operation another document carries.
- A document the handbook includes links only to a document an entry point in `HANDBOOK_ENTRIES` in [__main__.py](src/controlled_markdown/__main__.py) carries, or to a file outside the document set.
- A document rendered on its own is an entry point, and its lead says what the render leaves out when a link in the render leads there.
- A render leaves out the lines that carry an attribute its entry point excludes. Outside an entry point's lead, no heading of the render is left with nothing under it, and no line of it refers to a section the render leaves out.
    - `deferred` marks a section of a pass no entry point runs yet.
    - The session render carries them, and so does `scripts/context.py section`.

## Writing a file
- A file follows the shape the file shows.
- A file that carries editing notes opens with them, under a `* comment: when editing this doc` line. Read those notes before editing that file.
- A line uses precise and conventional words, each term in the meaning the documents give it, and no contrastive structure unless the alternative must be addressed.
    - A word is used in its literal sense: `name` as a verb is for giving a thing a name, and nowhere else.
- A reference to a document or a section is a link, as [Links](src/controlled_markdown/writing.md#links) gives it.
- A bare path stands in code that compares it, and nowhere else.
- A document tells no agent to write a file named `report.md`.
    * comment:
        - The harness refuses a write to that name.

## Checking
- `uv run python -m controlled_markdown check` reports what is off, each line carrying the rule's message.
- `fmt` in place of `check` rewrites a file in canonical form.
- The document set is the paths under `[tool.controlled_markdown]` in `pyproject.toml`.
- [Controlled Markdown](src/controlled_markdown/README.md) states the format and indexes the other documents of the package.
- [Writing a document](src/controlled_markdown/writing.md) states a rule where the message is not enough, or where the file shows no instance of the construct you need.

## Reviewing a change
- A reader's context is everything it receives, from its entry point to the last message, in the order it arrives.
- `uv run python scripts/context.py contexts` lists the readers, and `uv run python scripts/context.py context <reader> [args]` prints one reader's context, with the argument the listing gives for that reader.
- The `context` output leaves out [arc-workspace](CLAUDE.md) and the system reminders [workers.py](tools/console/solver_console/workers.py) prefixes to a console message.
- A change to this text is reviewed before it is called done and before an agent runs on it. The review reads each context the change touches, from the entry point to the end, as that reader.
    - The review reads the `context` output for that reader, with [arc-workspace](CLAUDE.md), and judges each line as a reader that has only that context and none of the files the editor has open. A fresh agent does the review.
    - The review follows the reader through each operation its context gives, in order. At each operation, it asks what the reader is focused on, what it holds, where each output it makes goes (a file, its report, or its reply), and whether the context gives what the operation needs.
    - Where one pass takes another pass's output, the review checks that the form the first pass's context gives that output is the form the second pass's context reads.
    - The review checks each line against [What a file holds](#what-a-file-holds) and [What goes where](#what-goes-where).
    - The review reports as a separate item each line that gives an agent a power it did not have, such as deleting, overwriting, renaming, reverting, or deciding what the user decides, and each line that moves a step between the user, the session at a terminal, and an agent.
    - The review starts from the assumption that defects are there, and traces each one to the line that caused it, or to the premise that is wrong.
    - A finding is one instance of a kind, and the review searches every context for the other instances of that kind.
    - After each fix, the contexts the fix touches are read again for contradictions.
- A change that moves or reshapes this text ends with a diff of the handbook render and the console messages against HEAD, read for dropped lines.
    * comment:
        - A worktree of HEAD gives the old render.
