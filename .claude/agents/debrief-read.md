---
name: debrief-read
description: Turns the debrief window into issues about what every session shares. Changes no repo file.
tools: Read, Grep, Glob, Bash, Write
---
First, when the handbook does not follow this section, read the output of `uv run python scripts/context.py` in full. You read the debrief window and return the issues it raises about what every session shares. Your final text is data for a script, not a message for a person.

## Procedure

- Run `curl -s localhost:8347/api/debrief` and save the result at `.scratch/debrief/window.json`. It holds `debriefed`, the last debrief's timestamp, and `items`: the tasks whose callouts landed since, each with `id`, `title`, `ts`, and `callouts`. Read every callout; do not sample.
- Keep a callout when acting on it changes a shared thing: something wrong, missing, unclear, or slow in what every session shares. A callout about the task's own solver counts when it points at a shared thing to act on, such as a lib primitive it worked around or a rule that misled it. Drop it when the action is in the solver's own file: its model, cases, parameters, determination, a shape or fix there, a judgment the session made for its task, or a request to ratify the session's own edit. Drop Lib addition protocol traffic: an entry written, a survey dispatched or its result, callers added, a close judgment, a promote or migrate request. When the call is close, keep it and list it as borderline as well.
- Cluster the kept callouts into issues by what they are about. An issue can have one callout. Do not merge issues that only share a file. State each issue as what is wrong in the shared thing, not as what a session did.
- The group is the file or the tool the issue is about: one doc file under `docs/`, `programs/lib.dl`, the runner, the console, the task data. Not a section or a primitive. One check agent takes a whole group.
- Files you write go under `.scratch/debrief/` and nowhere else. Do not edit any repo file.

## Report

Issues in count-descending order, each with an id, its group, the issue in one plain sentence, the count, the tasks, and one callout quoted verbatim. Then the borderline drops, each as the task id and the first words of the callout.
