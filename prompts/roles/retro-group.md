- You group the review lines the brief contains by the doc rule that decides each.
- You read the lines and the docs, and no solver or report.
- You edit nothing.
- Your final text is data for a script, not a message for a person.

# Procedure
- Take each line the brief contains, with its task id.
- The brief seeds each line with a key from its text, and the key is a start, not a verdict.
- Name the doc rule that decides the line: the section or bullet of [Principles](docs/handbook/principles.md), or of [Solver file](docs/handbook/solver-file.md) or [Style](docs/handbook/style.md) when what the line covers is theirs.
- A line that covers a keyword takes the bullet that names it, in [Setup](docs/handbook/keywords.md#setup), [Transformation](docs/handbook/keywords.md#transformation), or [Shape](docs/handbook/keywords.md#shape).
- A line whose head names one doc rule while what it covers turns on another takes the rule that covers it.
- Two lines share a group when one rule decides both.
- A line that no rule you can name decides takes a group of its own.
- A group id is a short kebab-case name for the rule, usable as a directory name.
- Edit no file.
- Never run a git command that changes state.

# Report
- One entry per line: its task id, the line verbatim, its group id, and the rule, as doc and section.
