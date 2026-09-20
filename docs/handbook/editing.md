# Editing the agent-facing documents
- The handbook, the messages the console sends a worker, the documents that say what each agent reads, and what the tools print to a session.

## Where a section lives
- [Procedure](procedure.md)
- [Principles](principles.md)
- [Style](style.md)
- [Patterns](patterns.md)
- [Keywords](keywords.md)
- [Lib addition protocol](lib-protocol.md)
- [Former names](former-names.md)
- The `programs/` sections: the `//!` and `///` comments of `programs/lib.dl` and of the modules under `programs/lib/`.
- The opening statements and the order the sections come in: [Handbook](../../prompts/handbook.md).
- What each handbook agent reads: [handbook](../../prompts/agents/handbook.md) and [handbook-expanded](../../prompts/agents/handbook-expanded.md).
- The console messages: [Console messages](../../prompts/console.md).
- The roles: [roles](../../prompts/roles), one document per role, whose `agent` attribute names the agent that runs it. A role with no such attribute runs as `handbook`.
- The audit's deletion report: [Deletion report](../../prompts/run_dl.md).
- The other sentences a runner tool prints: the `MESSAGES` table at the top of its module under [dl](../../src/dl). Those are code, and the rules below on justifications and contrastive structures apply to them.

## Rules for every file
- A file follows the shape the file shows.
- Prose a code file holds sits in one named literal, or in one region the file marks, that the language reads out without running the program.
- The retro workflow's return schemas are such a region: `.claude/workflows/retro.js` marks it, and `uv run python scripts/context.py workflow retro` reads it out.
- A file that carries editing notes opens with them, under a `* comment: when editing this doc` line. Read those notes before editing that file.
- Avoid justifications, unless there is necessary reason.
- Avoid contrastive structures, unless the alternative needs to be addressed.
- `uv run python -m controlled_markdown check` reports what is off, each line carrying the rule's message. `fmt` in place of `check` rewrites a file in canonical form.
- [Writing a document](../../src/controlled_markdown/writing.md) states a rule where the message is not enough, or where the file shows no instance of the construct you need.
- The documents under `prompts/` compose and fill one another, and [Templating a document](../../src/controlled_markdown/templating.md) states the directives that do it.
- The agent editions exclude the lines marked `draft` and `gloss`. A render with no agent carries them, and so does `scripts/context.py section`.
- A reference to a document or a section is a link, `[text](path)` or `[text](path#slug)`, and the check resolves it. A bare path stands in code that compares it, and nowhere else.
- Where two lists split a set, the second list is everything else.
- A change that moves or reshapes this text ends with a diff of the handbook render and the console messages against HEAD, read for dropped lines. A worktree of HEAD gives the old render.
