# Decision notes
- The goals every decision on the solver tools and the agents' documents is made from, how a decision is made, and which decisions reach the user.

## Decisions

### The ladder
1. ARC-AGI-2 tasks solved by principled solvers that agents produce, with less of the user over time.
2. Each solver is principled and pure. It is principled when [Principles](docs/handbook/principles.md) justifies each of its parts. It is pure when it reads as the concept, with nothing verbose and nothing shaped to one task.
3. Everything around the agents is arranged so that they produce the best solvers. In particular, the tool computes what the principles define, reports what an agent can act on, leaves judgments to the agent, runs fast, and never reports what is not so.
4. The passes test that arrangement, and a fault a pass shows is fixed in the documents, the tool or the pass structure.
5. The checker changes without breaking as the handbook changes.
6. The process improves as it runs: each miss changes the brief or the document that caused it.

### Rule and intent
- [Principles](docs/handbook/principles.md) is the theory.
- [Procedure](docs/handbook/procedure.md), [Solver file](docs/handbook/solver-file.md), the text the tool prints, [Case inclusion: the decision history](docs/wf-solver/case-rule-history.md), [The user's preferences](#the-users-preferences) and the user's other past words are support: they show what was intended, and none of them is a rule on its own.
    - Implement no line of them that has no principle behind it, and decide its question as [How a decision is made](#how-a-decision-is-made) gives.
- The agents' definitions, the spec, and the lines after the ladder are support too. The spec of a code change is the docstrings of the modules it touches. Where a support line and a rung of the ladder disagree, follow the rung, and have the line rewritten.
- Have a support line added only where a rule is missing, and have a miss fixed by a change to the line that caused it.

### How a decision is made
- Where a decision touches a solver, the lib, the tool or what it reports, the witnesses, a solver pass, [Principles](docs/handbook/principles.md) or [Case inclusion: the decision history](docs/wf-solver/case-rule-history.md), read [Decisions on solver work](prompts/agents/notes/decisions.md#decisions-on-solver-work) as well.
- Where a decision touches a document an agent or a session reads, read [Decisions on the agents' documents](prompts/agents/notes/decisions.md#decisions-on-the-agents-documents) as well.
- A ground is a source that is quotable or checkable. Cite it so that every reader of your text can check it: by a path that reader can open, a command it can run, or the line quoted, and a bundled skill's file by the absolute path of the copy that invoking the skill extracts under `/private/tmp/claude-<uid>/bundled-skills/`.
- Before you state a reason, verify each claim it depends on. State with each reason its ground, or where it has none, its assumption.
- Rest no default on an assumption a ground rules out.
- Churn is no reason against an option, and a risk to behavior is one.
- Before you make a decision, write in one line the rung it bears on and what each option does to that rung.
- Check a reported problem against the state that produced it.
- Prefer the general option, the one that settles the other instances of the question too, and the tooling change only where the problem needs the rule enforced.
    * comment: With the lines of [Decision notes](prompts/agents/notes/decisions.md) "Make no option the default that fits only the instance that raised the decision." and "Prefer the general option, the one that settles the other instances of the question too, and where tooling can enforce the rule, the tooling change." in its context, an assignee added a hook that parsed every agent's Bash call to deny a harmless pattern, on the evidence of one solver read that cost one extra command: ticket 2-153, on ticket 3-4.
- Make no option the default that fits only the instance that raised the decision.
- Before you act on a default, write down the strongest reason against it. Where that reason is defensible, drop the default and reframe the problem: ask why the need arises, then decide where its answer goes.
- Carry out no resolution whose need no output depends on, and anticipate only a practice that prevents a bad situation of the kind that prompted past changes, never a mechanical gap in the tooling.
- Decide by [Principles](docs/handbook/principles.md) where it speaks, read for its intent: a line about one instance of a kind covers the kind when its reason does.
- Where it is silent, follow the intent the support shows.
- Where neither settles what the tool does, have the tool report an `undecided` finding.
- A default's discretion tier is how far it goes beyond what its grounds determine:
    1. A ground states it outright, or it fixes a bug.
    2. A ground determines it through a reading of the user's intent or of an existing convention, and that reading admits no other.
    3. The grounds permit more than one option, and the default is defensible from them.
    4. No ground bears on it.
- Record a decision where the rule it makes lives, as the rule alone, and record what it was made from and its discretion tier in the log of the ticket it settles or in your reply: a line of [Principles](docs/handbook/principles.md); a support line; a history entry, by its date; or, for the code's shape, the rung it serves.
    - Record each line you write before a decision or a resolution in the same place, beside what the decision was made from.
- The history of a decision is in the session transcripts, and `python3 ~/.claude/skills/retrieve/transcripts.py --help` lists the subcommands that read them.
- Take agents' reports as evidence of what is there, never of what the principles or the spec should be.
- Leave the judgment of how the code is written to the agents that read it.

### The user's part
- Bring the user a decision only where every option, after you reframe the problem, still has a defensible reason against it.
    - Give one line per option, the default first, with the option's consequence for the rungs, and where a rung is judged by reading solver code, that solver's code before and after.
    - Where the user does not rule on the decision, carry out its default.
- Tell the user, without waiting on them, each change that affects the user directly, in one line, with the solver's code before and after where the user judges it by that code. A change affects the user directly where it does one of these:
    - It changes what the user reads, judges or uses. The user judges solver code, a concept an Analyze pass wrote and [Principles](docs/handbook/principles.md).
    - It changes how the user's own Claude Code sessions behave.
    - It changes what the user must learn or do.
    - It moves or loses a persistent working file, or rewrites git history.
    - It clearly moves token or rate-limit use, machine load, or the time the process takes.
- Bring the user nothing else unless the user asks for it.

### The user's preferences
- Make the agents do their best work efficiently before you bring the solvers to their best form.
- Save tokens first and time second, and count about 30 minutes saved as worth about 150k tokens: split work that can run in parallel on disjoint files and run its parts at once, with no contention and no excess coordination between agents.
- Spend no run the work does not need, recompute no output or measurement that a file already holds, record nothing that nothing reads afterwards, and keep no state in a second copy.
- Keep the process, the code and their semantics in their best state, with maintainable code and good software practice the user need not ask for: fix the cause of a failure as well as the state it left, and keep no backwards compatibility with an old form.
- Keep the process fast, on no more of the user's CPU than it needs: find slowness yourself, check time as you check output so that performance does not regress, fix machine load through the cost of the work and never by a cap on agents or commands, and keep a merge's gate under a minute.
- Prefer simple mechanisms: watch an agent by reading what it does, with no classifier.
- Think a design through for how it can fail before it is implemented, and tell the agent that implements it to do so.
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
- Prime no test of agents' reading: its prompt gives the text under test and no gloss of its terms.
