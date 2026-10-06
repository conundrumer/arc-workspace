# Worktree notes
- The statements on working in a worktree, that more than one entry point inlines or links.

## editor-messages
- Your final reply goes to the agent that launched you: the agent whose id your brief gives for it, or the coordinator where your brief gives none.
- A later message may give a doc reviewer's findings on your change, or findings of your checks. Check each against the worktree, fix each one that holds and needs no decision, and state each other one in your reply, with why you left it. Fix each finding a later message gives as kept, and carry out each decision it gives.
- Where a doc reviewer has sent findings on your change, send that reviewer your fixes with SendMessage before each reply to a later message, to the agent id its message came from, with each finding a later message gave as kept, each it gave as dropped with its reason, each finding you left for a decision, each decision you carried out, and each request a later message added. Message no other agent, apart from the agent that launched you, with your final reply alone.

## worktree
- The worktree of the change you work on is the one the message that launches you gives, or, where it gives none, your working directory at start.
- Where your brief gives the number of your change's ticket, `uv run python scripts/file_ticket.py path <number>` prints that ticket's path.
- A later message may add a request to the change, and that request is part of what the change is to do.

## worktree-commands
- Run each command in the worktree of your change, and take each path in the repo from it, apart from a path under `tickets/`, which you take from the main tree, the parent of the directory `git rev-parse --path-format=absolute --git-common-dir` prints.

## worktree-isolation
- The harness may refuse a compound Bash command that it cannot verify runs git only inside the worktree, such as one that writes a file through a heredoc, runs `printf` with a computed format, or runs git inside a command substitution. Write such a file with the Write or Edit tool, run such a git call as a simple command in a Bash call of its own, and run the rest of the command in a Bash call of its own.
    * comment: The refusal message reaches an agent only after the refused call. Without this line, code editor `a16cb9e50afdd6691` had five such commands refused and retried each split: ticket `1791218737-a16cb9e50afdd6691-transcript-review-3`. With only the heredoc and `printf` forms named, doc editor `a0c48e5b4d30194d1` had a command with git inside a command substitution refused and split it: ticket `1791220161-a0c48e5b4d30194d1-transcript-review-1`. The forms after "such as" stay because a reader cannot tell from the condition alone which commands the harness cannot verify.

## Re-invoked in another agent's worktree
- Act by the line below each time one of these happens:
    - An environment update gives as your primary working directory a linked worktree other than the one you run your commands in.
    - The harness refuses a Bash call with a text that opens "This agent is isolated in the worktree" and gives a worktree other than your working directory at start.
- After such an event, once each command you started has finished, other than one your documents have you leave running when you end your turn, launch a `general-purpose` agent in the background with a brief that asks only for a reply, end your turn right after the launch, with no other call, and continue your work when its completion re-invokes you.
    * comment
        - "with no other call" stays: with "end your turn as soon as you have launched it" alone, operator a017a43d837e9118a ran `pwd` after the launch at its L1813, the completion reached it mid-turn, and nothing re-invoked it for five and a half hours: ticket 2-137.
        - "After such an event" stays: with the launch line opening "Once each command you started has finished", under the line "Act by the line below each time one of these happens:" alone, ticket reviewer a0ea60e7c262c7daa, in a run where neither event happened, read the launch as a step of every run, and reported that its documents told it to launch such an agent before it ended its turn: ticket 2-291.
    - Where its completion reaches you before you have ended your turn, launch another the same way.
    - Until a re-invocation restores your working directory at start, launch no other agent: an agent you launch before then starts in the other worktree, and once that worktree is removed, it can run no command.
        * comment: The reason stays by the decision on change 2-137 that has the line state it: doc reviewer a555c16716d62355f, launched by operator a017a43d837e9118a at its L1685 while in agent-ae0647acd7a9f64e4, had every Bash call refused once that worktree was removed at the operator's L1691.

## gate
- `uv run python scripts/gate.py --outputs-only <out-dir> [cmd ...]` is the gate: it runs the gate commands it is given on the fixed inputs under `tests/gate/` that `gate.py --help` lists, and compares their outputs with the accepted ones.
- Run it only to write the accepted gate outputs your brief lists and those a finding of your checks gives to update, with the commands whose outputs those are as `cmd` and a new directory under your scratch directory as `<out-dir>`.
- Copy each of those outputs from `<out-dir>/gate/new/` to its accepted file under `tests/gate/accepted/`, and run no `gate.py --accept`.
