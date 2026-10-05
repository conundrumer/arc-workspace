# Decision notes
- The goals every decision on the solver tools and the agents' documents is made from, how a decision is made, and which decisions reach the user.

## Decisions

### The ladder
1. ARC-AGI-2 tasks solved by principled solvers that agents produce, with less of the user over time.
2. Each solver is principled and pure. It is principled when [Principles](docs/handbook/principles.md) or the user's case judgments in [Case inclusion: the decision history](docs/wf-solver/case-rule-history.md) justify each of its parts. It is pure when it reads as the concept, with nothing verbose and nothing shaped to one task.
3. Everything around the agents is arranged so that they produce the best solvers. In particular, the tool computes what the principles define, reports what an agent can act on, leaves judgments to the agent, runs fast, and never reports what is not so.
4. The passes test that arrangement, and a fault a pass shows is fixed in the documents, the tool or the pass structure.
5. The checker changes without breaking as the handbook changes.
6. The process improves as it runs: each miss changes the brief or the document that caused it.

### Rule and intent
- [Principles](docs/handbook/principles.md) is the theory.
- [Procedure](docs/handbook/procedure.md), [Solver file](docs/handbook/solver-file.md), the text the tool prints, the case history and the user's past words are support: they show what was intended, and none of them is a rule on its own.
    - Implement no line of them that has no principle behind it, and decide its question as [How a decision is made](#how-a-decision-is-made) gives.
- The agents' definitions, the spec, and the lines after the ladder are support too. The spec of a code change is the docstrings of the modules it touches. Where a support line and a rung of the ladder disagree, follow the rung, and have the line rewritten.
- Have a support line added only where a rule is missing, and have a miss fixed by a change to the line that caused it.

### How a decision is made
- A ground is a source that is quotable or checkable.
- Before you state a reason, verify each claim it depends on. State with each reason its ground, or where it has none, its assumption.
- Rest no default on an assumption a ground rules out.
- Churn is no reason against an option, and a risk to behavior is one.
- Before you make a decision, write in one line the rung it bears on and what each option does to that rung.
- Check a reported problem against the state that produced it.
- Prefer the general option, the one that settles the other instances of the question too, and where tooling can enforce the rule, the tooling change.
- Make no option the default that fits only the instance that raised the decision.
- Where a default breaks a line of [Principles](docs/handbook/principles.md), the decision becomes whether to amend that line.
- Before you act on a default, write down the strongest reason against it. Where that reason is defensible, drop the default and reframe the problem: ask why the need arises, then decide where its answer goes.
- Carry out no resolution whose need no output depends on.
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
- Where a check or survey runs slowly, change how its runs are made and batched before you reconsider what it computes.

### The user's part
- Bring the user a decision only where every option, after you reframe the problem, still has a defensible reason against it.
    - Give one line per option, the default first, with the option's consequence for the rungs, and where a rung is judged by reading solver code, that solver's code before and after.
    - Where the user does not rule on the decision, carry out its default.
- Tell the user each change to what the user reads or judges, without waiting on them: solver code, a concept an Analyze pass wrote, [Principles](docs/handbook/principles.md), and a document or a brief the user reads. Give each change in one line, with the solver's code before and after where the user judges it by that code.
- Bring the user nothing else unless the user asks for it.
