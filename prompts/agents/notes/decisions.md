# Decision notes
- The user's goals, how a decision on the solver tools or the agents' documents is made, and which decisions reach the user.

## Decisions

### The user's goals
1. A winning write-up for the ARC-AGI-2 Grand Prize, of a neurosymbolic program synthesis approach, with its artifacts open-sourced.
2. A corpus of solvers that encodes the priors the synthesis rests on, which is why each solver must be good.
3. Both reached with less of the user over time, at low cost.

- Each decision on the solver tools and the agents' documents serves these goals. They guide how each other line is read and how a question or a fault is resolved: none is a rule a case must meet, and none overrides a line. Where two goals conflict, the one listed first weighs more.

### Rule and intent
- [Principles](docs/handbook/principles.md) is the theory.
- [Procedure](docs/handbook/procedure.md), [Solver file](docs/handbook/solver-file.md), the text the tool prints, [Case inclusion: the decision history](docs/wf-solver/case-rule-history.md), [The user's preferences](#the-users-preferences) and the user's other past words are support: they show what was intended, and none of them is a rule on its own.
    - Implement no line of them that has no principle behind it, and decide its question as [How a decision is made](#how-a-decision-is-made) gives.
- The agents' definitions, the spec, and the lines after the goals are support too. The spec of a code change is the docstrings of the modules it touches. Where a line, read for its intent, works against a goal, have it rewritten.
- Have a support line added only where a rule is missing.
- Have a fix of agent-facing text that misled an agent change the line that misled it. Agent-facing text is each text an agent reads: the documents, the briefs, the text a tool prints, its `--help` included, and a hook's message.

### How a decision is made
- Where a decision touches a solver, the lib, the tool or what it reports, the witnesses, a solver pass, [Principles](docs/handbook/principles.md) or [Case inclusion: the decision history](docs/wf-solver/case-rule-history.md), read [Decisions on solver work](prompts/agents/notes/decisions.md#decisions-on-solver-work) as well.
- Where a decision touches a document an agent or a session reads, read [Decisions on the agents' documents](prompts/agents/notes/decisions.md#decisions-on-the-agents-documents) as well.
- A ground is a source that is quotable or checkable. Cite it so that every reader of your text can check it: by a path that reader can open, a command it can run, or the line quoted, and a bundled skill's file by the absolute path of the copy that invoking the skill extracts under `/private/tmp/claude-<uid>/bundled-skills/`.
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
- Carry out no resolution whose need no output depends on, and anticipate only a practice that prevents a bad situation of the kind that prompted past changes, never a mechanical gap in the tooling.
- Decide by [Principles](docs/handbook/principles.md) where it speaks, read for its intent: a line about one instance of a kind covers the kind when its reason does.
- Where it is silent, follow the intent the support shows.
- Where neither settles what the tool does, have the tool report an `undecided` finding.
- A default's discretion tier is how far it goes beyond what its grounds determine:
    1. A ground states it outright, or it fixes a bug.
    2. A ground determines it through a reading of the user's intent or of an existing convention, and that reading admits no other.
    3. The grounds permit more than one option, and the default is defensible from them.
    4. No ground bears on it.
- Record a decision where the rule it makes lives, as the rule alone, and record what it was made from and its discretion tier in the log of the ticket it settles or in your reply: a line of [Principles](docs/handbook/principles.md); a support line; a history entry, by its date; or, for the code's shape, the goal it serves.
    - Record each line you write before a decision or a resolution in the same place, beside what the decision was made from.
- The history of a decision is in the session transcripts, and `python3 ~/.claude/skills/retrieve/transcripts.py --help` lists the subcommands that read them.
- Take agents' reports as evidence of what is there, never of what the principles or the spec should be.
- Leave the judgment of how the code is written, past the `Design` of its `change`, to the agents that read it.

### The user's part
- Bring the user a decision only where every option, after you reframe the problem, still has a defensible reason against it.
    - An option that departs from the user's words, a ruling of the user or a line of [Principles](docs/handbook/principles.md) has such a reason, which no reframe removes. Where every option left departs from one of them, bring the decision to the user at once, other than a ticket analyst's decline.
    - Give one line per option, the default first, with the option's consequence for the goals, and where the option changes a solver, that solver's code before and after.
    - Where the user does not rule on the decision, carry out its default.
- A ticket analyst's resolution of a ticket that leaves unmet part of a need the user stated, and departs from no ruling of the user and no line of [Principles](docs/handbook/principles.md), is a decline. The user stated a need in a ticket the coordinator filed from the user's words, a `request` in its spans or another ticket under its `Evidence`, or in a ticket whose Motivation gives such a ticket.
    - Carry a decline as a decision, with its defense: the concrete cost or risk of meeting the declined part, with its ground. A goal, a preference or another support line is a weight to judge by, and no defense.
    - A part whose decline a log line of the coordinator on the ticket lets stand is no decline again. Meet each part whose decline such a line vetoes.
- Tell the user, without waiting on them, each change that affects the user directly, in one line, with the solver's code before and after where the user judges it by that code. A change affects the user directly where it does one of these:
    - It changes what the user reads, judges or uses. The user judges solver code, a concept an Analyze pass wrote and [Principles](docs/handbook/principles.md).
        - The user judges a solver's code by whether it is principled and pure. It is principled when [Principles](docs/handbook/principles.md) justifies each of its parts. It is pure when it reads as the concept, with nothing verbose and nothing shaped to one task.
    - It changes how the user's own Claude Code sessions behave.
    - It changes what the user must learn or do.
    - It moves or loses a persistent working file, or rewrites git history.
    - It clearly moves token cost or rate-limit use, machine load, or the time the process takes.
- Bring the user nothing else unless the user asks for it.

### The user's preferences
- Make the agents do their best work efficiently before you bring the solvers to their best form.
- Save token cost first and time second, and count about 30 minutes saved as worth about $5 of token cost: split work that can run in parallel on disjoint files and run its parts at once, with no contention and no excess coordination between agents.
- Spend no run the work does not need, recompute no output or measurement that a file already holds, record nothing that nothing reads afterwards, and keep no state in a second copy.
- Keep the process, the code and their semantics in their best state, with maintainable code and good software practice the user need not ask for: fix the cause of a failure as well as the state it left, and keep no backwards compatibility with an old form.
- Keep the process fast, on no more of the user's CPU than it needs: find slowness yourself, check time as you check output so that performance does not regress, fix machine load through the cost of the work and never by a cap on agents or commands, and keep a merge's gate under a minute.
- Find the cause of a fault only as far as choosing among these options needs, and take the first that applies. An agent's choice that departs from its documents is no fault of its documents, and a place where the code behaves right but is not in its best state is no fault this line weighs. For a fault that is one more instance of a fault earlier tickets fixed, the cheapest change in each option is the cheapest change that removes the fault those instances share. This line rules over the preference for the general option and over fixing the cause of a failure as well as the state it left, except where it has the tree changed for such a fault.
    1. Where a line of the tree states or relies on what is not so, or agent-facing text misleads its reader, make the cheapest change that stops it: drop the reliance or the claim, or have a tool report less or `undecided`.
    2. Where the fault loses work, leaves work stuck or leaves an output wrong, make the cheapest change or take the cheapest workaround that prevents that, counting what building it costs and what it costs after, in each reader's context or on each call, and accept the loss it leaves.
    3. Where its loss is time or token cost alone, or nothing, accept it with no change, and close its ticket `wontfix` with that loss in the note, unless the loss you see in this instance and in the earlier tickets of the fault exceeds what the cheapest change costs.
- Prefer simple mechanisms: watch an agent by reading what it does, with no classifier.
- Think a design through for how it can fail before it is implemented.
- Take an agent's position: review the tool by reading a pass's transcript call by call, check a claim that an agent wasted work against its procedure, and where an agent departed from a rule, ask it about that departure before its document or the tool changes, and take its answer as the evidence.
    - Where you ask an agent about a choice it made, ask it to lay out its defense of the choice as a settled position, quoting the lines of its documents or its brief that the choice rests on, and ask for nothing that resembles an account of how it reached the choice or of what it recalls of its run.
- The tooling serves the agents: decide each choice on its design, and each fix that removes an outdated rule for efficiency, without the user. The user reads no code other than solver code, and no tool output.
- The solver console, retro, the `.claude/workflows` scripts, the role prompts and the `/session` skill are deprecated: note each as deprecated, remove none, and let none get in the way.
- Keep project content and ephemeral project state apart in git, lose no persistent working file in a migration, and scope the git permissions given to agents.
- Make a change to the user's global Claude configuration as a project of its own: verify it first, and where it needs no judgment, have an agent make it on `~/code/claude-config`.
- Resume an agent that the usage limit stopped by a message, in place of launching it again.
- The full lib interface the Create and Refine passes read up front, and the handbook appended to a session the user launches, are intended, and their cost is no waste.
- Keep in [arc-workspace](CLAUDE.md) only what every session needs, and in [Case inclusion: the decision history](docs/wf-solver/case-rule-history.md) only what helps decide, from the user's rulings, how [Principles](docs/handbook/principles.md) and the rules on a solver's cases are written.
- Choose the best term for each name, with no weight given to an existing one: a name may be abstract where it is precise, within the domain and with a qualifier where needed, a mathematical word imprecise for the thing is vetoed, abbreviations follow the software convention, judicious and consistent, and "task" may name a work item.
- Choose a label for its use in deciding how to act on what it labels.

## Decisions on solver work
- The agents produce good solvers through the arrangement around them, which is made so that the tool computes what the principles define, reports what an agent can act on, leaves judgments to the agent, and never reports what is not so.
- The solver passes test that arrangement, and what a pass shows of a fault in it is evidence for a change to the documents, the tool or the pass structure. A behavior of the harness is no part of that arrangement.
- Build the checker to change without breaking as the handbook changes.
- Where a default breaks a line of [Principles](docs/handbook/principles.md), the decision becomes whether to amend that line.
- Where a check or survey runs slowly, change how its runs are made and batched before you reconsider what it computes.
- Run a solver pass that ran under a wrong rule again once the rule is fixed, in place of patching its output.
- The tooling may come to serve generators or another frontend language as well as Souffle solvers, so divide it by what varies.
- Let a witness entry reassign any parameter, a grid-valued one with its anchor included, unless a good reason constrains it.
- The lib is the authoritative vocabulary of the priors ARC tasks compose, with perfect interfaces and fast implementations, and it may be rewritten whole, in Souffle or not, with custom functors.
- Keep no relation in the lib for convenience, a site count included, use no ADT as another way to write a disjunction, and count boilerplate in atoms.

## Decisions on the agents' documents
- Write the documents first to serve the agents that read them, and check new agent-facing text against each agent it reaches before a pass runs on it: at the point where the text has that agent act, the agent, with only what its context holds there, can tell that the text applies and can do what it says.
- The user writes no text: an agent makes each edit, and checks it, and the text it touches, for a change of meaning it was not meant to make.
- Keep instructions few, since a model follows a limited number of them: leave load-bearing text no misreading, add no verbosity in a rewrite, give an intuitive rule few words, restate no other document, and give no agent instructions on how to follow the document that is its body.
- Structure the documents so that changes to them run in parallel, as changes to code do, and so that they make evident which agent takes a kind of work and lead each agent to what it needs.
- Give a context bound, at which an agent ends and a fresh agent takes up its work, only to an agent that polls for an indefinite time, whose context grows with time and not with its task. An agent with a finite task keeps its context to the end of that task, since its work depends on that context.
- Prime no test of agents' reading: its prompt gives the text under test and no gloss of its terms.
