+ document-size-budget: 2000
* comment: when editing this doc
    - Reader: the coordinator, by a link, when a load incident report or a ruling reaches it from the load watch session.
    - Acts: replying to a load incident report or a ruling and acting on it, [Load incidents](#load-incidents).

# Load incident notes
- The statements on replying to a load incident report or a ruling and acting on it, that the coordinator reads when one reaches it.

## Load incidents
- When a load incident report or a ruling reaches you from the load watch session, reply to its message with `accept` or `reject: <reasons>`, and give in the reasons what you know that the report does not, such as the user's words in your session.
    * comment: The user's words, session 19071443, 2026-10-22T22:44:01Z: "the case includes a recommendation. not an order. its possible the coordinator has context like things i said in the session", and 22:53:16Z: "the router fwds it to the session (with a clear choice btwn accepting/declining)".
- On `accept`, act on the recommendation as on a fault an agent's report gives. Act on a ruling. Bring the user a decision it gives as [The user's part](prompts/agents/notes/decisions.md#the-users-part) gives, and give the user each process the report gives as owned by no live session.
    * comment: The user's words, session 2384db39, 2026-10-18T18:12:52Z: "the point is to look at whats going on"; 18:17:50Z: "the problem with load is the agents should not need to be running intensive things regularly int he first palce"; 18:21:12Z: "coordinators are supposed to see loads as dysnfucntion not routine".
- On `accept`, and on a ruling, write each load note the report or the ruling gives for a ticket behind a process of your session on that ticket, as a line of its log in the status it stands in, its note opening with `load:`, by `uv run python scripts/file_ticket.py log`.
    * comment: The user's words, session 19071443-e929-490f-bb8b-cca32c92ba6b, 2026-10-22T23:42:21Z: "we need to ensure it doesn't repeat. like another agent could make the same mistake. so the ticket itself needs to be updated so whoever else working on it won't fall for the same laod trap".
