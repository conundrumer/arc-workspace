# Editing the agent-facing documents
- The handbook, the console's messages to a worker, the documents that say what each agent reads, and what the tools print to a session.

## Where a section lives
- [Principles](docs/handbook/principles.md)
- [Solver file](docs/handbook/solver-file.md)
- [Style](docs/handbook/style.md)
- [Patterns](docs/handbook/patterns.md)
- [Keywords](docs/handbook/keywords.md)
- [Lib addition protocol](docs/handbook/lib-protocol.md)
- [Former names](docs/handbook/former-names.md)
- The operations: [Procedure](docs/handbook/procedure.md).
- The `programs/` sections: the `//!` and `///` comments of `programs/lib.dl` and of the modules under `programs/lib/`.
- The order the sections come in: [Handbook](prompts/handbook.md), which holds nothing of its own.
- What every session in the repo reads: [arc-workspace](CLAUDE.md).
- What a session at a terminal reads, and the passes it runs: [Session](.claude/skills/session/SKILL.md), then [Solver session](prompts/session.md).
    - [Session](.claude/skills/session/SKILL.md) carries no `comment` directive.
    - Its context: `context session`, then what each command the text names prints.
- What a codex session on the repo reads: [Codex on arc-workspace](prompts/codex.md).
    - Its context: `context codex`, then the user's message.
- What each handbook agent reads: [handbook](prompts/agents/handbook.md) and [handbook-expanded](prompts/agents/handbook-expanded.md).
    - Its context: `context agent <name>`.
- The statements an entry point inlines into its lead: [Shared notes](prompts/agents/notes.md).
- The console messages: [Console messages](prompts/console.md).
    - A worker's context: the appendix, the message the stage opens with, then each message a condition sends, under that condition: `context console <stage>`.
    - A survey session's context: the appendix, its role, then the `survey` message: `context survey`.
    - The system reminders the console prefixes to a message: [workers.py](tools/console/solver_console/workers.py).
- The roles: [roles](prompts/roles), one document per role. A role's `agent` attribute names the agent that runs it, and a role with none runs as `handbook`.
    - Its context: `context role <name>`.
    - A role's brief comes from the script or the session that spawns it, and the `context role` output names that file.
- The audit's deletion report: [Deletion report](prompts/run_dl.md).
- The other sentences a runner tool prints: the `mctx` strings of the modules under [dl](src/dl), and the help text in [cli.py](src/dl/cli.py) and [context.py](scripts/context.py).
- What the callout-rate classifier reads: [Classification rubric](tools/console/recal/RUBRIC.md).
- The classifier: [Callout rate recalibration](tools/console/recal/README.md).
- The workflow briefs and the schema descriptions: the scripts under [workflows](.claude/workflows).
    - A workflow agent that runs a role reads `context workflow <name>`, and an agent with no role reads its brief alone.
    - `readerFor` in [retro.js](.claude/workflows/retro.js) names the reader of each document a retro fix touches.
- `uv run python scripts/context.py --write` generates files git does not track, and `uv run python scripts/context.py --help` names them.

## What goes where
- A file is written for the reader its entry point names, and holds what that reader needs for the work it does there.
    - A document the handbook includes says nothing that holds for one entry point and not another.
    - An entry point inlines each operation it runs, in order, under a heading of its name.
    - A session's entry point inlines [Every pass](docs/handbook/procedure.md#every-pass) as well.
    - A console worker and the `handbook-expanded` agent read the lib as its interface.
    - Every other reader reads the index, and a declaration's interface when it needs one.
- A fact or a rule is stated in one file, and every other file links it.
- A link depends on a section's heading, and never on what the body says.
- No document restricts, replaces or redirects an operation another document carries.
- A document the handbook includes links only to a document an entry point in `HANDBOOK_ENTRIES` in [__main__.py](src/controlled_markdown/__main__.py) carries, or to a file outside the document set.
- A document rendered on its own is an entry point, and its lead names what the render leaves out.
- A render leaves out the lines marked `draft` and `gloss` where its entry point excludes them.
    - The session render carries them, and so does `scripts/context.py section`.
- Where two lists split a set, the second list is everything else.

## Writing a file
- A file follows the shape the file shows.
- A file that carries editing notes opens with them, under a `* comment: when editing this doc` line. Read those notes before editing that file.
- Avoid justifications, unless there is necessary reason.
- Avoid contrastive structures, unless the alternative needs to be addressed.
- A reference to a document or a section is a link, as [Links](src/controlled_markdown/writing.md#links) gives it.
- A bare path stands in code that compares it, and nowhere else.
- Prefer precise and conventional words.

## Prose a program holds
- [Prose in code](src/controlled_markdown/writing.md#prose-in-code) states how such a string is written and read.

## Checking
- `uv run python -m controlled_markdown check` reports what is off, each line carrying the rule's message.
- A run with nothing to report prints one line: the count of documents it read, and `ok`.
- `fmt` in place of `check` rewrites a file in canonical form.
- The document set is the paths under `[tool.controlled_markdown]` in `pyproject.toml`.
- [Controlled Markdown](src/controlled_markdown/README.md) states the format and indexes the other documents of the package.
- [Writing a document](src/controlled_markdown/writing.md) states a rule where the message is not enough, or where the file shows no instance of the construct you need.
- [Templating a document](src/controlled_markdown/templating.md) states the directives the documents under `prompts/` compose and fill one another with.
- [The grammar](src/controlled_markdown/grammar.md) states the rules and the edge cases the other two leave out.
- A change that moves or reshapes this text ends with a diff of the handbook render and the console messages against HEAD, read for dropped lines.
* comment:
    - A worktree of HEAD gives the old render.

## Reading a context
- A reader's context is everything it receives, from its entry point to the last message, in the order it arrives.
- `uv run python scripts/context.py contexts` lists the readers, and `uv run python scripts/context.py context <reader> [args]` prints one reader's context, with the argument the listing gives for that reader.
- The `context` output leaves out [arc-workspace](CLAUDE.md), which the harness gives every session, and the system reminders [workers.py](tools/console/solver_console/workers.py) prefixes to a console message.
- A change to this text is reviewed by reading each context it touches from the entry point to the end, as that reader, before it is done.
- The check reads files, and a context's contradictions, gaps and duplicates show only in the context.
