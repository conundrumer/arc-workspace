# Worktree notes
- The statements on working in a worktree, that more than one entry point inlines or links.

## editor-messages
- Your final reply goes to the agent that launched you: the agent whose id your brief gives for it, or the coordinator where your brief gives none.
- A later message may give a doc reviewer's findings on your change, or findings of your checks. Check each against the worktree, fix each one that holds and needs no decision, and state each other one in your reply, with why you left it. Fix each finding a later message gives as kept, and carry out each decision it gives.
- Where a doc reviewer has sent findings on your change, send that reviewer your fixes with SendMessage before each reply to a later message, to the agent id its message came from, with each finding a later message gave as kept, each it gave as dropped with its reason, each finding you left for a decision, each decision you carried out, and each request a later message added. Message no other agent, apart from the agent that launched you, with your final reply alone, and the sender of a message that asks you to send it an answer by SendMessage, with that answer.

## worktree
- The worktree of the change you work on is the one your brief gives, or, where the form of your brief gives none, the main tree.
- Where your brief gives the number of your change's ticket, `uv run python scripts/file_ticket.py path <number>` prints that ticket's path.
- A later message may add a request to the change, and that request is part of what the change is to do.

## worktree-commands
- Run each command in the worktree of your change, and take each path in the repo from it, apart from a path under `tickets/`, which you take from the main tree, the parent of the directory `git rev-parse --path-format=absolute --git-common-dir` prints.

## Re-invoked in another agent's worktree
- Act by the lines below each time an environment update gives as your primary working directory a linked worktree other than the one you run your commands in.
- After such an event, until an environment update gives your working directory at start as your primary working directory, make no call other than a wait for a command of yours to finish and the calls the line below gives, whatever another line of your documents gives: until then, a command of yours runs in the other worktree, so a relative path resolves against it and a script runs from its copy, and an agent you launch starts in it and can run no command once it is removed.
    * comment
        - The reason for agents stays by the decision on change 2-137 that has the line state it: doc reviewer a555c16716d62355f, launched by operator a017a43d837e9118a at its L1685 while in agent-ae0647acd7a9f64e4, had every Bash call refused once that worktree was removed at the operator's L1691.
        - The reason for commands stays: under a line that limited only launches, operator abc04d75924b0510d, re-invoked by a message with no environment update while in agent-a555c4a4dee7909c0, ran `merge_change.py` on a relative path to that worktree at its L491, which the script refused: ticket 2-498.
- At such an event, and each time something re-invokes you or the completion of an agent you launched by this line reaches you until then: once each command you started has finished, other than one your documents have you leave running when you end your turn, launch a `general-purpose` agent in the background, with `haiku` as the Agent call's `model` and a brief that asks only for a reply, unless an agent you launched by this line still runs, and end your turn with no other call.
    * comment
        - "with no other call" stays: with "end your turn as soon as you have launched it" alone, operator a017a43d837e9118a ran `pwd` after the launch at its L1813, the completion reached it mid-turn, and nothing re-invoked it for five and a half hours: ticket 2-137.
        - "At such an event" stays: with the launch line opening "Once each command you started has finished", under the line "Act by the line below each time one of these happens:" alone, ticket reviewer a0ea60e7c262c7daa, in a run where neither event happened, read the launch as a step of every run, and reported that its documents told it to launch such an agent before it ended its turn: ticket 2-291.
- Once that environment update has come, carry on your work, with the requests of each message that reached you before it.

## gate
- `uv run python scripts/gate.py --outputs-only <out-dir> [cmd ...]` is the gate: it runs the gate commands it is given on the fixed inputs under `tests/gate/` that `gate.py --help` lists, and compares their outputs with the accepted ones.
- Run it only to write the accepted gate outputs your brief lists and those a finding of your checks gives to update, with the commands whose outputs those are as `cmd` and a new directory under your scratch directory as `<out-dir>`.
    - Where your brief gives those outputs as the ones that a `DIFF` of the gate your items cause gives, run it with no `cmd` and with `--affected <base>`, where `<base>` is the commit `git merge-base HEAD master` prints in your worktree.
- Copy each of those outputs from `<out-dir>/gate/new/` to its accepted file under `tests/gate/accepted/`, and run no `gate.py --accept`.
