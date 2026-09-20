# Editing the agent-facing documents
- The handbook, the console's messages to a worker, the documents that say what each agent reads, and what the tools print to a session.

## Where a section lives
- [Procedure](docs/handbook/procedure.md)
- [Principles](docs/handbook/principles.md)
- [Style](docs/handbook/style.md)
- [Patterns](docs/handbook/patterns.md)
- [Keywords](docs/handbook/keywords.md)
- [Lib addition protocol](docs/handbook/lib-protocol.md)
- [Former names](docs/handbook/former-names.md)
- The `programs/` sections: the `//!` and `///` comments of `programs/lib.dl` and of the modules under `programs/lib/`.
- The order the sections come in: [Handbook](prompts/handbook.md), which holds nothing of its own.
- What a session at a terminal reads, and the passes it runs: [Solver session](prompts/session.md).
- What each handbook agent reads: [handbook](prompts/agents/handbook.md) and [handbook-expanded](prompts/agents/handbook-expanded.md).
- The console messages: [Console messages](prompts/console.md).
- The roles: [roles](prompts/roles), one document per role. A role's `agent` attribute names the agent that runs it, and a role with none runs as `handbook`.
- The audit's deletion report: [Deletion report](prompts/run_dl.md).
- The other sentences a runner tool prints: the `MESSAGES` table at the top of its module under [dl](src/dl).
- The workflow briefs and the schema descriptions: the scripts under [workflows](.claude/workflows).

## What holds where
- The handbook holds the operations and no pass.
- An entry point lists the operations its pass runs, as links, in order.
- No document restricts, replaces or redirects an operation another document carries.
- A document the handbook includes links only to another document it carries, or to a file outside the document set.
- A composition document is an entry point, and its lead names what the render leaves out.
- The agent editions leave out the lines marked `draft` and `gloss`.
- A render with no agent carries them, and so does `scripts/context.py section`.
- Where two lists split a set, the second list is everything else.

## Writing a file
- A file follows the shape the file shows.
- A file that carries editing notes opens with them, under a `* comment: when editing this doc` line. Read those notes before editing that file.
- Avoid justifications, unless there is necessary reason.
- Avoid contrastive structures, unless the alternative needs to be addressed.
- A reference to a document or a section is a link, `[text](path)` or `[text](path#slug)`, its path taken from the repo root.
- A bare path stands in code that compares it, and nowhere else.

## Prose a program holds
- A string a program holds enters an agent's context when it is wrapped in `mctx`.
- [Prose in code](src/controlled_markdown/writing.md#prose-in-code) states how such a string is written and read.

## Checking
- `uv run python -m controlled_markdown check` reports what is off, each line carrying the rule's message.
- `fmt` in place of `check` rewrites a file in canonical form.
- The check resolves every link a document holds.
- [Writing a document](src/controlled_markdown/writing.md) states a rule where the message is not enough, or where the file shows no instance of the construct you need.
- [Templating a document](src/controlled_markdown/templating.md) states the directives the documents under `prompts/` compose and fill one another with.
- A change that moves or reshapes this text ends with a diff of the handbook render and the console messages against HEAD, read for dropped lines.
* comment:
    - A worktree of HEAD gives the old render.

## Reading a chain
- A chain is everything one reader receives, from its entry point to the last message, in the order it arrives.
- A change to this text is reviewed by reading each chain it touches from the entry point to the end, as that reader, before it is done.
- The check reads files, and a chain's contradictions, gaps and duplicates show only in the chain.
- The chains, and what assembles each:
    - The session at a terminal: `uv run python scripts/context.py`, then what each command the text names prints.
    - A handbook agent: its generated definition under `.claude/agents/`, then `uv run python scripts/context.py role <name>`, then the brief.
    - A console worker: the appendix and the messages that `tools/console/solver_console/prompts.py` builds, in the order a stage sends them.
    - A workflow agent: its role from `uv run python scripts/context.py workflow <name>`, then the brief its script builds.
    - Codex: `AGENTS.md`.
