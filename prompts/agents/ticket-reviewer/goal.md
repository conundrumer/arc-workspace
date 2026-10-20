+ document-size-budget: 1100
* comment: when editing this doc
    - The ticket reviewer reads this document by the link of the item `Judge each draft by its Goal` of its [checklist](prompts/agents/ticket-reviewer/checklist.md), at the start of its review.
    - Acts, each with its section:
        - Judging a draft against its Goal: [The Goal](#the-goal).

# The Goal
- Judge whether the change, merged as its Intent and its `Design` give it, meets the Goal of the request it serves, over every case that Goal covers, less each part whose decline a log line of the coordinator on the draft lets stand. `uv run python scripts/spans.py brief <number>` prints that request's Goal and spans. For a change that serves no request, its Goal is the Impact of each ticket it settles.
    + xref: scripts/spans.py:brief
    * comment: Ticket reviewer `aa7eb6bb4a3bb8e45` held draft 11-1751 on a Goal finding whose decline the coordinator's log line of 2026-10-19T00:59:01Z let stand, and a decision analyst ran to rule it (ticket 11-1819).
- Where it does not, log one finding that gives the part of the Goal the design does not meet and a case it leaves out, and check that draft no further in this round.
