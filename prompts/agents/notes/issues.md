# Issue notes
- The statements on filing an issue that more than one entry point inlines.

## pass-issues
- An issue is a doc line or a tool behavior that cost the pass time or tokens, or that made its output wrong; a problem in the task's own files is not one.
- As each issue happens, note it in `.scratch/<task_id>/progress.md`, under a heading that is the name of this pass's report.
- When the report's other sections are settled, file each issue noted under that heading, whether or not an earlier pass hit it, with the task id as `<source>` and your agent's name as `<agent>`.
    - `kind` is `interference` when the pass's output had something wrong because of the issue, whether or not the pass repaired it, and `delay` otherwise.
    - Cite the target as a link as this rendering shows it, a step and the phrase quoted, or a command.
    - Write under `Effect` what the issue cost the pass, and for `interference`, what was wrong in the output and whether it still is.

## Issue files
- File each issue as one file under `issues/new/`, and create that directory when it is absent.
    - Name the files `<unix time>-<source>-<agent>-<i>.md`, with one `date +%s` for all of them, and `<i>` counting them from 1.
    - Write each file in this form:
        ```
        ---
        kind: <kind>
        ---
        # <the target as you cite it>: <what is wrong in it>

        ## Effect
        <its effect>

        ## Evidence
        <the line quoted, or the command and its output, or the grid, as you saw it>
        ```
    - Leave out what the fix should be.

## tracking
- The directories `issues/new/`, `issues/assigned/` and `issues/resolved/` are an issue's statuses, and moving its file between them is its transition.
- After each transition, append a line to the file's log, in the form `<time> <status> [<agent>]: <note>`, with your agent's name as `<agent>`.
    - Write the log as the file's last section, `## Log`, and add that section with its first line.
    - Lead the note of the line into `resolved` with the resolution: `fixed`, `duplicate`, `cannot-reproduce`, `wontfix` or `invalid`.
        - The resolution of a place that is judged and kept is `wontfix`, and the note gives the judgment.
