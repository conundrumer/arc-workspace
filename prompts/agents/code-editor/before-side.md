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
- Run no command only to time or profile it, on either side, and build no script that replays a run for a timing. Take each timing and each profile from a run your work makes anyway (your tests, your checks, the gate, a command your items have you run).
    * comment: The user's words, session 2384db39, 2026-10-18T13:32:25Z, "Go", on the coordinator's proposal that an editor on a speed change run no baseline or comparison and time only the runs its work does anyway; the user's ruling "Don't run a baseline or a comparison run; time and profile the runs you do anyway", "There is no exception". Code editors of 9-1351 and 11-1177 ran `profile_call.py` replays for minutes only to time.
    - Where a record gives the before side's seconds, compare against it. Where none does, the timing of the after side stands alone, with no run of the before side.
