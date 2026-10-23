+ lib: none
+ document-size-budget: 3200
* comment: when editing this doc
    - The load watch session reads this document whole, by the link of the skill [Load watch](.claude/skills/load-watch/SKILL.md), when the user invokes `/load-watch` on it.
    - Acts, each with its section:
        - Running the load monitor and responding to its exit: [Load watch](#load-watch).
        - Sending each owning session its part of a report, and settling a rejection: [Reports and rulings](#reports-and-rulings).

# Load watch
- This session is the load watch session. Do no work other than this document gives, and wait for no message of the user.
    * comment: The user's words, session 19071443, 2026-10-22T22:53:16Z: "a main session that's basically a router and listener. it runs the machine load script that, when tripped, it launches an investigator agent", and 23:00:48Z: "this should be a skill too so i can invoke it on a session to watch the load".
- Start `uv run python scripts/load_monitor.py` in the background.
    + xref: scripts/load_monitor.py:main
- When the monitor exits with an alert's path, start it again at once. Then launch nothing where each process of the alert is one that a report gave as justified at its load and that its owner accepted, a ruling upheld, or the report alone settled, as a part sent to no owner does. Otherwise launch a `load-incident-analyst` with the brief [A load incident analyst's brief](prompts/agents/notes/launching.md#a-load-incident-analysts-brief) gives.
- Where the monitor exits otherwise, give the user its output.
- Between incidents, end your turn: the harness re-invokes you at the monitor's exit and at each message.
- Give a brief in its section's form and launch the type whose description links it, as [Launching](prompts/agents/notes/launching.md#launching) gives.

## Reports and rulings
- Send each owning session whose part's recommendation gives it an act to take, such as a load note on a ticket, that part of the load incident report by SendMessage, at the row of that session in ListAgents, with the choice given as two reply forms: `accept` and `reject: <reasons>`. Send a session whose part gives it no act no message. Send the part on processes that no live session owns to the main session, the one `tickets/main` gives, for its coordinator to give the user.
    * comment: The user's words, session 19071443, 2026-10-23T00:27:16Z: "if there's no action for the owning sessions to take, don't send messages to them".
- On `reject: <reasons>`, launch a `decision-analyst` with the brief form of [A decision analyst's brief](prompts/agents/notes/launching.md#a-decision-analysts-brief) that gives a load incident report, and send the owning session its ruling, or the decision it brings the user. The ruling binds the owning session, and the user answers a decision in the owning session.
- An incident is open until each owner it sent a part accepts, or that owner's ruling reaches it.
