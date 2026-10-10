# The before side
- Where your brief or a file records the before side, compare against that record, and run nothing to make the before side.
    * comment: Six briefs from 2026-09-27 to 2026-10-01 had agents run "before" measurements a file already held.
- Where nothing records the before side, make it in a detached worktree of `HEAD`:
    - Add it with `git worktree add --detach <dir> HEAD`, with a new directory under your scratch directory as `<dir>`.
    - Run each command of the before side with `--directory <dir>` after its `uv run`, and give each path it writes as an absolute path outside `<dir>`.
    - Remove it with `git worktree remove --force <dir>` once the before side is made, and before you end your turn.
- A timing your brief asks for is one timed run per job, against the seconds a record gives. Where no record gives the seconds of the before side, run each job once untimed on each side, then time it on the two sides one after the other.
