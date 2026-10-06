"""The handbook's readers: the reference context a solver session reads,
the agent documents, and the generated files they read. `lib` holds the
lib as its readers read it, rendered as documentation or as an index, and
`wrappers` the text of the module of the lib's component wrappers.
`coordinator_document` renders the coordinator's document and gives it,
through the session-start hook, to the coordinator, the session the user
talks with. `readers` holds the readers the `context` command knows."""
