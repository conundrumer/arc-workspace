# Decline notes
- The statements on a ticket analyst's decline, that the coordinator reads when a decline reaches it.

## Declines
- A `decision:` item whose text opens with `decline` or `user decline` gives a ticket analyst's decline: the part of a need the user stated that its resolution leaves unmet, with its defense. Judge each decline with what you know of what the user asked for:
    - Where the user asked for the declined part and the defense does not hold, veto the decline. Revise a `change` with the declined part, as [Operators](prompts/agents/notes/launching.md#operators) gives, move another ticket to `tickets/open/` with the veto in the note and tell an operator that tickets are open, and on a step held on what a change's editors leave, write the veto in a log line on the change's ticket and rule the step with the choice that launches another ticket analyst.
    - Where the defense holds, bring the decline to the user as a decision: the declined part, the defense and your own view. What it settles waits on the user's ruling.
    - Otherwise let it stand. Move a `change` to `tickets/draft/` with a note that says so and send it in a `Drafts to review` line, close another ticket with the resolution the decline gives, and on a step held on what a change's editors leave, say so in a log line on the change's ticket and rule the step with the choice that goes on to the merge.
