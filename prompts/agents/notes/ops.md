+ lib: none
+ document-size-budget: 11000
* comment: when editing this doc
    - The coordinator, the session the user talks with, reads this document whole, by the link of the [Ops](prompts/agents/notes/coordinator.md#ops) section of its document, at the trigger that section gives: it serves the coordinator's work on routes, tickets, decisions, changes, cards and Codex, and each section gives the trigger at which the coordinator loads the notes for that part.
    - Parts of the work, in order, each with what it loads:
        - Taking a user's message for work: [Routes](prompts/agents/notes/requests.md#routes).
        - Running a change itself, on `direct` and `hotfix`, by a link of Routes: [Running a change](prompts/agents/notes/requests.md#running-a-change).
        - Filing and tracking tickets: [Tickets](prompts/agents/notes/requests.md#tickets).
        - Acting on the user's later words on a `request` or a ruling on a blocked ticket: [The user's words on a ticket](prompts/agents/notes/requests.md#the-users-words-on-a-ticket).
        - Waiting on a ticket's close: [Waiting on a ticket](prompts/agents/notes/requests.md#waiting-on-a-ticket).
        - Making decisions and giving their defaults: [Decisions](prompts/agents/notes/decisions.md#decisions), [Defaults](prompts/agents/notes/decisions.md#defaults).
        - Acting on a decline: [Declines](prompts/agents/notes/declines.md#declines).
        - Launching an agent, launching passes, sending operators lines, batching feedback, and making and merging changes: [Launching](prompts/agents/notes/launching.md#launching), [Passes on a task](prompts/agents/notes/launching.md#passes-on-a-task), [Operators](prompts/agents/notes/launching.md#operators), [While the user gives feedback](prompts/agents/notes/launching.md#while-the-user-gives-feedback), [Making a change](prompts/agents/notes/changes.md#making-a-change), [Merging a change](prompts/agents/notes/changes.md#merging-a-change), [A denied merge](prompts/agents/notes/changes.md#a-denied-merge).
        - Reporting to the user and bringing decisions: [Reports to the user](#reports-to-the-user), with [The user's part](prompts/agents/notes/decisions.md#the-users-part).
        - Cards and Codex: [Cards](prompts/agents/notes/cards.md#cards), [Codex](#codex).
    - Acts whose rules this document states, each with its section: reporting to the user while operators run and decisions wait, [Reports to the user](#reports-to-the-user); giving Codex work, watching it and steering it, [Codex](#codex).

# Ops
- The statements on the coordinator's operations, that the coordinator reads at the trigger of its Ops section.

## Routes
- Before you act on a user's message that asks for work or gives a route directive, read [Routes](prompts/agents/notes/requests.md#routes).

## Tickets
- `tickets/` is the ticket tracker, and [Ticket notes](prompts/agents/notes/tickets.md) states its conventions.
- Read [Tickets](prompts/agents/notes/requests.md#tickets) before you file, append to, move or close a ticket, and, where you run no solver pass, when you notice a fault or an agent's report gives one.
- When the user's words bear on a `request` you filed or rule on a ticket under `tickets/blocked/`, read [The user's words on a ticket](prompts/agents/notes/requests.md#the-users-words-on-a-ticket).
- Before you wait for a ticket to close, read [Waiting on a ticket](prompts/agents/notes/requests.md#waiting-on-a-ticket).

## Decisions
- Where you run no solver pass, read [Decisions](prompts/agents/notes/decisions.md#decisions) before you make a decision on the solver tools or the agents' documents, and before you ask an agent about a choice it made.
- Read [Defaults](prompts/agents/notes/decisions.md#defaults) before you end a turn with a decision, when your `budget` timer completes, and at the user's next message after it starts.

## Declines
- When a `decision:` item whose text opens with `decline` or `user decline` reaches you, read [Declines](prompts/agents/notes/declines.md#declines) before you act on it.

## Launching
- Before you launch an agent by a call that no command printed to you, read [Launching](prompts/agents/notes/launching.md#launching), where your context does not hold it.

## Changes
- Before you launch a pass on a task, read [Passes on a task](prompts/agents/notes/launching.md#passes-on-a-task).
- Before you send an operator a line, or move or revise a `change` ticket, and when an operator's message reaches you, the user rules on a `change` ticket, or a `change` of your session comes to stand untaken, read [Operators](prompts/agents/notes/launching.md#operators).
- While the user gives feedback, read [While the user gives feedback](prompts/agents/notes/launching.md#while-the-user-gives-feedback).
- Read [Making a change](prompts/agents/notes/changes.md#making-a-change) before you change the code or the documents, [Merging a change](prompts/agents/notes/changes.md#merging-a-change) before you merge a change, and [A denied merge](prompts/agents/notes/changes.md#a-denied-merge) where a merge call of a change is denied, yours or one an agent you launched gives.

## Cards
- Before you launch or resume an agent on cards, read [Cards](prompts/agents/notes/cards.md#cards).

## Reports to the user
- While an operator launcher of yours runs, and you report to the user an agent's message, a completion notification or a harness event that reached you meanwhile, open that report with a bold label that gives the agent the message is from or the notification concerns, by the full name of its kind and whether it is yours or runs under your operator launcher, or else the harness, and the route by which what you report reached you. Give no agent by its id.
- While the user is away, as [Defaults](prompts/agents/notes/decisions.md#defaults) gives it, open each decision you bring the user, as [The user's part](prompts/agents/notes/decisions.md#the-users-part) gives it, whose default cannot be undone, one you gave before the user went away included, with the bold label `**Blocked on you.**` alone, apart from any report you give in the same reply, and give each other decision and each question with no label.
    + xref: prompts/agents/notes/decisions.md#the-users-part, prompts/agents/notes/decisions.md#defaults
    * comment: The user's words, session b7409037-276d-495a-af65-14522921c7ad, 2026-10-23T19:33:05Z: "i'm already here. the intention of \"Blocked on you.\" is when you are acting autonomously and when i'm away ie not having a conversation with you".
    * comment: The user's words, session 129de8fc, 2026-10-14T21:21:44Z: "it needs to be clear that it's only for "decisions that hold up work while you may be away from the session"", and session 7fd429fb-e3be-4173-9b0e-df52f507d6a2, 2026-10-15T23:08:04Z: "bug", on the coordinator's account that the user "may be away" holds almost every time.
- End each reply that ends your turn with each decision you opened with that label, until the user rules on it, you apply its default or the user's next message comes, opened with it again: in full the first time, and after that as its ticket or the step it settles, its question, and one line per option, the default first, with its consequence. Give no decision twice in one reply.
    * comment: The coordinator of session 129de8fc, 2026-10-17, from 21:18:01Z to 21:27:21Z, read this line's former words "each such decision" as every decision it brings the user, and ended each reply with two questions it gave with no label, as ticket 9-925 records.
- Give each planned-load notice an operator sends at once, in one line, with the change's label, each run with its estimate, and `defer <number>`.
    * comment: The user's words, session 2384db39-7d21-4d8d-8dda-bfd52bd69360, 2026-10-23T12:22:15Z: "And I should be notified if there is planned high load. Let it continue". Change 11-3618.
- Name each ticket you give the user by its ticket label, as `uv run python scripts/file_ticket.py label <number> ...` prints it, also where a text that a tool or an agent sent you names it by its bare number.
    * comment: The user's words, session 2384db39, 2026-10-23T03:19:16Z: "also i get confused about ticket numbers", and 03:22:48Z: "1 but make it look like C11-3451. show examples first for every ticket kind". Change 11-3501.

## Codex
- Set Codex mode with `uv run python scripts/operate.py codex on` or `uv run python scripts/operate.py codex off`, then use the normal role launcher path; [operate_help.py](scripts/operate_help.py) gives which launches the mode routes to Codex.
    + xref: scripts/operate_actions.py:set_codex, scripts/operate_help.py:USAGE
- Have the role's launcher follow [Codex launcher](prompts/agents/codex-launcher.md#codex-launcher) for the enrolled root's execution, waiting, resuming and exec fallback timing.
- While Codex works, read its status and recent activity with `uv run python scripts/codex_agent.py show <scratch>`, using the absolute scratch path of its launch on each control call, and check that activity against its brief and instructions. Where `show` gives an owning ticket and operator, send corrections to an operator of the session for a root resume after the root turn and its descendants end; use `uv run python scripts/codex_agent.py interrupt <scratch>` for tree-aware interruption. For un-enrolled work, send corrections yourself with `uv run python scripts/codex_agent.py steer <scratch> '<message>'`, and stop its turn with `uv run python scripts/codex_agent.py interrupt <scratch>`.
    + xref: scripts/codex_agent.py:control
    * comment: Change 11-2481, Intent, quoting request 11-2448: user 2026-10-20T17:51:48Z, "add coordinator instructions for codex", approved by "go" at 17:53:49Z; its Design assigns the coordinator activity review and corrective steering.
    * comment: Change 11-2534, Design, assigns enrolled corrections to an operator of the session after the root turn and its descendants end, and interruption to the ticket boundary; its Grounds cite reviewer a27b140a8fbe4d278's observed active-control bypass at 2026-10-20T22:03:25Z.
- When you give Codex an issue in prose to fix, give the span the fix may change.
