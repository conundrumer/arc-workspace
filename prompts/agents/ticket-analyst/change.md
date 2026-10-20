+ document-size-budget: 11479
* comment: when editing this doc
    - The ticket analyst and the draft analyst receive this document from the step command as they enter the part of their work that writes the text of a `change` they file or revise, once they have chosen that resolution.
    - Acts, each with its section:
        - Writing the Intent, its items' traces and its coverage of the need: [Requirements](#requirements).
        - Writing the `change`'s Motivation, its `Design`, the Scope that design gives, and its `Grounds`: [Design](#design).
        - Checking the draft by the ticket reviewer's checks: [Checking a draft](#checking-a-draft).

# Writing a change ticket

## Requirements
- When you write the Intent of a `change` to the agents' processes, a `change` whose Scope touches `prompts/agents/` or `src/operations/`, read [Process notes](prompts/agents/notes/process.md).
- Give with each Intent item of a `change` that serves a `request`, and that you file or revise, what it traces to, as the check on an Intent item's trace in [Checks](prompts/agents/ticket-reviewer/review.md#checks) gives it.
    + xref: prompts/agents/ticket-reviewer/review.md#checks
    - Put each means of an option the user's words choose in the `Design` alone, as a candidate that the `Design` may take or change.
- Make the Intent's items, with each decline you give, cover each part of the need that the Goal and spans of the request, or the Impact and Evidence of each ticket the change settles, give, over each reader, file and case their words name.
    * comment: The user's "File", session 7fd429fb-e3be-4173-9b0e-df52f507d6a2, 2026-10-12T16:36:16Z, which chose the coordinator's option of 16:36:02Z, "The stage ends with a coverage check that the requirements cover the whole goal". Change 6-690 covered only the coordinator's document of 6-685's need for the agent documents, and 6-685 closed `fixed` with the rest unmet.

## Design
- In a `change` for speed, give in its Scope the figures of each profile that exists, with the record that holds them, and no command, script or replay that its editor runs to profile.
    * comment: The user's words, session 2384db39, 2026-10-18T13:32:25Z, "Go", on the coordinator's proposal that an editor on a speed change time only the runs its work does anyway. The Scope of 11-1177 gave a `profile_call.py` command line, and its code editor ran that replay for minutes at about 0.6 to 1 core: request 11-1265. Ticket 11-1279.
- Write the Motivation and the Scope of a `change` to the agents' processes as the check on it in [Checks](prompts/agents/ticket-reviewer/review.md#checks) gives.
    + xref: prompts/agents/ticket-reviewer/review.md#checks
- For a `change` to code or to the agent-facing documents, run `uv run python scripts/area.py` on the files its design touches, read each place its `References` list gives that uses a name or a section the change alters, and search with the Grep tool for each name (a function, method or attribute) and each key phrase of a rule that the change alters, and for each kind of reference that `uv run python scripts/area.py --help` gives the list as leaving out, by the key it gives. Give under a line `Interactions:` in the `Design` each part that output and your reading find, with what the change does to it.
    * comment: Analysts gave the gate's outputs as changed by an edit of the documents: tickets 10-644, 11-740, 11-1438.
- Write the `Design` section of a `change` that adds a mechanism to code from reading the code, and of a `change` that adds or changes a rule or a fact in the agent-facing documents from reading the documents it touches, so that the design makes illegal states unrepresentable, each mechanism it adds is no larger than the cases it serves need, and it gives by its standard name each other principle of software design it applies, by these steps:
    * comment: The user's words, session 7fd429fb, 2026-10-13T14:46:25Z: "im curious if this could be part of a planning principle"; 14:47:10Z: "what about just poitnting at the core idea", the core idea being "Make illegal states unrepresentable"; 14:47:43Z, on reading the bare name as license for big refactors: "i dont expect that to happen but if it did i would welcome it". On the standard names, the user's words, session 7fd429fb, 2026-10-15T22:44:57Z: "Let’s try it. Principles are short and well known in training set"; 2026-10-16T02:19:36Z: "almost seems liek a regression".
    1. For a `change` to the documents, plan by rule or fact, as the check on such a `Design` in [Checks](prompts/agents/ticket-reviewer/review.md#checks) gives. Give for each rule and fact it finds whether the new one joins it, replaces it, retires it or stands beside it, and how the new one goes in: as a change to an existing line, as a new line in that section, or not at all.
        + xref: prompts/agents/ticket-reviewer/review.md#checks
        - For a change to a document under [agents](prompts/agents), read the spec in the editing notes of each document it edits.
    2. Estimate what each part of the design costs and what it gains, as the check on a `Design`'s estimates in [Checks](prompts/agents/ticket-reviewer/review.md#checks) gives. Take the figures the tree and the session give where they exist, such as `profile_runs` costs, a ticket's budget and the prices of [token_prices.py](scripts/token_prices.py), and otherwise estimate from the work's size.
        + xref: prompts/agents/ticket-reviewer/review.md#checks
    3. Where an Intent item fails the estimate check of [Checks](prompts/agents/ticket-reviewer/review.md#checks), reframe the problem of that item as [How a decision is made](prompts/agents/notes/decisions.md#how-a-decision-is-made) gives, for a design that meets it at a gain above its cost. Where you find none, take the item out of the Intent and out of the `Design`, and where it serves a need the user stated, give leaving it unmet as a decline, as [Resolving](prompts/agents/notes/decisions.md#resolving) gives.
        + xref: prompts/agents/ticket-reviewer/review.md#checks, prompts/agents/notes/decisions.md#how-a-decision-is-made, prompts/agents/notes/decisions.md#resolving
    4. Where a part fails the estimate check of [Checks](prompts/agents/ticket-reviewer/review.md#checks) on one model only, reframe it to apply only on the models where it gains, and where no reframe does that, bring the user the decision on it. Leave out each other part that fails it, or bring the user the decision on it. Bring each such decision as [The user's part](prompts/agents/notes/decisions.md#the-users-part) gives, as a `decision:` item, and not as your own decision with a `tell:`.
        + xref: prompts/agents/ticket-reviewer/review.md#checks, prompts/agents/notes/decisions.md#the-users-part
    5. Cover in its Scope each file that design gives that the change edits. `uv run python scripts/file_ticket.py scope-check <number>`, or with the draft's text on its stdin before you file it, prints each path of that design the Scope leaves out.
        + xref: scripts/file_ticket.py:SUBCOMMANDS
- Give under `Grounds` of each `change` you file or revise each ground its design rests on: each line quoted with its file's path, each command with its output, each transcript span with its session and times, and the hash of `master` at which they hold. `uv run python scripts/file_ticket.py ground` prints that line for a span of a file or for a command.
    + xref: scripts/file_ticket.py:SUBCOMMANDS

## Checking a draft
- Check a draft by each check of [Checks](prompts/agents/ticket-reviewer/review.md#checks), cut and check its claims as [A draft's outcome](prompts/agents/notes/launching.md#a-drafts-outcome) gives, and fix each fault a check shows.
    + xref: prompts/agents/ticket-reviewer/review.md#checks, prompts/agents/notes/launching.md#a-drafts-outcome
