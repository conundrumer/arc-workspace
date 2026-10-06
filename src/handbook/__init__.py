"""The handbook's readers: the reference context a solver session reads,
the agent documents, and the generated files they read. `context` holds
the entry documents composed with the lib, the roles, the workflows, the
handbook's sections and the codex files; `agents` the agent documents and
the agents' definitions; `attributes` the reader of an entry document's
attribute that takes one of a closed set of forms; `contexts` what each
reader of the `context` command reads; `role_briefs` where a role's brief
comes from; `workflow_scripts` the roles a workflow script reaches, each
with its phase; and `generated` the writes of the generated files in the
checkout, the check that git ignores each, and the removal of stale ones.
`lib` holds the lib as its readers read it, rendered as documentation or as
an index, and `wrappers` the text of the module of the lib's component
wrappers.
`coordinator_document` renders the coordinator's document and gives it,
through the session-start hook, to the coordinator, the session the user
talks with. `readers` holds the readers the `context` command knows."""
