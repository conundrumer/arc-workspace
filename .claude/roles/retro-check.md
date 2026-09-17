You check the issues the brief lists, all about one shared thing, and return a status for each. Your final text is data for a script, not a message for a person.

## Procedure

- The window is at `.scratch/retro/window.json`; a task's `ts` is when it landed. A task's reports are under `tools/console/state/reports/<task>/` (`create.md`, `refine.md`, `finalize.md` when present); open one only when an issue needs its context. You may read `src/dl/`, which a solver session may not.
- closed: a later change closed it. Find the change with `git log --since=<the task's ts> -p -- <the files the issue is about>` and compare the current text against the complaint. Name the commit or the current text. When a claim does not hold against the current code or text, check whether it held at the report's time. Find the change with a content search over git history (`git log -S`), and compare its time with the report's. A change that postdates the report closes the issue.
- dropped: no fix should be made. The fix would serve one task's case, which overfits; or the issue is a judgment the shared thing should not settle. An argument from what earlier solvers did is weak, weakest for the earliest. Give what argues for the drop and what argues against it, each reason as its own sentence, and the fix the drop declines, so a reversal can make it. Give the drop its discretion level, how much room it took beyond what the grounds determine. 1: a ground states it outright, or it fixes a bug. 2: a ground determines it through a reading of the user's intent or of an existing convention, and that reading admits no other. 3: the grounds permit more than one option, and the default is defensible from them. 4: no ground bears on it.
- open: say whether the issue changed what a session did (a wrong ruling, a reversal, wasted work, a workaround) or was only noted. Return the candidate fixes, each with for and against, the recommended first.
- A fix has a kind. prose: a doc under `docs/` or a comment in `programs/lib.dl` or a module under `programs/lib/`. code: the runner under `src/`, the console under `tools/console/`, or a lib implementation change that keeps every member relation, signature, and claim as they are. solver: a solver under `programs/solvers/`, one file per task id. entry: a lib change a caller can see, a member relation added or removed, a signature, a claim. The retro does not make that change; the fix is a proposals entry per `docs/wf-solver/lib-protocol.md` with its `Survey:` line, and the protocol runs from there.
- A fix edits one target. When closing an issue takes edits in two files, give one candidate fix per file, each stated so an agent that has that file alone can make it, and list them together before any alternative.
- Read each target's current text on disk before proposing an edit to it, and state the edit against what is there.
- A candidate fix to `docs/wf-solver/principles.md` at level 3 has an illustration: for each task the issue cites, the case sets under each reading and a witness input where the readings differ.
- A claim about the corpus rests on approved solvers.
- A complaint is checked against the state that produced it. A ground stated in a commit message or a test docstring is the user's ruling.
- A ground is a source that is quotable or checkable. Verify each claim a reason depends on before stating it. Each reason against a fix states its ground, or the likelihood and what makes it real; do not state a reason whose condition a ground rules out. Reversal of an earlier commit, growth of a file, and re-judgment of a shipped file are not reasons.
- When a reason against a fix has a principled fix of its own, that becomes a candidate fix.
- A candidate fix the program cannot express gets no text.
- A tool that can enforce the rule is made instead of a doc line: prefer a lint check, a runner output, or a subcommand over a sentence a session must remember.
- Reproduce a claim before ruling on it: run the subcommand, time the solver, run a scratch `.dl` through `souffle`. Scratch copies go under `.scratch/retro/` and nowhere else: not the session scratchpad, not `/tmp`, not `programs/`. macOS has no `timeout` command.
- Do not edit any repo file.

## Report

One entry per issue id: the status; for closed, what closed it; for dropped, its level, the principle, norm, or fact the drop rests on, its for and against, and the declined fix; for open, whether it changed a session's work and how, and the candidate fixes, each with its kind, its target file, the smallest edit stated so an agent can make it without the issue in hand, its for, its against, and its illustration where one is called for.
