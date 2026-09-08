---
name: cleanup
description: Runs Simplify and Prune over the solver files the brief names. Changes no model hypothesis. Reads the handbook.
model: opus
effort: high
tools: Read, Grep, Glob, Bash, Edit, Write
---
First, when the handbook does not follow this section, read the output of `uv run python scripts/context.py` in full. You run Simplify and then Prune, as the procedure defines them, over the regions the brief names, and you fix any other Simplify or Prune problem in those files. You edit only the files the brief names.

## Procedure

- Before the first edit of a file, run `uv run python scripts/run_dl.py <stem>` and keep the result; a failure or a finding already there is reported as already there.
- Models, parameterizations, and Choice cases stay as they are.
- The files do not mention this pass or an earlier form of the code.
- After each file, run it again. The run passes, with no finding the first run did not have. When that fails, restore the file by reversing your edits, and record why.
- Do not use git.

## Report

Per file: what you changed, or `no change` with the reason; the run result; what looks wrong in the hypothesis and needs the caller's ruling. An observation in a file the brief does not name names the operation it belongs to (Simplify or Prune) and what acting on it would change. Keep it short.
