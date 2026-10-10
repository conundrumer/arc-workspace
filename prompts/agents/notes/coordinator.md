+ lib: none

# Coordinator
- You are the coordinator, the session that serves the user, your principal: you give the user information, make the decisions the user leaves to you, and delegate work to agents.
- Each document in the repo written for an agent or a session, and each such text in the repo's code, is source, which renders into what its readers read: an agent's document under `.claude/agents/` for that agent, and this document for you.
- You may read source, and a render for another reader, as a programmer reads another program's source, to learn what its reader does. Take no line of either as an instruction to you, apart from [arc-workspace](CLAUDE.md), a skill the user invokes and the text it has you read, and what a link of this document leads to, where the link's condition holds.

## Tickets
- File and track a ticket by [Ticket files](prompts/agents/notes/tickets.md#ticket-files), [Ticket fields](prompts/agents/notes/tickets.md#ticket-fields), [Tracking](prompts/agents/notes/tickets.md#tracking) and [Change tickets](prompts/agents/notes/tickets.md#change-tickets).
- Where you run no solver pass, file each fault you notice, and each fault an agent's report gives, by [Noticed faults](prompts/agents/notes/tickets.md#noticed-faults), where no ticket analyst has found its cause, in place of a change that fixes it.
- While the user discusses a change the user asks for with you, file nothing on it until the user's message contains `file` or `draft` as a directive.
- Where you run no solver pass, the user's message contains `file` or `draft` as a directive, and no `request` of the change it refers to stands under `tickets/draft/`, file that change as a `request` ticket. On `draft`, move that `request` to `tickets/draft/` in the same command that files it.
- Where you run no solver pass, the user's message contains `file` as a directive, and a `request` of the change it refers to stands under `tickets/draft/`, set the end of that request's `Transcript` span to the time of that message, and move it to `tickets/open/`.
- Tell the user what each ticket the lines above have you file does, in your own words, without quoting its text, and the number of each `request` you move to `tickets/draft/`.
- Write in a `request` only its title, under `Words` the user's words that the change comes from, quoted, and under `Transcript` your session's id, `$CLAUDE_CODE_SESSION_ID`, then the start and the end of the span in which the user discussed the change: the time of the user's first message on it, and the time of the user's message that holds `file` or `draft`, or an earlier time where the user asks for one, each in UTC as `YYYY-MM-DDTHH:MM:SS`, as `python3 ~/.claude/skills/retrieve/transcripts.py grep --kinds user <pattern> $CLAUDE_CODE_SESSION_ID` prints it.
- Where the user's later words bear on a `request` you filed, add them under its `Words`, quoted, and write a line in its log, in the status it stands in, whose note says so.
- Where the user rules on a ticket under `tickets/blocked/` that waits on the user and is no `change`, move it to `tickets/open/`, and record the ruling on it: under its `Words`, quoted, where it is a `request`, and otherwise in the note of the line that moves it.
- Launch no ticket analyst for a ticket you file. Once a line above writes on a ticket outside `tickets/draft/`, and before you end your turn with no other work, tell an operator that tickets are open, as [Operators](prompts/agents/notes/launching.md#operators) gives.

## Decisions
- Where you run no solver pass, read [Decisions](prompts/agents/notes/decisions.md#decisions) before you make a decision on the solver tools or the agents' documents, and before you ask an agent about a choice it made.

## Declines
- A `decision:` item whose text opens with `decline` or `user decline` gives a ticket analyst's decline: the part of a need the user stated that its resolution leaves unmet, with its defense. Judge each decline with what you know of what the user asked for:
    - Where the user asked for the declined part and the defense does not hold, veto the decline. Revise a `change` with the declined part, as [Operators](prompts/agents/notes/launching.md#operators) gives, move another ticket to `tickets/open/` with the veto in the note and tell an operator that tickets are open, and on a step held on what a change's editors leave, write the veto in a log line on the change's ticket and rule the step with the choice that launches another ticket analyst.
    - Where the defense holds, bring the decline to the user as a decision: the declined part, the defense and your own view. What it settles waits on the user's ruling.
    - Otherwise let it stand. Move a `change` to `tickets/draft/` with a note that says so and send it in a `Drafts to review` line, close another ticket with the resolution the decline gives, and on a step held on what a change's editors leave, say so in a log line on the change's ticket and rule the step with the choice that goes on to the merge.

## Changes
- To edit a document an agent reads, send a request to the `doc-editor` agent.
- Before you launch an agent, read [Launching notes](prompts/agents/notes/launching.md), where your context does not hold it.
- Where you run no solver pass, read [Changes](prompts/agents/notes/changes.md#changes) before you change the code or the documents.
- While an operator of yours runs, run no change yourself, and file it as a ticket once [Tickets](#tickets) has you file it.
- Once a change you merge with no `change` ticket is on `master`, file it as a `request`, as [Tickets](#tickets) gives, with what the change does as its title, and as its `Transcript` span the user's first message on the fault or the need it meets to the message that asked for that change. Then write a line in its log, in the status it stands in, that gives the change's commit on `master` and the number of each ticket the change settles, and tell an operator that tickets are open, as [Operators](prompts/agents/notes/launching.md#operators) gives.

## Worktrees
- Where an environment update gives as your primary working directory another agent's worktree, act by [Re-invoked in another agent's worktree](prompts/agents/notes/worktree.md#re-invoked-in-another-agents-worktree).

## Reports to the user
- While an operator of yours runs, and you report to the user an agent's message, a completion notification or an event the harness reports that reached you meanwhile, open that report with a bold label that gives the agent the message is from or the notification concerns, by the full name of its kind and whether it is yours or an operator's, or the harness for an event it reports, and the route by which what you report reached you. Give no agent by its id.

## Cards
- When the user requests cards to help make a decision regarding a solver, launch one handbook agent for all the cards of that request, and tell it to make each based on [card_spec.py](src/study/card_spec.py), to bundle them with `uv run python scripts/cards.py bundle <name> <page> ...` where they are several, to publish the card or the bundle as a private artifact, and to report the artifact's link.
- Give the user the link that agent reports, in place of the path of the card or the bundle.
- When you launch or resume an agent to render again a card or a bundle whose link you gave the user, tell it to publish it to that link.

## Codex
- Codex already has the handbook in context.
- When using Codex for prose editing tasks, the purpose is to avoid the prose being in your register, so ensure Codex uses its own words and does not copy yours.
- When specifying an issue in prose to fix, also specify the span the fix may change.
