# Editing the agent-facing documents
- The handbook, the messages the console sends a worker, the documents that say what each agent reads, and what the tools print to a session.

## Where a section lives
- [Procedure](docs/handbook/procedure.md)
- [Principles](docs/handbook/principles.md)
- [Style](docs/handbook/style.md)
- [Patterns](docs/handbook/patterns.md)
- [Keywords](docs/handbook/keywords.md)
- [Lib addition protocol](docs/handbook/lib-protocol.md)
- [Former names](docs/handbook/former-names.md)
- The `programs/` sections: the `//!` and `///` comments of `programs/lib.dl` and of the modules under `programs/lib/`.
- The opening statements and the order the sections come in: [Handbook](prompts/handbook.md).
- What each handbook agent reads: [handbook](prompts/agents/handbook.md) and [handbook-expanded](prompts/agents/handbook-expanded.md).
- The console messages: [Console messages](prompts/console.md).
- The roles: [roles](prompts/roles), one document per role, whose `agent` attribute names the agent that runs it. A role with no such attribute runs as `handbook`.
- The audit's deletion report: [Deletion report](prompts/run_dl.md).
- The other sentences a runner tool prints: the `MESSAGES` table at the top of its module under [dl](src/dl).
- The workflow briefs and the schema descriptions: the scripts under [workflows](.claude/workflows).

## Rules for every file
- A file follows the shape the file shows.
- A string a program holds enters an agent's context when it is wrapped in `mctx`, and the check reads it there.
- A hole in such a string is `{name}` in Python and `${name}` in JavaScript, and the value it takes is computed above the literal.
- A string that opens with a marker is format lines, and any other is the text of one statement.
- A document the handbook includes links only to another document it carries, or to a file outside the document set, so a reader can follow every link it holds. A composition document is an entry point, and its lead names what the render leaves out.
- A file that carries editing notes opens with them, under a `* comment: when editing this doc` line. Read those notes before editing that file.
- Avoid justifications, unless there is necessary reason.
- Avoid contrastive structures, unless the alternative needs to be addressed.
- `uv run python -m controlled_markdown check` reports what is off, each line carrying the rule's message. `fmt` in place of `check` rewrites a file in canonical form.
- [Writing a document](src/controlled_markdown/writing.md) states a rule where the message is not enough, or where the file shows no instance of the construct you need.
- The documents under `prompts/` compose and fill one another, and [Templating a document](src/controlled_markdown/templating.md) states the directives that do it.
- The agent editions exclude the lines marked `draft` and `gloss`. A render with no agent carries them, and so does `scripts/context.py section`.
- A reference to a document or a section is a link, `[text](path)` or `[text](path#slug)`, its path taken from the repo root, and the check resolves it. A bare path stands in code that compares it, and nowhere else.
- Where two lists split a set, the second list is everything else.
- A change that moves or reshapes this text ends with a diff of the handbook render and the console messages against HEAD, read for dropped lines. A worktree of HEAD gives the old render.
