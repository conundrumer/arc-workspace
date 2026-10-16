+ budget: 1100
* comment: when editing this doc
    - The ticket reviewer loads this document from [Ticket reviewer](prompts/agents/ticket-reviewer.md#ticket-reviewer), in each round, before every other check on a draft.
    - Acts, each with its section:
        - Judging whether the change, as designed, meets the Goal of its request: [The Goal](#the-goal).

# The Goal
- Judge whether the change, merged as its Intent and its `Design` give it, meets the Goal of the request it serves, over every case that Goal covers. `uv run python scripts/spans.py brief <number>` prints that request's Goal and spans. For a change that serves no request, judge it against the Impact of each ticket it settles in place of a Goal.
- Where it does not, log one finding that gives the part of the Goal the design does not meet and a case it leaves out, and check that draft no further in this round.
- Where it does, go on to the rest of [Ticket reviewer](prompts/agents/ticket-reviewer.md#ticket-reviewer).
