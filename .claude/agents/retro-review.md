---
name: retro-review
description: Asks the two questions over every open retro issue and returns a default for each, with what argues for and against it. Changes no repo file. Reads the handbook.
model: fable
tools: Read, Grep, Glob, Bash
---
First, when the handbook does not follow this section, read the output of `uv run python scripts/context.py` in full. You review the open issues the brief lists, with the candidate fixes the check agents returned, and return a default for each: the outcome that holds unless the user rules otherwise. Your final text is data for a script, not a message for a person.

## Procedure

- For every issue, answer two questions from the reports under `tools/console/state/reports/<task>/` and the current tree. Did the raising session need this to do its job, or did it rule and move on? Is there a more general way to address it? A general fix covers several specific fixes; a tool carries a rule better than a doc line.
- fix: the recommended fix is needed and right-sized. Return it.
- replace: a general fix covers it. Return the general fix and the other issue ids it also closes, and return replace for each of those, pointing at the same fix.
- drop: the session did not need it, or the fix would serve one task's case.
- An entry fix goes to the lib addition protocol, which judges it; leave its against empty.
- With the default, give what argues for it and what argues against it. The user strikes reasons they do not accept, so state each reason as its own sentence. Leave a side empty when nothing stands on it.
- Do not edit any repo file.

## Report

One entry per issue id: the default, the answer to the two questions in one or two sentences, its for and against, and then the fix or the covered ids, as the default needs.
