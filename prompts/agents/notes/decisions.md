+ document-size-budget: 26674
* comment: when editing this doc
    - The ticket analyst and the draft analyst inline the subsections of [Decisions](#decisions) other than A decision's record in a reply, for resolving a ticket, and [Resolving](#resolving), for applying a resolution. The decision analyst inlines The user's goals, Rule and intent, How a decision is made, The user's part, Cost and time and Agents' choices, for judging what a change's editors leave, ruling a held step and ruling a declined load act. The reply files of the checklists of those three link [analyst-reply](#analyst-reply), for giving their reply. The ticket reviewer and the doc reviewer inline The user's goals, for weighing a design or a change. The coordinator loads Decisions, The user's part and Defaults by the links of its Decisions section, before it makes a decision or ends a turn with one. Process notes, the ticket analyst's step documents and the coordinator's change notes link sections of it.
    - Acts, each with its section:
        - Weighing what a decision serves: [The user's goals](#the-users-goals).
        - Reading a rule by its intent: [Rule and intent](#rule-and-intent).
        - Recording what a decision was made from in a reply: [A decision's record in a reply](#a-decisions-record-in-a-reply).
        - Making a decision: [How a decision is made](#how-a-decision-is-made), with [Decisions on solver work](#decisions-on-solver-work) and [Decisions on the agents' documents](#decisions-on-the-agents-documents) for those subjects.
        - Bringing a decision to the user: [The user's part](#the-users-part).
        - Trading cost, time and quality: [The user's preferences](#the-users-preferences).
        - Giving a decision's default and applying it: [Defaults](#defaults).
        - Applying a ticket analyst's resolution: [Resolving](#resolving).
        - The items of a ticket analyst's reply: [analyst-reply](#analyst-reply).

# Decision notes
- How a decision is made, and which decisions reach the user.

## Decisions

### The user's goals
1. A winning write-up for the ARC-AGI-2 Grand Prize, of a neurosymbolic program synthesis approach, with its artifacts open-sourced.
2. A corpus of solvers that encodes the priors the synthesis rests on, which is why each solver must be good.
3. Both reached with less of the user over time, at low cost.

- Each decision on the solver tools and the agents' documents serves these goals. When the user mentions [Decision notes](prompts/agents/notes/decisions.md), your behavior is working against those goals. They guide how each other line is read and how a question or a fault is resolved: none is a rule a case must meet, and none overrides a line. Where two goals conflict, the one listed first weighs more.
    * comment: The user's words, session 2384db39-7d21-4d8d-8dda-bfd52bd69360, 2026-10-20T21:02:41Z: "Decisions.md should have a note saying that when I mention it, it’s triggered from you behaving in a counterproductive way wrt goals". Request 11-2507.

### Rule and intent
- [Principles](docs/handbook/principles.md) is the theory.
- [Procedure](docs/handbook/procedure.md), [Solver file](docs/handbook/solver-file.md), the text the solver tool, `scripts/run_dl.py`, prints, [Case inclusion: the decision history](docs/wf-solver/case-rule-history.md), [The user's preferences](prompts/agents/notes/decisions.md#the-users-preferences) and the user's other past words are support: they show what was intended, and none of them is a rule on its own.
    - Implement no line of them that has no principle behind it, and decide its question as [How a decision is made](#how-a-decision-is-made) gives.
        + xref: prompts/agents/notes/decisions.md#how-a-decision-is-made
- The agents' definitions and the spec are support too. The spec of a code change is the docstrings of the modules it touches. Where a line, read for its intent, works against a goal, have it rewritten.
- Have a support line added only where a rule is missing.
- Agent-facing text is each text an agent reads: the documents, the briefs, the text a tool prints, its `--help` included, and a hook's message.

### How a decision is made
- Where a decision touches a solver, the lib, the solver tool or what it reports, the witnesses, a solver pass, [Principles](docs/handbook/principles.md) or [Case inclusion: the decision history](docs/wf-solver/case-rule-history.md), read [Decisions on solver work](prompts/agents/notes/decisions.md#decisions-on-solver-work) as well.
- Where a decision touches a document an agent or a session reads, read [Decisions on the agents' documents](prompts/agents/notes/decisions.md#decisions-on-the-agents-documents) as well.
- A ground is a source that is quotable or checkable. Cite it so that every reader of your text can check it: by a path that reader can open, a command it can run, or the line quoted, and a bundled skill's file by the absolute path of the copy that invoking the skill extracts under `/private/tmp/claude-<uid>/bundled-skills/`.
    * comment: Without the bundled skill's clause, a ticket reviewer, given a skill's file cited by a path relative to the skill, searched the CLI binary six minutes for what that file holds: ticket 2-357.
- Before you state a reason, verify each claim it depends on. State with each reason its ground, or where it has none, its assumption.
- Rest no default on an assumption a ground rules out.
- Churn is no reason against an option, and a risk to behavior is one.
- Before you make a decision, write in one line the goal it bears on and what each option does to that goal.
- Check a reported problem against the state that produced it.
- Prefer the general option, the one that settles the other instances of the question too, and the tooling change only where the problem needs the rule enforced.
    * comment: With the lines of [Decision notes](prompts/agents/notes/decisions.md) "Make no option the default that fits only the instance that raised the decision." and "Prefer the general option, the one that settles the other instances of the question too, and where tooling can enforce the rule, the tooling change." in its context, an assignee added a hook that parsed every agent's Bash call to deny a harmless pattern, on the evidence of one solver read that cost one extra command: ticket 2-153, on ticket 3-4.
- Make no option the default that fits only the instance that raised the decision.
- Before you act on a default, write down the strongest reason against it. Where that reason is defensible, drop the default and reframe the problem: ask why the need arises, then decide where its answer goes.
    - Where you decide how to resolve a fault, or how to make a change the user asks for, keeping each mechanism of the tree in which the problem shows is a default, and the reason against keeping one is a reason against the mechanism itself, apart from any fault in it.
        * comment: With the line "Before you act on a default, write down the strongest reason against it." in its context, ticket analyst a4b3eb50ada587b16, on ticket 2-526, kept the review of a launch brief that took five review rounds, and wrote no reason against keeping that review: tickets 2-527 and 2-579, and its transcript at line 235.
- Apply no resolution whose need no output depends on.
- A `question` whose case has no instance, no input the tree holds or a run produced that reaches it, no test `master` held before the change that gives it and no line of Principles that requires it, has a need no output depends on: close it `wontfix`, with that judgment and no defense.
    * comment: The user's words, session 2384db39, 2026-10-18T12:12:07Z: "answer a question about a case the corpus never has with `wontfix`, so it adds no code", and 12:15:45Z, "Go": ticket 9-1350.
- Anticipate each kind of bad situation that prompted past changes, and recommend the practice that prevents it: a kind is the situations one cause makes, and it covers each place where that cause stands, whether or not a situation showed there. A resolution at such a place has a need an output depends on. Recommend no practice for a place that no such cause reaches.
    * comment: The user's words, session dc433af1, 2026-10-05T18:54:16Z: "there's no evidence for a need for "not covered", and that's "dumb" stuff. i was thinking more about practices that prevents bad situations like what prompted all the changes. i was trying to anticipate those situations.", and 18:58:20Z: "ok so you have nothing to recommend to prevent general SWE scaling software problems and everything's fine, got it". Without the clauses on the cause, a ticket analyst closed ticket 10-960 wontfix, reading the kind as one launch site, so that each site of a cause that had faulted at four sites waited for its own fault; the user, session 2384db39, 2026-10-17T15:39:33Z, on that close: "sounds circular": ticket 11-75.
- Decide by [Principles](docs/handbook/principles.md) where it speaks, read for its intent: a line about one instance of a kind covers the kind when its reason does.
- Where it is silent, follow the intent the support shows.
- Record a decision where the rule it makes lives, as the rule alone, and record what it was made from in the log of the ticket it settles: a line of [Principles](docs/handbook/principles.md); a support line; a history entry, by its date; or, for the code's shape, the goal it serves.
    - Record each line you write before a decision or a resolution in the same place, beside what the decision was made from.
- The history of a decision is in the session transcripts, and `python3 ~/.claude/skills/retrieve/transcripts.py --help` lists the subcommands that read them.
- Take agents' reports as evidence of what is there, never of what the principles or the spec should be.
- Leave the judgment of how the code is written, past the `Design` of its `change`, to the agents that read it.

### A decision's record in a reply
- You may record what a decision was made from, and each line you write before it, in your reply in place of the log of the ticket it settles.

### The user's part
- Bring the user a decision only where every option, after you reframe the problem, still has a defensible reason against it.
    - An option that departs from the user's words, a ruling of the user or a line of [Principles](docs/handbook/principles.md) has such a reason, which no reframe removes. Where every option left departs from one of them, bring the decision to the user at once.
    - Give one line per option, the default first, with the option's consequence for the goals, and where the option changes a solver, that solver's code before and after.
- A ticket analyst's resolution of a ticket, or a decision analyst's resolution of what a change's editors leave, that leaves unmet part of a need the user stated, and departs from no ruling of the user and no line of [Principles](docs/handbook/principles.md), is a decline. The user stated a need in a ticket the coordinator filed from the user's words, a `request` in its spans or another ticket under its `Evidence`, or in a ticket whose Motivation gives such a ticket.
    - Give a decline as a decision for the coordinator, in place of one for the user, with its defense: the design that meets the declined part at the least cost or risk you found once you reframed the problem as [How a decision is made](#how-a-decision-is-made) gives, and that cost or risk, as an estimate, with the figures the tree or the session gives for it where they exist. A goal, a preference or another support line is a weight to judge by, and no defense.
        + xref: prompts/agents/notes/decisions.md#how-a-decision-is-made
    - A part whose decline a log line of the coordinator on the ticket lets stand is no decline again. Meet each part whose decline such a line vetoes.
- Tell the user, without waiting on them, each change that affects the user directly, in one line, with the solver's code before and after where the user judges it by that code. A change affects the user directly where it does one of these:
    - It changes what the user reads, judges or uses. The user judges solver code, a concept an Analyze pass wrote and [Principles](docs/handbook/principles.md).
        - The user judges a solver's code by whether it is principled and pure. It is principled when [Principles](docs/handbook/principles.md) justifies each of its parts. It is pure when it states the concept, with nothing verbose and nothing shaped to one task.
    - It changes how the user's own Claude Code sessions behave.
    - It changes what the user must learn or do.
    - It moves or loses a persistent working file, or rewrites git history.
    - It clearly moves token cost or rate-limit use, machine load, or the time the process takes.
- Bring the user nothing else unless the user asks for it.

### The user's preferences
- Make the agents do their best work efficiently before you bring the solvers to their best form.
- Spend no run the work does not need, recompute no output or measurement that a file already holds, record nothing that nothing reads afterwards, and keep no state in a second copy.
- Keep the process, the code and their semantics in their best state, with maintainable code and good software practice the user need not ask for: fix the cause of a failure as well as the state it left, and keep no backwards compatibility with an old form.
- Keep the process fast, on no more of the user's CPU than it needs: find slowness yourself, check time as you check output so that performance does not regress, fix machine load through the cost of the work and never by a cap on agents or commands, and keep a merge's gate under a minute.
- Find the cause of a fault only as far as choosing among these fault options needs. Take option 1 where it applies and option 2 where it applies, and option 3 only where neither does. These options rule over the preference for the general option and over fixing the cause of a failure as well as the state it left, except where they have the tree changed for such a fault.
    1. Where a line of the tree states or relies on what is not so, or a reader misread agent-facing text, true or not, make the cheapest change that stops it: drop the reliance or the claim, have a tool report less or `undecided`, or reword the misread words so that they admit no such reading, adding no line and few words: a fix that needs many added words fails, and where no change of few words stops it, option 1 does not apply.
        * comment: The user's words, session 7fd429fb, 2026-10-13T02:58:03Z: "that should use clarification, but like improving the wording, not like adding new lines", and 02:59:39Z: "i want ot makei t very clear it is a failure if many words needed to be added".
    2. Where the fault loses work, leaves work stuck or leaves an output wrong, or lets a wrong output stand where a line of the tree claims that a check or a report shows it, make the cheapest change or take the cheapest workaround that prevents that, counting what building it costs and what it costs after, in each reader's context or on each call, and accept the loss it leaves. A change that makes a check or a report show such an output, where a line of the tree claims that it does, needs no past situation to show its need.
    3. Where its loss is time or token cost alone, or nothing, accept it with no change and close its ticket `wontfix`, unless the loss of the fault, seen in this instance and in its earlier tickets and expected at the same rate at each other place its cause stands, exceeds what the cheapest change costs.
        - The close note gives that loss in dollars, its token cost as `uv run python scripts/profile_runs.py <agent id> ...` prints it for the runs the fault spent and its time at the rate [Cost and time](#cost-and-time) gives, and the places it expects loss at, by their count and the command or list that gives them, beside the cheapest change that removes the fault with that change's cost in dollars, or beside the statement that no change removes it.
            + xref: scripts/profile_runs.py:parser, prompts/agents/notes/decisions.md#cost-and-time
- A place where the code behaves right but is not in its best state is no fault the fault options weigh.
- For a fault that is one more instance of a fault earlier tickets fixed, the cheapest change in each fault option is the cheapest change that removes the fault those instances share.
- Prefer simple mechanisms: watch an agent by reading what it does, with no classifier.
- Think a design through for how it can fail before it is implemented.
- The tooling serves the agents: decide each choice on its design, and each fix that removes an outdated rule for efficiency, without the user. The user reads no code other than solver code, and no tool output.
- The `.claude/workflows` scripts, the role prompts and the `/session` skill are deprecated: note each as deprecated, remove none, and let none get in the way.
- Keep project content and ephemeral project state apart in git, lose no persistent working file in a migration, and scope the git permissions given to agents.
- Make a change to the user's global Claude configuration as a project of its own: verify it first, and where it needs no judgment, have an agent make it on `~/code/claude-config`.
- Choose the best term for each name, with no weight given to an existing one.
    - A name may be abstract where it is precise, within the domain and with a qualifier where needed.
    - A mathematical word imprecise for the thing is vetoed.
    - Abbreviations follow the software convention, judicious and consistent.
    - "task" may name a work item.
- Choose a label for its use in deciding how to act on what it labels.

#### Cost and time
* comment: The user's words, session 2384db39, 2026-10-19T12:37:34Z: "I guess it's just one short sentence with one number? \"Week has $X\"?"
- A cost is in subscription dollars, a plan's price per week times the share of its weekly usage window the work uses: the Claude week is about $46 and the Codex week about $23.
- A change spends about $0.15 after the decision beyond its ticket's budget, in its ticket review and revisions, the operator's turns and the reviews of its runs.
    * comment: The user's words, session 2384db39, 2026-10-19T12:46:01Z: "Expedite the cost fix". Measure: the ticket-reviewer, draft-analyst, operator, general-purpose, code-reviewer and lib-reviewer costs of `uv run python scripts/profile_runs.py 2384db39-7d21-4d8d-8dda-bfd52bd69360 129de8fc-2a0d-4d4d-b950-3a0194c762e2 f44896df-9faa-48b9-b4ce-992d850c46df 62ca2ad1-bd13-4adc-82f3-20fb26d2049a --since 2026-10-18T17:54:30Z`, $1,038.75 in sum, divided by the 154 `change` tickets closed `fixed` in that window, counted by `grep -l '^kind: change' tickets/closed/*.md | xargs grep -h -E '^20[0-9-]+T[0-9:]+Z closed \[[^]]*\]: fixed' | awk '$1 >= "2026-10-18T17:54:30Z"' | wc -l` at 2026-10-19T13:25Z. The types leave out the build and its decision analysts, which a ticket's budget gives. Failure: the estimate of ticket 11-1958 priced only the doc editor's runs.
- Save token cost first and time second, and count about 30 minutes saved as worth about $0.11 of token cost: split work that can run in parallel on disjoint files and run its parts at once, with no contention and no excess coordination between agents.

#### Agents' choices
- An agent's choice that departs from its documents is no fault of its documents.
- Take an agent's position: review the solver tool by reading a pass's transcript call by call, check a claim that an agent wasted work against its procedure, and where an agent departed from a rule, ask it about that departure before its document or the solver tool changes, and take its answer as the evidence.
    - Where you ask an agent about a choice it made, ask it to lay out its defense of the choice as a settled position, quoting the lines of its documents or its brief that the choice rests on, and ask for nothing that resembles an account of how it reached the choice or of what it recalls of its run.

## Decisions on solver work
- The agents produce good solvers through the arrangement around them, which is made so that the solver tool computes what the principles define, reports what an agent can act on, leaves judgments to the agent, and never reports what is not so.
- The solver passes test that arrangement, and what a pass shows of a fault in it is evidence for a change to the documents, the solver tool or the pass structure. A behavior of the harness is no part of that arrangement.
- Where neither [Principles](docs/handbook/principles.md) nor the support settles what the solver tool does, have the solver tool report an `undecided` finding.
- Build the checker to change without breaking as the handbook changes.
- Where every option left for a solver to encode a rule of the concept its Analyze pass gave exempts the solver from a line of [Principles](docs/handbook/principles.md) or of the handbook's rules, amends such a line, or reads that rule otherwise than the concept states it, the decision is that concept.
    - Bring the user the concept, that rule and the line the solver cannot meet, with a default that leaves the solver and its ticket as they stand.
    - Where that default breaks a line of [Principles](docs/handbook/principles.md) otherwise, the decision becomes whether to amend that line.
- Where a check or survey runs slowly, change how its runs are made and batched before you reconsider what it computes.
- Run a solver pass that ran under a wrong rule again once the rule is fixed, in place of patching its output.
- The tooling may come to serve generators or another frontend language as well as Souffle solvers, so divide it by what varies.
- Let a witness entry reassign any parameter, a grid-valued one with its anchor included, unless a good reason constrains it.
- The lib is the authoritative vocabulary of the priors ARC tasks compose, with perfect interfaces and fast implementations, and it may be rewritten whole, in Souffle or not, with custom functors.
- Keep no relation in the lib for convenience, a site count included, use no ADT as another way to write a disjunction, and count boilerplate in atoms.
- Keep in [Case inclusion: the decision history](docs/wf-solver/case-rule-history.md) only what helps decide, from the user's rulings, how [Principles](docs/handbook/principles.md) and the rules on a solver's cases are written.

## Decisions on the agents' documents
- Write the documents first to serve the agents that read them, and check new agent-facing text against each agent it reaches before a pass runs on it: at the point where the text has that agent act, the agent, with only what its context holds there, can tell that the text applies and can do what it says.
- The user writes no text: an agent makes each edit, and checks it, and the text it touches, for a change of meaning it was not meant to make.
- Keep instructions few, since a model follows a limited number of them: leave load-bearing text no misreading, add no verbosity in a rewrite, give an intuitive rule few words, restate no other document, and give no agent instructions on how to follow the document that is its body.
- Structure the documents so that changes to them run in parallel, as changes to code do, and so that they make evident which agent takes a kind of work and lead each agent to what it needs.
- Give a context bound, at which an agent ends and a fresh agent takes up its work, only to an agent that polls for an indefinite time, whose context grows with time and not with its task. An agent with a finite task keeps its context to the end of that task, since its work depends on that context.
- Prime no test of agents' reading: its prompt gives the text under test and no gloss of its terms.
- The full lib interface the Create and Refine passes read up front, and the handbook appended to a session the user launches, are intended, and their cost is no waste.
- Keep in [arc-workspace](CLAUDE.md) only what its readers need.

## Defaults
- Say in a decision its default is the user's ruling unless their next reply rules on or asks about it.
- A default can be undone where git or the ticket tracker reverses its whole effect, such as a merge to `master`, a ticket's move or a filed ticket, and cannot where it sends anything out of the session, deletes work that is not in git, or rewrites git history. Where you cannot tell which holds, it cannot.
    * comment: Without the instances, a coordinator trial of doc reviewer ab593b418d23f9831 on change 6-688, agent a241fd876fa112d54, judged a merge of change 6-700 one it could not tell git reverses, from what `merge_change.py` does beyond the commit, and started no timer.
- Say in each decision whether its default can be undone, and where it can, that it goes ahead at the end of the delay, with the time that delay ends.
- The delay is 30 minutes from your first reply, since the user's last message, that gives a decision. End that reply's turn by running `uv run python scripts/agent_timer.py start budget "$CLAUDE_CODE_SESSION_ID" 1800` in the background.
    + xref: scripts/agent_timer.py:Kind.BUDGET
- At the user's next message, run `uv run python scripts/agent_timer.py stop budget "$CLAUDE_CODE_SESSION_ID"`.
    + xref: scripts/agent_timer.py:Action.STOP
- When that start completes and its output ends with `timer completed`, the user is away until their next message: apply the default of each waiting decision that can be undone, and until the user's next message, apply at once the default of each later decision that can be undone, in place of bringing it to the user. Where its output ends otherwise, apply no default.
    + xref: scripts/agent_timer.py:start
- In your reply to the user's first message after a default went ahead with no message of the user, list each such default, with how to undo it, and with no `**Blocked on you.**` label.

## Resolving
- Where [The user's part](#the-users-part) brings a decision to the user, act on none of its options, and move the ticket to `tickets/blocked/` with a note that opens with `user` and gives the decision.
- Apply every other resolution: where it changes the tree, file a `change` ticket for it, with the number of each ticket it settles in its Motivation, and move each of those tickets to `tickets/waiting/` with a note that opens with `change` and that change's number, and otherwise close the ticket with its resolution word.
    - Where that `change` serves a `request`, add to the request the `## Validation` section that `uv run python scripts/file_ticket.py --help request` gives, from the need its Goal states.
        + xref: scripts/file_ticket.py:SUBCOMMANDS
- Where your resolution is a decline, close no ticket for it. Move the ticket it leaves with the decline, the `change` you file or revise or the ticket you would close, to `tickets/blocked/` with a note that opens with `user decline` and gives the declined part and its defense.
- Give rote work to an agent, and judge the list it returns.

## analyst-reply
- At the end of your reply, under a `## For the coordinator` heading, give a list item for each decision you bring the user, opened with `decision:`, for each change [The user's part](#the-users-part) tells the user, opened with `tell:`, and for each item that your brief or a later request asks of you, that you leave undone and that waits on you alone, opened with `unfinished:`, with its reason, and nothing else.
    - Give each decision and each change in the form that section gives, with each line after its item's first line nested under that item.
        + xref: prompts/agents/notes/decisions.md#the-users-part
    - Give each decline as a `decision:` item whose text opens with `decline`.
- In your reply, give each ticket you judged, and each item your brief or a later request gives, with its resolution, other than those the `For the coordinator` heading gives, each decision with what it was made from, each `change` ticket you filed or revised, by its path, and each agent you launched, by its agent id.
    - Give an item whose ticket another agent holds with that ticket's `assigned` log line, and an item that waits on the user with the log line that gives that wait.
