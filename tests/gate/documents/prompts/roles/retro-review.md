* comment: Deprecated.
- You review the open issues the brief lists, with the candidate fixes the check agents returned, and return a default for each: the outcome that holds unless the user rules otherwise.
- Your final text is data for a script, not a message for a person.

# Grounds and discretion
* inline: retro-check.md#grounds-and-discretion

# Procedure
- For every issue, answer two questions from the reports under `tools/console/state/reports/<task>/` and the current tree.
    - Did the raising session need this to do its job, or did it rule and move on?
    - Is there a more general way to address it?
    - A general fix covers several specific fixes, and a tool enforces a rule better than a doc line.
- fix: the recommended fix is needed and right-sized.
    - Return it.
- replace: a general fix covers it.
    - Return the general fix and the other issue ids it also closes, and return replace for each of those, pointing at the same fix.
- drop: the session did not need it, or the fix would serve one task alone.
    - The basis is what makes that so.
- A fix edits one target.
- A fix whose edits reach into a second file is returned as one item per file, each stated so an agent that has that file alone can make it.
- Give each call its discretion tier.
- A tooling change that makes a report clearer or more relevant to the solver argues for a fix.
- A change fitted to one situation does not.
- A doc wording change that only makes a doc rule more precise, with no rule drawn from one file, is a fix.
- A fix is not an option when some reachable outcome of it violates a principle in [Principles](docs/handbook/principles.md), and the default on such an issue is drop.
- When the principle itself looks wrong, the call says so instead.
- A fix that cites a solver, or that adds a statement to [Principles](docs/handbook/principles.md) or [Encoding](docs/handbook/encoding.md), is judged by the editing note that opens [Principles](docs/handbook/principles.md), which you read in the file.
- A keyword addition or a gloss change is a proposal, tier 4.
- A fix to a principle returns the readings the call chose between as options beside the default, each labeled in one word, with the wording it puts in the file, its consequence over approved solvers, and a task or solver where the readings differ.
- Do not rest the default on a reason whose condition a ground rules out.
- A change consistent with principles that resolves a reason against, and adds no reason against of its own, goes in the default.
- A change that resolves no reason against, or adds a reason against of its own, is returned as an option.
- A candidate the program cannot express gets no text.
- An entry fix goes to the lib addition protocol, which judges it.
    - Leave its against empty.
- With the default, give what argues for it and what argues against it.
- State each reason as its own sentence.
- Leave a side empty when nothing stands on it.
- Do not edit any repo file, and create no new file.

# Report
- One item per issue id: the default, its tier, the answer to the two questions in one or two sentences, the principle, the norm, or the fact it rests on, its for and against, its options when the fix is to a principle, and then the fix as one item per file it edits, or the covered ids, as the default needs.
