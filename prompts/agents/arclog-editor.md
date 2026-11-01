---
name: arclog-editor
description: "For editing arclog files and lowering the bits of their programs."
model: opus
tools: Read, Grep, Glob, Bash, Edit, Write, TaskStop
---

+ lib: none
+ document-size-budget: 96400
* comment: when editing this doc
    - The `arclog-editor` agent's entry point: a session launches it for work on arclog files, and the clauses of a program may change.
    - Its brief gives its work, and it replies with what it did. It files no ticket and runs no operation.
    - Parts of the work, in order:
        - Reading the arclog documents: [Arclog documents](prompts/arclog.md), which includes the handbook's theory, the language, the lib and the list of what the agent reads when its condition holds.
    - Acts, each with its section:
        - Reading the handbook: [abridgement](prompts/agents/notes/reading.md#abridgement), [citations](prompts/agents/notes/reading.md#citations).
        - Running a command: [commands](prompts/agents/notes/commands.md#commands).

* inline: notes/reading.md#abridgement

* inline: notes/reading.md#citations

* inline: notes/commands.md#commands

* include: ../arclog.md
    + exclude: draft, gloss
