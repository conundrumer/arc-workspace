+ document-size-budget: 1185
* comment: when editing this doc
    - The ticket reviewer receives this document from the step command as it enters a later round's review, once it has entered the review of the drafts of its brief that meet their Goal.
    - Acts, each with its section:
        - Limiting a later round's findings, and taking the draft's text at that round: [A later round](#a-later-round).

# A later round
- On a draft that an earlier round checked by [Checks](prompts/agents/ticket-reviewer/review.md#checks), make by those checks only a finding the last such round could not have made: one on text that changed since that round, one on a claim whose ground, in the tree or this session's state, changed since that round, or a finding of an earlier round that still stands.
- A draft's text at that round is in the transcript of the ticket reviewer whose agent id that round's log lines give, which `python3 ~/.claude/skills/retrieve/transcripts.py` reads by agent id. Where you cannot read that text, take the whole draft as changed since that round.
