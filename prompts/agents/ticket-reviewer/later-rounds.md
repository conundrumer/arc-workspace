+ budget: 1200
* comment: when editing this doc
    - The ticket reviewer loads this document from [Ticket reviewer](prompts/agents/ticket-reviewer.md#ticket-reviewer), when an earlier round reviewed the draft.
    - Acts, each with its section:
        - Limiting a later round's findings, and taking the draft's text at the earlier round: [A later round](#a-later-round).

# A later round
- In a round after the first on a draft, make only a finding the earlier round could not have made: one on text that changed since that round, one on a claim whose ground, in the tree or this session's state, changed since that round, or a finding of an earlier round that still stands.
    - Take the draft's text at the earlier round from the transcript of the ticket reviewer whose agent id that round's log lines give, which `python3 ~/.claude/skills/retrieve/transcripts.py` reads by agent id. Where you cannot read that text, take the whole draft as changed since that round.
