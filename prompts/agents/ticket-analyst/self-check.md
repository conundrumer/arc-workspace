+ budget: 1200
* comment: when editing this doc
    - The ticket analyst loads this document from [Jobs](prompts/agents/ticket-analyst.md#jobs), once it has written the text of a draft `change`, before it files the draft or logs its revision.
    - Acts, each with its section:
        - Checking the draft by the ticket reviewer's checks: [Checking a draft](#checking-a-draft).

# Checking a draft
- Check the draft by each check of [Checks](prompts/agents/ticket-reviewer/review.md#checks) on these, and fix each fault a check shows, before you file the draft or log its revision:
    - `depends-on`.
    - The order of instructions that edit the same part of a file.
    - The outcome of [Process notes](prompts/agents/notes/process.md) in the Motivation.
    - The `Design` of a `change` to code or to the agent-facing documents, with the Scope covering each file it gives.
    - The readers a rule's stated scope covers.
    - The Intent items as requirements, and their traces.
    - The states a `Design` lists, with each part's cost and gain.
