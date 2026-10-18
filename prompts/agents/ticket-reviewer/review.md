+ budget: 9894
* comment: when editing this doc
    - The ticket reviewer receives this document from the step command as it enters the review of its drafts, once it has judged each draft of its brief by its Goal.
    - Acts, each with its section:
        - Reviewing a draft that meets the Goal, and writing suggestions: [Reviewing a draft](#reviewing-a-draft).
        - Checking a draft as an execution plan: [Checks](#checks).

# Reviewing a draft
- In a draft's review, check the whole draft against the tree and this session's state as they are now, by [Checks](#checks).
    * comment: With "Review each draft" in its context and a brief that gave the revised parts, ticket reviewer a031cd2826cb3df6e checked mainly those parts of draft 2-525 and moved it to `tickets/open/` while three findings stood on lines of the draft as first filed: the Intent of ticket 2-530.
- Report nothing on a draft's wording where each agent that executes the draft, each editor its `editors` field gives and the `general-purpose` agent the operator's command launches on its `after-merge` steps, would act on the draft the same way under other words.
- Where the draft changes or relies on what the operator's command does, read the operator's procedures in the docstrings of [operate.py](scripts/operate.py) and of the modules under [operations](src/operations), which the docstring of [__init__.py](src/operations/__init__.py) indexes, and its loop and its use of overrides with `uv run python scripts/context.py context agent operator`. Read the documents of each agent that executes the draft, and of each agent the draft has the operator's command launch or message, with `uv run python scripts/context.py context agent <name>`.
- Take the state from `uv run python scripts/profile_runs.py --running $CLAUDE_CODE_SESSION_ID`, `git log master`, the tickets under `tickets/`, and the operators' transcripts, which `python3 ~/.claude/skills/retrieve/transcripts.py --help` says how to read.
- A finding quotes the draft's line and gives what you checked it against, with what that showed.
- Give as a suggestion each resolution you see one level above the draft's, one that meets the need of the draft's Motivation at a place where it also covers the cases the draft's mechanism leaves, or that removes the need for a mechanism the draft adds or keeps. A ticket analyst takes or leaves it.
    - Suggest no patch to the draft's own mechanism.
    - Example: a revision of draft 2-736 had each ticket analyst write the `For the coordinator` heading only where it gives an item, and kept the operator sending whatever part it reads. The suggestion one level above it: the operator, which reads every analyst's part, sends nothing where the part gives no item, whatever an analyst writes.
        * comment: Ticket reviewer af471549f475ff481 moved that revision of draft 2-736 (2026-10-08T01:32:00Z revised, 01:33:07Z reviewed) to `tickets/open/` with no such suggestion, and the coordinator moved it back at 02:27:36Z after the user flagged the operator's side in session dc433af1-cf87-408d-ab9d-9a1ede6b1b2a at 2026-10-08T02:27:22: the log of ticket 2-736 and the Intent of ticket 2-766.

## Checks
- Check each of these:
    - A `change` ticket's `depends-on` gives the tickets [Change tickets](prompts/agents/notes/tickets.md#change-tickets) has its filer give there, and the `change` waits for no other ticket but, where it stands under `tickets/waiting/`, the `change` it waits on.
    - Instructions of the draft that edit the same part of a file, as [Change tickets](prompts/agents/notes/tickets.md#change-tickets) gives a part, are ordered.
    - Each claim the draft makes about the current state that the draft's outcome rests on holds now, by that state: each case, count and place it gives, each thing it says a file, a command or the tree does, and each result it expects a check of the tree to give. Such a claim that you do not settle is a finding.
        - Judge which claims the draft's outcome rests on by [A draft's outcome](prompts/agents/notes/launching.md#a-drafts-outcome).
        - The draft's `Grounds` give where the source of each claim lies, as read at the hash of `master` they give.
        * comment: With the line without its list in its context, ticket reviewer a283a71c0cf18c9ba passed two such claims of draft 2-527, on the lines of `CLAUDE.md` and `prompts/agents/notes/coordinator.md` that mention launching and on the hooks of `.claude/settings.json`, whose disproof its own calls had printed: the Intent of ticket 2-530.
    - A `change` to the agents' processes, a `change` whose Scope touches `prompts/agents/` or `src/operations/`, that changes what an agent reads or does, gives in its Motivation an outcome of [Process notes](prompts/agents/notes/process.md), and serves it, and its Scope covers each line of those notes that the change makes untrue.
        * comment: On the Scope: without it, the ticket reviews of these changes passed a Scope that left a line of Process notes untrue: change 6-1141 left Measurement of Process notes with no owner for the script-call check it added (bug 6-1171), change 6-597 left the line of Work products on a built document change giving the doc reviewer's review to a change merged past its cost budget (change 11-313), and the batch gate and the after-merge agent were left out of Verification, Merge and the built code change line (change 9-745).
    - A `change` that adds a mechanism to code has a `Design`, each existing operation that design gives does in the code what the design uses it for, no operation in the code computes what a new one it gives computes (DRY), and the Scope covers each file that design gives.
        * comment: The user's words, session 7fd429fb, 2026-10-15T22:44:57Z: "Let’s try it. Principles are short and well known in training set"; 2026-10-16T02:19:36Z: "almost seems liek a regression".
    - A `change` that adds or changes a rule or a fact in the agent-facing documents has a `Design` that gives, for each rule or fact, each rule and fact of the documents on the same act that its reader loads for the part of its work the design gives.
        - No rule that design leaves standing beside the new one is an exception to it.
        - No existing line states what a line that design gives states.
        - Each line that design gives stands, by the rules of [Editing the agent-facing documents](docs/handbook/editing.md), in the section whose subject it is.
        - Each reader of such a line loads that section for the part of its work the design gives.
        - Each line, or words in a line, that the design adds to stop a reader's failure meets the observed-failure test of [What a file holds](docs/handbook/editing.md#what-a-file-holds) by the failure the `change` cites under its `Grounds`.
        - The Scope covers each file that design gives.
        - For a rule or fact in a document under [agents](prompts/agents), the `Design` leaves no rule standing beside it, and gives the act it falls under of the spec in that document's editing notes, which you read in the file, or, where that spec gives no such act, a revision of that spec that gives the part of the reader's work that needs a new act and why no act's rule covers it.
    - The `Design` of a `change` to code or to the agent-facing documents gives under `Interactions:` each part of the system that reads, calls, orders or is ordered by what the files it touches hold, with what the change does to it.
        * comment: Without it, the `Design` of change 6-1210 put `alerts.ticket_stalls` ahead of the steps of the changes in `plan.EARLY`, and since the operator takes one step per call, operator adc8eb58fcc132a15 spent 7 calls of about 2 minutes on stall messages while a take was ready: bug 6-1404.
    - Each agent that executes the draft can follow each instruction under its documents: each agent, tool, permission and name the instruction relies on exists.
    - A rule's stated scope covers the readers the draft means it for, and no others.
    - Each item of the Intent is a requirement, as [An edit's items](prompts/agents/notes/launching.md#an-edits-items) gives it.
    - In a `change` that serves a `request`, each item of the Intent gives what it traces to: the user's words in a span of that request, quoted, or a line of that request's Grounds.
        - What an item traces to itself asks for or states what the item states.
        - The user's words are the text of the user's own messages.
        - Where the user's words choose an option the coordinator proposed, the trace quotes that choice and gives the option it picks as the coordinator's.
        - Where they choose such an option, the item states as its requirement the goal that option serves, in terms that hold for any design.
        - Such an item states no means of that option, and no range or ceiling a number of the option sets, that the user's words do not themselves state, whatever a line of the request's Grounds states about it.
    - A `Design` estimates what each part costs and gains against the goal of [The user's goals](prompts/agents/ticket-reviewer.md#the-users-goals) that its Intent serves, on each model an agent the design acts on runs on from the merge, where the model changes the estimate. No Intent item costs more than it gains by those estimates, and no part is kept whose estimated gain does not exceed its estimated cost. An estimate is a finding only where a figure the tree or the session gives shows it off by enough to turn that comparison.
    - No case that the readers of a line that sets a design meet, in the current state or among the cases the draft gives, makes that line wrong.
        * comment: Ticket reviewer a283a71c0cf18c9ba passed the design line "the one its session or its launch started at" of draft 2-527, which a compaction makes wrong, as a line the check on current-state claims does not reach and the draft's open list of failure cases covers: the Intent of ticket 2-530.
