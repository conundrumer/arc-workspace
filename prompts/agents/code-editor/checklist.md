+ document-size-budget: 4339
* comment: when editing this doc
    - The code editor's checklist: `uv run python scripts/step.py code-editor` prints its items one at a time, by [Code editor](prompts/agents/code-editor.md#code-editor), each as the code editor reaches its step.
    - Acts, each with its section: each step of its work, under the item of that step.

# Copy the tree
- Copy `src/`, `scripts/` and each other directory that holds a file of your part into a new directory under your scratch directory, and note its path in `progress.md`.

# Write the Reuse list
- Read the index of the packages that hold the files your brief gives, as `uv run python scripts/code_index.py <those files>` prints it, and the list of packages that `uv run python scripts/code_index.py` prints, and look first in the modules they lead to.
    * comment: The user's words, session 2384db39-7d21-4d8d-8dda-bfd52bd69360, 2026-10-18T12:50:26Z: "I feel the code or docs should help w navigation? Or is it enough to tell them to look around aroound? But they have to look around every time?"; 12:53:52Z: "Go", which chose "An editor reads the map of the packages it touches before writing code". Ticket 11-1251.
- Write in `progress.md`, under a `Reuse` heading, each thing your items need computed, named, checked or printed, with the existing code anywhere in the repository that does it for the same purpose, or `none found`, whether you call, extend or move that code, and each file outside the files your brief gives that this reuse edits, which you add as you find it.
    * comment: The user's words, session 7fd429fb-e3be-4173-9b0e-df52f507d6a2, 2026-10-15T16:10:02Z: "i think the scope thing is a fundamental problem that makes code editors not reliably stay DRY?"; 16:11:25Z: "1 yes but stage disc"; 16:13:07Z: "misaligned. purpose of stagedisc is to increas instruct compliance". Without this line, code editors wrote a second copy of code that already computed what they needed: tickets 6-1059, 6-1025 and 6-1026. Code editor a3fa90721fd524e00, on hotfix 6-1138, listed under `Reuse` the move of `run_store`'s `SOURCES` into `scripts/kept_reads.py`, whose kept reads need a different file set (ticket 6-1148).

# Find the refactor tickets on your modules
- For each module your brief gives, and each your `Reuse` list gives as edited, find the `refactor` tickets that cite it, as [Writing the code](prompts/agents/code-editor/writing-the-code.md#writing-the-code) gives.
    + xref: prompts/agents/code-editor/writing-the-code.md#writing-the-code

# Split the cited modules
- This part applies where a ticket the step before this one found cites a module you are to edit: [A split](prompts/agents/code-editor/split.md).

## Split each cited module
- Split each module such a ticket cites.

# Write the code
- Write the code your items need, as [Writing the code](prompts/agents/code-editor/writing-the-code.md#writing-the-code) gives.
    + xref: prompts/agents/code-editor/writing-the-code.md#writing-the-code

# Review your diff
- Read your diff for each kind of place [Your diff](prompts/agents/code-editor.md#your-diff) gives, other than many ideas in one place, and fix each defect place that does not stand.
    + xref: prompts/agents/code-editor.md#your-diff

# Judge the document lines your diff touches
* comment: The user's words, session 2384db39, 2026-10-18T15:14:04Z, "File", and 14:41:46Z: "I think more generally there is dependencies between doc and code. In code it's mechanically checked. In docs, No." Ticket 11-1368.
- Run `uv run python -m controlled_markdown xrefs $(git merge-base master HEAD)`, and judge each line it prints against the code your diff leaves. Edit a line that no longer holds where your brief gives that document, and otherwise give it in your report as unfinished.
    + xref: src/controlled_markdown/__main__.py:main

# Run the document check
* comment: The user's words, session 2384db39-7d21-4d8d-8dda-bfd52bd69360, 2026-10-19T21:30:38Z: "If it's fast then yes", which chose the coordinator option that has an editor check its worktree before it reports. Ticket 11-2379.
- Run `uv run python -m controlled_markdown check` with no path, and fix each line it reports in a file your brief lets you edit. Give each other line in your report as unfinished.

# Compare with the before side
- This part applies where your brief asks for a comparison of outputs with what the tree before the change gives, the before side, on a change not for speed: [The before side](prompts/agents/code-editor/before-side.md).

## Make the before side
- Where nothing records the before side, make it.

## Make the comparison
- Make each comparison your brief asks for.

# File your tickets
- File each case noted under the `Questions` heading of your `progress.md`, and each place your diff holds that poses a question, as [Tickets](prompts/agents/code-editor.md#tickets) gives.
    + xref: prompts/agents/code-editor.md#tickets

# Write your report
- Where your brief gives a report file, write your report to it, as [Your report](prompts/agents/code-editor/reply.md#your-report) gives.
    + xref: prompts/agents/code-editor/reply.md#your-report

# Launch the checks
- Run `uv run python scripts/operate.py review <agent id>`, with your own agent id, and do as it prints. Where it prints an Agent call, read [Background agents](prompts/agents/notes/commands.md#background-agents) and make that call. Run it again after each Agent call it prints.
    + xref: scripts/operate_review.py:review
    * if: codex
        - `review` prints nothing for up to 210 s. Start it with `yield_time_ms` 30000, then wait with one `write_stdin` call with empty `chars` and `yield_time_ms` 240000, in the same cell. Make no other poll.

# Report
- Give your final reply, as [Your report](prompts/agents/code-editor/reply.md#your-report) gives, once each agent you launched has replied after your last edit, and where you launched none, once `review` prints that you give it.
    + xref: prompts/agents/code-editor/reply.md#your-report
