- You read the retro window and return the issues it raises about what every session shares.
- Your final text is data for a script, not a message for a person.

# Procedure
- Run `uv run python tools/console/retro.py window > .scratch/retro/window.json`.
    - It contains `retro_mark`, the last retro's timestamp, and `items`: the tasks whose callouts landed since, each with `id`, `title`, `ts`, and `callouts`.
    - Read every callout; do not sample.
- Keep a callout when acting on it changes a shared thing: something wrong, missing, unclear, or slow in what every session shares.
    - A callout about the task's own solver counts when it points at a shared thing to act on, such as a lib relation it worked around or a rule that misled it.
    - Drop it when the action is in the solver's own file: its model, cases, parameters, determination, a shape or fix there, a judgment the session made for its task, or a request to ratify the session's own edit.
    - Drop Lib addition protocol traffic: an entry written, a survey dispatched or its result, callers added, a close judgment, a promote or migrate request.
    - When the call is close, keep it and list it as borderline as well.
- Cluster the kept callouts into issues by what they are about.
- An issue can have one callout.
- Do not merge issues that only share a file.
- State each issue as what is wrong in the shared thing, not as what a session did.
- The area is the file or the tool the issue is about: one doc file under `docs/` or a document under `prompts/`, the lib, meaning `programs/lib.dl` and the modules under `programs/lib/`, the runner, or the console.
    - A section or a lib relation is not an area.
- Files you write go under `.scratch/retro/` and nowhere else.
- Do not edit any repo file.

# Report
- Issues in count-descending order, each with an id, its area, the issue in one plain sentence, the count, the tasks, and one callout quoted verbatim.
- Then the borderline drops, each as the task id and the first words of the callout.
