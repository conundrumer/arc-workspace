+ budget: 7266
* comment: when editing this doc
    - Readers: the editors of a change inline its sections other than Gate, which they link for writing accepted gate outputs, the doc reviewer inlines the sections on its worktree, the ticket analyst, the draft analyst, the decision analyst and the ticket reviewer inline the one on another agent's worktree, and the coordinator links that one.
    - Acts, each with its section:
        - Later findings and requests: [editor-messages](#editor-messages), and, for the findings left unfixed in the editor's report, [An editor's report on a change](prompts/agents/notes/launching.md#an-editors-report-on-a-change).
        - Finding the worktree: [worktree](#worktree).
        - Running commands there: [worktree-commands](#worktree-commands).
        - Another agent's worktree: [Re-invoked in another agent's worktree](#re-invoked-in-another-agents-worktree).
        - Writing accepted gate outputs: [Gate](#gate).

# Worktree notes
- The statements on working in a worktree, that more than one entry point inlines or links.

## editor-messages
- A later message may give a doc reviewer's findings on your change, or findings of your checks. Check each against the worktree, and fix each one that holds and needs no decision. Fix each finding a later message gives as kept, and apply each decision it gives.
- Where a doc reviewer has sent findings on your change, before each reply to a later message, send that reviewer by SendMessage, at the agent id its message came from, each item of that later message with what you did on it, or, for a finding you left, why you left it.
- Message only the agents a line of your documents has you message, each with only what that line gives.

## worktree
- The worktree of the change you work on is the one your brief gives, or, where the form of your brief gives none, the main tree.
- Where your brief gives the number of your change's ticket, `uv run python scripts/file_ticket.py path <number>` prints that ticket's path.
    + xref: scripts/file_ticket.py:SUBCOMMANDS
- A later message may add a request to the change, and that request is part of what the change is to do.

## worktree-commands
- Run each command in the worktree of your change, other than each call of `scripts/step.py` on your own checklist, which you run in the main tree, the parent of the directory `git rev-parse --path-format=absolute --git-common-dir` prints, and take each path in the repo from the worktree of your change, apart from a path under `tickets/`, which you take from the main tree.
    + xref: scripts/step.py:main
    * comment: "each call of `scripts/step.py` on your own checklist" stays: code editor a4f7e3c9cc0837cd0, running `step.py code-editor write-the-code` in its worktree, whose `HEAD` lacked commits of master, got `no agent has a checklist` for a step its context gave (ticket 9-697, session 129de8fc). It stands right after the main clause, in the clause's own exception: with it in the line's last clause, doc editor ac084c67e1eab54c3 read "Run each command in the worktree" as covering it, and ran `step.py doc-editor ...` in its worktree (ticket 11-1326, session 2384db39, its answer of 2026-10-18).
- Run no command and no script that replays a run only to time or profile it. Take each timing and each profile from a run your work makes anyway (your tests, your checks, the gate, a command your items have you run). Where a record gives the figure of the tree before the change, compare against it, and where none does, the figure of the tree after the change stands alone.
    * comment: The user's words, session 2384db39, 2026-10-18T13:32:25Z, "Go", on the coordinator's proposal that an editor on a speed change run no baseline or comparison and time only the runs its work does anyway; the user's ruling "Don't run a baseline or a comparison run; time and profile the runs you do anyway", "There is no exception". Code editors of 9-1351 and 11-1177 ran `profile_call.py` replays for minutes only to time. At 13:35:51Z, "Go", on "The rule needs to be in the code editor's starting context, `code-editor.md`, so every editor has it": this section is inlined by `code-editor.md`. Ticket 11-1279.
- On a change for speed, run nothing on the tree before the change. On another change, run the tree before the change only for a comparison of outputs your brief asks for.
    * comment: The user's words, session 2384db39, 2026-10-18T13:32:25Z, "Go", on the coordinator's option "an editor on a speed change runs no baseline or comparison, and times only the runs its work does anyway". Ticket 11-1279.

## Re-invoked in another agent's worktree
- From an environment update that gives as your primary working directory a linked worktree other than the one you run your commands in, until one gives your working directory at start as your primary working directory, a command of yours runs in that other worktree, so a relative path resolves against it and a script runs from its copy, and an agent you launch starts in it and can run no command once it is removed. Until then, whatever another line of your documents gives, make no call but these:
    * comment
        - The reason for agents stays by the decision on change 2-137 that has the line state it: doc reviewer a555c16716d62355f, launched by operator a017a43d837e9118a at its L1685 while in agent-ae0647acd7a9f64e4, had every Bash call refused once that worktree was removed at the operator's L1691.
        - The reason for commands stays: under a line that limited only launches, operator abc04d75924b0510d, re-invoked by a message with no environment update while in agent-a555c4a4dee7909c0, ran `merge_change.py` on a relative path to that worktree at its L491, which the script refused: ticket 2-498.
    - A wait for a command of yours to finish.
    - At that update, and each time something re-invokes you or the completion of an agent you launched by this line reaches you until then: once each command you started has finished, other than one your documents have you leave running when you end your turn, launch a `general-purpose` agent in the background, with `haiku` as the Agent call's `model` and a brief that asks only for a wait and then a reply: one foreground Bash call that runs `: 'unattended-wait: in the worktree of another agent'; sleep 60`, then the reply, unless an agent you launched by this line still runs, and end your turn with no other call.
        * comment
            - "with no other call" stays: with "end your turn as soon as you have launched it" alone, operator a017a43d837e9118a ran `pwd` after the launch at its L1813, the completion reached it mid-turn, and nothing re-invoked it for five and a half hours: ticket 2-137.
            - "At that update" stays: with the launch line opening "Once each command you started has finished", under the line "Act by the line below each time one of these happens:" alone, ticket reviewer a0ea60e7c262c7daa, in a run where neither event happened, read the launch as a step of every run, and reported that its documents told it to launch such an agent before it ended its turn: ticket 2-291.
- Once the environment update that gives your working directory at start has come, continue your work, with the requests of each message that reached you before it.

## Gate
- `uv run python scripts/gate.py <out-dir> [cmd ...]` is the gate: it runs the gate commands it is given on the fixed inputs under `tests/gate/` that `gate.py --help` lists, and compares their outputs with the accepted ones.
    + xref: scripts/gate.py:main
- Run it only to write the accepted gate outputs your brief lists and those a finding of your checks gives to update, with the commands whose outputs those are as `cmd` and a new directory under your scratch directory as `<out-dir>`.
    - Where your brief gives those outputs as the ones that a `DIFF` of the gate your items cause gives, run it with no `cmd` and with `--affected <base>`, where `<base>` is the commit `git merge-base HEAD master` prints in your worktree.
        + xref: scripts/gate.py:main
- Copy each of those outputs from `<out-dir>/gate/new/` to its accepted file under `tests/gate/accepted/`.
