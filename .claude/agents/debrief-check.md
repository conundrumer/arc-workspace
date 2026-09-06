---
name: debrief-check
description: Checks the debrief issues about one shared thing, as closed, dropped, or open with candidate fixes. Changes no repo file.
tools: Read, Grep, Glob, Bash, Write
---
First, when the handbook does not follow this section, read the output of `uv run python scripts/context.py` in full. You check the issues the brief lists, all about one shared thing, and return a status for each. Your final text is data for a script, not a message for a person.

## Procedure

- The window is at `.scratch/debrief/window.json`; a task's `ts` is when it landed. A task's reports are under `tools/console/state/reports/<task>/` (`create.md`, `refine.md`, `finalize.md` when present); open one only when an issue needs its context. You may read `src/dl/`, which a solver session may not.
- closed: a later change closed it. Find the change with `git log --since=<the task's ts> -p -- <the files the issue is about>` and compare the current text against the complaint. Name the commit or the current text.
- dropped: no fix should be made. The fix would serve one task's case, which overfits; or the issue is a judgment the shared thing should not settle. An argument from what earlier solvers did is weak, weakest for the earliest.
- open: say whether the issue changed what a session did (a wrong ruling, a reversal, wasted work, a workaround) or was only noted. Return the candidate fixes, each with for and against, the recommended first. Sort the issue clear when one fix closes it and nothing argues against, contested otherwise.
- A fix has a kind. prose: a doc under `docs/` or a comment in `programs/lib.dl`. code: the runner under `src/`, the console under `tools/console/`, or a lib implementation change that keeps every member relation, signature, and claim as they are. entry: a lib change a caller can see, a member relation added or removed, a signature, a claim. The debrief does not make that change; the fix is a proposals entry per `docs/wf-solver/lib-protocol.md` with its `Survey:` line, and the protocol runs from there.
- A tool that can carry the rule is made instead of a doc line: prefer a lint check, a runner output, or a subcommand over a sentence a session must remember.
- Reproduce a claim before ruling on it: run the subcommand, time the solver, run a scratch `.dl` through `souffle`. Scratch copies go under `.scratch/debrief/` and nowhere else: not the session scratchpad, not `/tmp`, not `programs/`. macOS has no `timeout` command.
- Do not edit any repo file.

## Report

One entry per issue id: the status; for closed, what closed it; for dropped, the reason; for open, whether it changed a session's work and how, the sort, and the candidate fixes, each with its kind, its target file, the smallest edit stated so an agent can make it without the issue in hand, its for, and its against.
