+ budget: 2327
* comment: when editing this doc
    - Readers: each reader of [Editing the agent-facing documents](docs/handbook/editing.md), by the link of its [Where each text is](docs/handbook/editing.md#where-each-text-is), before it edits a text of the solver console, of the roles or of the workflows, or reviews a change that one of their readers reads.
    - Acts, each with its section:
        - Finding a deprecated text and its reader's context: [Deprecated texts](#deprecated-texts).

# Deprecated text notes
- The statements on the deprecated agent-facing texts that [Editing the agent-facing documents](docs/handbook/editing.md) links.

## Deprecated texts
- The console messages: [Console messages](prompts/console.md).
    - A worker's context: the appendix, the message the stage opens with, then each message a condition sends, under that condition: `context console <stage>`.
    - A survey session's context: the appendix, its role, then the `survey` message: `context survey`.
    - The system reminders the console prefixes to a message, which the `context` output leaves out: [workers.py](tools/console/solver_console/workers.py).
    - The committer's brief: `commit_brief` in [config.py](tools/console/solver_console/config.py).
- The roles: [roles](prompts/roles), one document per role. A role's `agent` attribute says which agent runs it, and a role with none runs as `handbook`.
    - Its context: `context role <name>`.
    - A role's brief comes from the script or the session that spawns it, and the `context role` output gives that file's path.
- What the callout-rate classifier reads: [Classification rubric](tools/console/recal/RUBRIC.md).
- The classifier: [Callout rate recalibration](tools/console/recal/README.md).
- The workflow briefs and the schema descriptions: the scripts under [workflows](.claude/workflows).
    - A workflow agent that runs a role reads `context workflow <name>`, and an agent with no role reads its brief alone.
    - `readerFor` in [retro.js](.claude/workflows/retro.js) gives the reader of each document a retro fix touches.
