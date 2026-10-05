# Worktree notes
- The statements for an agent that works on a change in its worktree, that more than one entry point inlines.

## editor-messages
- Your final reply goes to the agent that launched you: the agent whose id your brief gives for it, or main where your brief gives none.
- Where your brief gives the number of your change's ticket and no items, the ticket's Intent gives the items of your brief, and its Scope gives the files your brief gives, limited to the part your brief gives as yours where it gives one.
- A later message may give a doc reviewer's findings on your change. Check each against the worktree, fix each one that holds and needs no decision, and give each other one in your report, with why you left it. Fix each finding a later message gives as kept, and carry out each decision it gives.
- Where a doc reviewer has sent findings on your change, send that reviewer your fixes with SendMessage before each report to a later message, to the agent id its message came from, with each finding a later message gave as kept, each it gave as dropped with its reason, each finding you left for a decision, each decision you carried out, and each request a later message added. Message no other agent, apart from the agent that launched you, with your final reply alone.
- Run no git command that changes state.

## worktree
- The worktree of the change you work on is the one the message that launches you gives, or, where it gives none, your working directory at start. Run each command in it, and take each path in the repo from it, apart from a path under `tickets/`, which you take from the main tree, the parent of the directory `git rev-parse --path-format=absolute --git-common-dir` prints.
- Where your brief gives the number of your change's ticket, `uv run python scripts/file_ticket.py path <number>` prints that ticket's path.
- A later message may add a request to the change, and that request is part of what the change is to do.

## worktree-isolation
- The harness may refuse a compound Bash command that it cannot verify runs git only inside the worktree, such as one that writes a file through a heredoc, runs `printf` with a computed format, or runs git inside a command substitution. Write such a file with the Write or Edit tool, run such a git call as a simple command in a Bash call of its own, and run the rest of the command in a Bash call of its own.
    * comment: The refusal message reaches an agent only after the refused call. Without this line, code editor `a16cb9e50afdd6691` had five such commands refused and retried each split: ticket `1791218737-a16cb9e50afdd6691-transcript-review-3`. With only the heredoc and `printf` forms named, doc editor `a0c48e5b4d30194d1` had a command with git inside a command substitution refused and split it: ticket `1791220161-a0c48e5b4d30194d1-transcript-review-1`. The forms after "such as" stay because a reader cannot tell from the condition alone which commands the harness cannot verify.

## gate
- `uv run python scripts/gate.py --outputs-only <out-dir> [cmd ...]` is the gate: it runs the gate commands it is given on the fixed inputs under `tests/gate/` that `gate.py --help` lists, and compares their outputs with the accepted ones.
- Run it only to write the accepted gate outputs your brief lists and those a finding of your checks gives to update, with the commands whose outputs those are as `cmd` and a new directory under your scratch directory as `<out-dir>`.
- Copy each of those outputs from `<out-dir>/gate/new/` to its accepted file under `tests/gate/accepted/`, and run no `gate.py --accept`.
