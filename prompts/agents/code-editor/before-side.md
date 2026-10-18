+ budget: 1400
* comment: when editing this doc
    - The code editor receives this document from the step command as it enters the before side, once it has written the code and reviewed its diff.
    - Acts, each with its section:
        - Making the before side and comparing and timing against it: [The before side](#the-before-side).

# The before side
- Where your brief or a file records the before side, compare against that record, and run nothing to make the before side.
    * comment: Six briefs from 2026-09-27 to 2026-10-01 had agents run "before" measurements a file already held.
- Make the before side in a detached worktree of `HEAD`:
    - Add it with `git worktree add --detach <dir> HEAD`, with a new directory under your scratch directory as `<dir>`.
    - Run each command of the before side with `--directory <dir>` after its `uv run`, and give each path it writes as an absolute path outside `<dir>`.
    - Remove it with `git worktree remove --force <dir>` once the before side is made.
