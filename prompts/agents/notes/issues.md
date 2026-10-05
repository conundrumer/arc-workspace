# Issue notes
- The statements on filing an issue that more than one entry point inlines.

## pass-issues
- An issue is a doc line or a tool behavior that cost the pass time or tokens, or that made its output wrong, or a step that a line below has you file a `delay` issue for; a problem in the task's own files is not one.
- As each issue happens, note it in `.scratch/<task_id>/progress.md`, under a heading that is the name of this pass's report.
- When the report's other sections are settled, file each issue noted under that heading, whether or not an earlier pass hit it, with the task id as `<source>` and your agent's name as `<agent>`.
    - Give each issue the kind `interference` or `delay`.
    - Cite the target as a link as this rendering shows it, a step and the phrase quoted, or a command.
    - Write under `Effect` what the issue cost the pass, and for `interference`, what was wrong in the output and whether it still is.

## Issue files
- Where your instructions, your brief or a later message ask you to file an issue, file it with `uv run python scripts/file_issue.py`, in the form its `--help` gives.
    - Where no other line gives them, `<agent>` is your agent's name, and `<source>` is a short name for your work.
    - Where no other line gives an issue's kind, give it one of these:
        - `interference`: something in your output was wrong because of the issue, whether or not you repaired it.
        - `delay`: the issue cost time or tokens only.
        - `undecided`: a case your rules do not cover, or a place that poses a question.
    - Write under `Evidence` the line quoted, or the command and its output, or the grid, as you saw it.
    - Leave out what the fix should be.
- File a `delay` issue for each step of your work whose run time is far out of proportion to the work the step does.

## tracking
- The directories `issues/new/`, `issues/assigned/` and `issues/resolved/` are an issue's statuses, and moving its file between them is its transition.
- After each transition, append a line to the file's log, in the form `<time> <status> [<agent>]: <note>`, with your agent's name as `<agent>`.
    - Write the log as the file's last section, `## Log`, and add that section with its first line.
    - Lead the note of the line into `resolved` with the resolution: `fixed`, `duplicate`, `cannot-reproduce`, `wontfix` or `invalid`.
        - The resolution of a place that is judged and kept is `wontfix`, and the note gives the judgment.
