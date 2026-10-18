+ budget: 1811
* comment: when editing this doc
    - The ticket reviewer's checklist: `uv run python scripts/step.py ticket-reviewer` prints its items one at a time, by [Ticket reviewer](prompts/agents/ticket-reviewer.md#ticket-reviewer), each as the ticket reviewer reaches its step.
    - Acts, each with its section: each step of its work, under the item of that step.

# Judge each draft by its Goal
- Judge each draft of your brief by [The Goal](prompts/agents/ticket-reviewer/goal.md#the-goal).

# Review the drafts that meet their Goal
- This part applies where a draft of your brief meets its Goal: [Reviewing a draft](prompts/agents/ticket-reviewer/review.md).

## Limit a later round's findings
- This part applies where an earlier round checked such a draft by [Checks](prompts/agents/ticket-reviewer/review.md#checks): [A later round](prompts/agents/ticket-reviewer/later-rounds.md).

### Read each draft's text at that round
- Read the text that each draft an earlier round checked by Checks had at the last such round, as [A later round](prompts/agents/ticket-reviewer/later-rounds.md#a-later-round) gives.
    + xref: prompts/agents/ticket-reviewer/later-rounds.md#a-later-round

## Review each draft
- Review each draft that meets its Goal, as [Reviewing a draft](prompts/agents/ticket-reviewer/review.md#reviewing-a-draft) gives.
    + xref: prompts/agents/ticket-reviewer/review.md#reviewing-a-draft

# Leave or move each draft
- Leave each draft of your brief with a finding or a suggestion under `tickets/draft/`, and move each other draft of your brief to `tickets/open/` with `uv run python scripts/file_ticket.py log`, in the form its `--help` gives.
    + xref: scripts/file_ticket.py:SUBCOMMANDS

# Reply
- Give your final reply, as [Reply](prompts/agents/ticket-reviewer/reply.md#reply) gives.
    + xref: prompts/agents/ticket-reviewer/reply.md#reply
