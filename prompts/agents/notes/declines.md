+ budget: 1819
* comment: when editing this doc
    - Reader: the coordinator, by a link, when a decline reaches it.
    - Acts: judging and acting on a decline, [Declines](#declines).

# Decline notes
- The statements on the decline of a ticket analyst or a decision analyst, that the coordinator reads when a decline reaches it.

## Declines
- A decline gives the part of a need the user stated that the resolution of a ticket analyst or a decision analyst leaves unmet, with its defense.
- Judge each decline with what you know of what the user asked for:
    - Where the user asked for the declined part and the defense does not hold, veto the decline.
    - Where the defense holds, bring the decline to the user as a decision: the declined part, the defense and your own view. What it settles waits on the user's ruling.
    - Otherwise let it stand.
- Apply a veto, or a decline you let stand, by what the decline is on:
    - On a `change`, for a veto, revise it with the declined part, as [Operators](prompts/agents/notes/launching.md#operators) gives. For a decline that stands, move it to `tickets/draft/` with a note that says so and send it in an `Op drafts to review:` line.
        + xref: prompts/agents/notes/launching.md#operators, prompts/agents/notes/launching.md#an-operators-brief
    - On another ticket, for a veto, move it into a take's queue, as `uv run python scripts/file_ticket.py log --help` gives it, with the veto in the note and tell an operator that tickets are open. For a decline that stands, close it with the resolution the decline gives.
    - On a step held on what a change's editors leave, write the veto, or that the decline stands, in a log line on the change's ticket. Then rule the step with the choice that launches another decision analyst for a veto, and with the choice that goes on to the merge for a decline that stands.
