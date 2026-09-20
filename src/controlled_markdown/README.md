# Controlled Markdown

- Controlled Markdown is Markdown with one rule added: every line is one item of a nested list.
    - The source is valid Markdown, so it renders wherever Markdown does and reads as a document without the tooling.
- One line holds one statement, so a person or an agent cites, searches, diffs, and edits it on its own line.
    - A statement is one claim, one instruction, or one definition.
    - What would be a second sentence goes on its own line, under the first.
- Indentation is the only structure. A line takes its meaning from what it sits under, and a directive governs the lines under it and none beside it.
- The documents are text for people and for agents. A person reads the source and an agent reads the render, and both edit them.
    - The render shows the statements as nested lists under headings, and nothing else.
    - The source shows the same lists, with the attributes and the editor's notes beside them, which no render shows.
- A document explains the format in use. A reader infers the rules from a document that follows them.
    - Every marker is at work near the rule that states it.
    - No convention needs a table outside the document.
- The keywords are few and conventional, so a reader who knows templating conventions understands each directive from its name.
- Data stays scalar. An attribute is a name and a short value, and structured data stays in front matter.
    - A render fills text with values and builds no structure, so the format has no reordering and no loop.
- The documents are the data. What each reader gets is stated in a document, and the rendering code follows from it.
    - A render gives its reader the lines, never a pointer at a source file.
    - A section a render abridges names the command that prints it in full.
- A feature exists because a document needs it. The format is reconsidered when a need arrives.

## The documents

- Each document below states its own rules, and a reader takes the one its job needs.
- Each is written in the indicative mood, and each demonstrates a rule in a fenced example where a demo helps.
- `writing.md`: the lines and the markers, for anyone editing a document.
- `templating.md`: composing a document out of others and filling it with values, for anyone editing the prompts.
- `grammar.md`: the exact rules and the edge cases, for anyone maintaining the package.
