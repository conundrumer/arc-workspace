+ budget: 8885
* comment: when editing this doc
    - The coordinator loads each section by a link: Routes before it acts on a user's message that asks for work, Running a change from the `direct` and `hotfix` lines of Routes, and Tickets, The user's words on a ticket and Waiting on a ticket at the triggers its document gives.
    - Acts, each with its section:
        - Routing a user's request for work: [Routes](#routes).
        - Taking, running and closing out a change the coordinator runs itself: [Running a change](#running-a-change).
        - Filing, tracking and closing the coordinator's tickets: [Tickets](#tickets).
        - Acting on the user's later words on a `request` and rulings on a blocked ticket: [The user's words on a ticket](#the-users-words-on-a-ticket).
        - Waiting on a ticket's close: [Waiting on a ticket](#waiting-on-a-ticket).

# Request notes
- The statements on the user's requests for work and on the tickets the coordinator files and tracks, that the coordinator reads at the triggers its document gives.

## Routes
- A user's message may open or end with a route directive: `direct`, `send`, `hotfix`, `expedite <number>`, `file`, `draft`, `scratch`, or `re <number>`, a follow-up on that `request`.
- Where a user's message that asks for work gives no route directive, infer its route, the `request` a follow-up concerns, and the span.
- On a route other than `scratch`, write, read back each write and each route you infer, then act: in the same turn on a route the user states, and on an inferred one at the user's next message, unless that message changes or cancels it.
    - To write is to run the command of `uv run python scripts/spans.py` that writes the route's `request` or brief. To act is to launch an agent with that brief, make or merge the change, send an operator an `Expedite:` line, or tell an operator that tickets are open.
        - The goal you give that command is the point of the work, the outcome the user wants, from the user's words, with no means you proposed and no elaboration.
    - Read back right after the write: give the route, the goal word for word as the command prints it where you ran one, and the work in your own words.
        - On an inferred route, open the readback with `**Inferred route: <route>.**`, and end it with the act the user's next message sets off, as `Once you reply, I <act>.`, or, where it sets off none, with a sentence that says so. Give it as no decision.
            * comment: Ticket 6-1167: the coordinator gave a readback again as a labelled decision with a default.
- `scratch` is work after which nothing under version control has changed, nothing has left the session, and nothing later depends on it. Do it with no readback, no ticket and no brief. Where that work would change a tracked file or send something out of the session, read back a route before that step.
- `direct`: file the change's `request`, write its brief, and carry the change as [Running a change](#running-a-change) gives.
- `send`: file the `request` and, in that turn, tell an operator that tickets are open where an operator launcher of yours runs, and otherwise launch a ticket analyst on it, with its transcript brief, and tell an operator so once the analyst replies.
- `hotfix`: file the change's `request`, write its brief, and, as [Running a change](#running-a-change) gives, launch at once on a worktree the editors it needs, each with that brief, and merge the change.
- `expedite <number>`: write nothing, send an operator `Expedite: <number>`, and tell the user the tickets outside `tickets/closed/` that a chain of links, as [Change tickets](prompts/agents/notes/tickets.md#change-tickets) gives a link, reaches from it.
- Run a change yourself only on `direct` and `hotfix`.

## Running a change
- Before you act, take each ticket the change would settle that waits on no `change`.
- Where a ticket the change would settle waits on a `change` or its take is refused, do not act: move each ticket you took to `tickets/open/` and the `request` to wait on that `change`, or else to `tickets/open/`.
- Carry and merge the change as [Changes](prompts/agents/notes/coordinator.md#changes) gives.
- Once a change you run is on `master`, write a line in its `request`'s log that gives its commit and the number of each ticket it settles, move the `request` and each ticket you took that is no `change` to `tickets/open/`, and leave held each `change` you took.

## Tickets
- File and track a ticket by [Ticket files](prompts/agents/notes/tickets.md#ticket-files), [Ticket fields](prompts/agents/notes/tickets.md#ticket-fields), [Tracking](prompts/agents/notes/tickets.md#tracking) and [Change tickets](prompts/agents/notes/tickets.md#change-tickets).
- Where you run no solver pass, file each fault you notice, and each fault an agent's report gives, by [Noticed faults](prompts/agents/notes/tickets.md#noticed-faults), where no ticket analyst has found its cause, in place of a change that fixes it.
- Where you run no solver pass, the route is `file`, `draft` or `send`, and no `request` of the change stands under `tickets/draft/`, file the change as a `request` with `uv run python scripts/spans.py file`.
- Where you run no solver pass and a `request` of the change stands under `tickets/draft/`, file no other `request` of the change. Once the user states `file`, `send`, `direct` or `hotfix`, or sends the next message after your readback of an inferred route other than `draft`, and that message does not change or cancel it, append to that `request` the span from the message after its last span to that message, with `uv run python scripts/spans.py append --route <route>` and that route.
- Tell the user what each ticket a line of this document has you file does, in your own words, without quoting its text, and the number of each `request` you move to `tickets/draft/`.
- A `request`'s first span runs from the user's first message on the change to the user's message that gives its route, or on an inferred route to the user's last one on it, or to an earlier message where the user asks for one.
- Write each line under `Grounds` of a `request` or of a brief as one addition of yours to what the spans give, with its source: a line of a file quoted with its path, a command with its output, or a ticket's log line. Write no other line there.
- Launch a ticket analyst on a ticket you file only where a line of your documents has you. Once a line of this document writes on a ticket outside `tickets/draft/` that you neither hold, filed on `send`, nor launch a ticket analyst with, and before you end your turn with no other work, tell an operator that tickets are open.

## The user's words on a ticket
- Where the user's later words bear on a `request` you filed, append their span to it with `uv run python scripts/spans.py append`, with the new goal where those words change the goal or state one. Send that span to each agent that holds the `request` or the `change` it waits on, and move the `request` to `tickets/open/` where it waits on a `change` that has not merged.
    - Where the `change` of that `request` has merged, file those words as a new `request` in place of the append, with a line under `Grounds` that gives the earlier one, and where those words withdraw the earlier `request`'s need, close it `wontfix` with the new `request`'s number.
- Where the user rules on a ticket under `tickets/blocked/` that waits on the user and is no `change`, move it to `tickets/open/`, and record the ruling on it: as a span where it is a `request`, and otherwise in the note of the line that moves it.

## Waiting on a ticket
- To learn when a ticket you wait on closes, run `uv run python scripts/file_ticket.py await-close <number> ...` in the background: its completion notification gives how the ticket closed.
    * comment: The user's words, session 7fd429fb-e3be-4173-9b0e-df52f507d6a2, 2026-10-13T02:21:38Z: "File ticket for ability to be notified on ticket close".
