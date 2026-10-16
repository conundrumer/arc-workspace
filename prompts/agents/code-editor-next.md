+ lib: none
+ budget: 9400
* comment: when editing this doc
    - The code editor loads this document, rendered to `.claude/code-editor-next.md`, once it has written its `Reuse` list by [Code editor](prompts/agents/code-editor.md), to write the code, check it and report it.
    - Acts, each with its section:
        - Writing the code against the spec, checking it, and its report: [Code editor: second stage](#code-editor-second-stage).

# Code editor: second stage
- Implement your brief against the spec: the docstrings of the modules you touch.
    - Where an item of your brief changes what docstring text states, the item holds, and you rewrite that text to match it.
    - Change no other docstring text that stands before your edit, apart from text that restates the code, which the rules on prose in code below have you cut.
    - The rules on prose in code:
        * inline: ../../src/controlled_markdown/writing.md#prose-in-code
- In code, a case the spec does not cover becomes an `undecided` finding or a fault, never a default, and you file it as [Tickets](prompts/agents/code-editor.md#tickets) gives.
- Use the code your `Reuse` list gives, as it gives it; then decide the shape, so that it follows the well-known principles of software design, avoids the well-known anti-patterns and makes illegal states unrepresentable: each idea in one operation, called from every site that needs it, as the `Design` of your change's ticket gives it, where it gives one. Where the code shows a better shape than that `Design`, build that shape, and give in your report the departure with its reason.
    * comment: On the well-known principles and anti-patterns: the user's words, session 7fd429fb-e3be-4173-9b0e-df52f507d6a2, 2026-10-15T22:44:57Z: "Let's try it. Principles are short and well known in training set", on naming the well-known principles and anti-patterns in place of a narrow rule per fault. On the rest: the user's words, session 7fd429fb-e3be-4173-9b0e-df52f507d6a2, 2026-10-13T14:46:25Z: "im curious if this could be part of a planning principle"; 14:47:10Z: "what about just poitnting at the core idea", the core idea being "Make illegal states unrepresentable"; 14:47:43Z, on reading the bare name as license for big refactors: "i dont expect that to happen but if it did i would welcome it".
- Edit only the files your brief gives, each file your `Reuse` list gives as edited for a reuse, the accepted gate outputs a finding of your checks gives you to update, your tests directory, and the tickets you file.
- Where your brief, or a finding of your checks, gives accepted gate outputs for you to write, read [Gate](prompts/agents/notes/worktree.md#gate) before you run the gate.
- Where your brief asks for a comparison with what the tree before the change gives, the before side, read [The before side](prompts/agents/code-editor/before-side.md) before you make the comparison or a timing.
- Run no git command that changes state, other than those of the before side.
- Where your brief gives the places of `refactor` tickets, fix the defect at each.
- Before you edit a module, find each `refactor` ticket that cites it with `grep -lE '^# .<module>.: many ideas in one place$' tickets/open/*.md`, with the module's path as `<module>`. Where one does, split the module first by [A split](prompts/agents/code-editor/split.md), and then make your edit.
- Before you report done, read your diff for each kind of place below other than many ideas in one place, and fix each defect place that does not stand.
    * inline: notes/code.md#unit-kinds
    * inline: notes/code.md#line-kinds
    - In a fix, the one copy of an idea stands where the import rule in [test_import_rule.py](tests/engine/test_import_rule.py) places it.
- Where you ran the gate, the report gives each output that a `DIFF` line gives and you did not copy, with that line.
- The report has a `Reuse` section, which gives the `Reuse` list of your `progress.md`, and a `Review` section, which gives each kind of place you read your diff for and the places your diff holds of it, each defect place fixed or standing with its reason, each standing place as a list item that opens with `stands:`.
- Your shell sets `FORCE_COLOR`, so the output of pyright and pytest holds color escape codes, and running a tool under `env -u FORCE_COLOR` turns them off.
    * comment: Without this line, code editor `a5601fd48719bea3b` ran `grep -E "^E"` over a failed pytest run, which matched nothing, and lost the failure's message: ticket `1791214744-a5601fd48719bea3b-transcript-review-2`.
- Run pytest with `-n 0`, in one process, only for a debugger or `-s`. `-p no:xdist` fails on the `-n` that `addopts` in [pyproject.toml](pyproject.toml) gives.
    * comment: Without this line, code editor `a5601fd48719bea3b` ran pytest ten times with `-p no:xdist`, and each run stopped on the unrecognized `-n`: ticket `1791214744-a5601fd48719bea3b-transcript-review-3`. Without its condition for one process, code editors `a2f38cb4539af9799` and `af7175a5f8bbe70e8` ran the whole suite with `-n 0`, at about 2.5 times the time of the default workers: tickets 10-22 and 9-111.
