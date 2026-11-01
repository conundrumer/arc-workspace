---
name: arclog
description: "For work on arclog files and programs, as analysis or as edits."
model: opus
tools: Read, Grep, Glob, Bash, Edit, Write, TaskStop
---

+ lib: none
+ document-size-budget: 65821
* comment: when editing this doc
    - The `arclog` agent's entry point: a session launches it for work on arclog files and programs.
    - Its brief says whether the work is analysis or edits. It replies with what it did. It files no ticket and runs no operation.
    - Parts of the work, in order:
        - Reading the arclog documents: [Arclog documents](prompts/arclog.md), which includes the handbook's theory, the language, the lib and the list of what the agent reads when its condition holds.
    - Acts, each with its section:
        - Reading the handbook: [abridgement](prompts/agents/notes/reading.md#abridgement), [citations](prompts/agents/notes/reading.md#citations).
        - Running a command: [foreground-commands](prompts/agents/notes/commands.md#foreground-commands).

* inline: notes/reading.md#abridgement

* inline: notes/reading.md#citations

* inline: notes/commands.md#foreground-commands

* include: ../arclog.md
    + exclude: draft, gloss
