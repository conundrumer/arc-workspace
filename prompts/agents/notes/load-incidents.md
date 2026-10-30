+ document-size-budget: 2000
* comment: when editing this doc
    - Reader: the coordinator, by a link, when a load incident report or a ruling reaches it from the load watch session.
    - Acts: replying to a load incident report or a ruling and acting on it, [Load incidents](#load-incidents).

# Load incident notes
- The statements on replying to a load incident report or a ruling and acting on it, that the coordinator reads when one reaches it.

## Load incidents
- When a load incident report or a ruling reaches you from the load watch session, take each act it gives that you do not decline, then reply to its message with one line for each act it gives: `done: <act>`, `not done: <act>: <what stopped it>`, or `declined: <act>: <reasons>`. Give in a decline's reasons what you know that the report does not, such as the user's words in your session. Decline no act that a ruling upholds.
    * comment: The user's words, session 19071443, 2026-10-22T22:44:01Z: "the case includes a recommendation. not an order. its possible the coordinator has context like things i said in the session", and 22:53:16Z: "the router fwds it to the session (with a clear choice btwn accepting/declining)". The user's words, request 11-3628, session 2384db39, 2026-10-23T13:10:37Z: "“Accept” does nothing. We need something better. Something that communicates action was or was not taken or declined to take".
- Take the acts of a report as [Tickets](prompts/agents/notes/requests.md#tickets) gives for a fault an agent's report gives, and take each act a ruling upholds. Bring the user a decision a ruling gives as [The user's part](prompts/agents/notes/decisions.md#the-users-part) gives, and give the user each process the report gives as owned by no live session. Give the user each act you reply `not done`, with what stopped it and the number of the ticket on that cause, the one you filed or the open ticket that records it.
    + xref: prompts/agents/notes/requests.md#tickets
    * comment: The user's words, session 2384db39, 2026-10-18T18:12:52Z: "the point is to look at whats going on"; 18:17:50Z: "the problem with load is the agents should not need to be running intensive things regularly int he first palce"; 18:21:12Z: "coordinators are supposed to see loads as dysnfucntion not routine". The user's words, request 11-3628, session 2384db39, 2026-10-23T13:10:37Z: "The point of load incident messages is to result in action", and "latter two should result in escalation".
- Write each load note the report or the ruling gives that you do not decline, for a ticket behind a process of your session on that ticket, as a line of its log in the status it stands in, its note opening with `load:`, by `uv run python scripts/file_ticket.py log`. A refused log line makes that note `not done`.
    * comment: The user's words, session 19071443-e929-490f-bb8b-cca32c92ba6b, 2026-10-22T23:42:21Z: "we need to ensure it doesn't repeat. like another agent could make the same mistake. so the ticket itself needs to be updated so whoever else working on it won't fall for the same laod trap".
