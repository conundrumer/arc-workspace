+ budget: 11405
* comment: when editing this doc
    - The coordinator loads Carrying a change, Merging a change and A denied merge by the links of its Changes section, at the steps they give; the decision analyst loads Findings an editor leaves by a link of its prompt, where its brief gives findings an editor left.
    - Acts, each with its section:
        - Having an editor write a change, and carrying it through its review and checks: [Carrying a change](#carrying-a-change).
        - Judging the findings and items an editor leaves: [Findings an editor leaves](#findings-an-editor-leaves).
        - Merging a change: [Merging a change](#merging-a-change).
        - Acting on a denied merge call: [A denied merge](#a-denied-merge).

# Change notes
- The statements on carrying a change to the code or the documents from who writes it to its commit, that more than one entry point inlines or links.

## Changes

### Carrying a change
- Have an editor write each change to the code or the documents. The `handbook-expanded` agent writes the part of a change in [lib.dl](programs/lib.dl), in the modules under [lib](programs/lib) and in the solvers under [solvers](programs/solvers), with the accepted gate outputs its items change, and a code editor in the same worktree writes the part in each other file outside the documents. A code editor drafts the text of each `mctx` fragment its code needs, and a doc editor writes that text once the code editors have reported.
- A change is one editor's edit, or one edit for each part the line above splits it into, and each edit that fixes what its review or its checks found.
- A change's ticket is the `change` ticket that gives that change, and a change no `change` ticket gives has no ticket.
- Make the worktree of a change with `uv run python scripts/change_worktree.py <number> <agent>`, with the number of its ticket, or, where it has no ticket, with `uv run python scripts/change_worktree.py --name <name>`, with a name for the change that `--help` allows.
- A change passes when each editor that worked on it has given its final reply, and, unless the coordinator runs it on `hotfix`, when each of these holds as well:
    - Each item an editor reports unfinished is decided, and no item its editors report done needs an item they report unfinished.
    - Where it changes the documents, which include the `///` and `//!` comments of [lib.dl](programs/lib.dl) and of the modules under [lib](programs/lib) and the text of `mctx` fragments: a reply of the doc reviewer that follows the last edit of those changes says no finding stands, and `uv run python -m controlled_markdown check` passes in its worktree.
    - Its items are checked: for each editor other than the `handbook-expanded` agent, an item checker's check of that editor's items finds each of them shown to hold or decided, and that check follows the editor's last report, or sent no message and ends its reply with the line `Worktree: <digest>`, with the digest `uv run python scripts/change_worktree.py --fingerprint <worktree>` prints for the change's worktree now.
- Where the operator's command carries a change past the cost budget its ticket's log gives, the command, in place of the rule above on when a change passes, ends the change's work in flight, merges the change where its editors' latest reports, after one last item check, leave nothing for a decision, and otherwise moves its ticket to `tickets/draft/`.
- Once each editor of a change has reported, where its items are not checked, as the rule above on when a change passes gives, launch an `item-checker` agent to check them, with the latest report of each editor other than the `handbook-expanded` agent that has reported since the last item checker's launch on the change, then a ticket analyst on what its reply leaves for a decision, where it leaves any.
- Where the latest report of the `handbook-expanded` agent on a change does not open with `done` and follows the last ticket analyst's launch on the change, launch a ticket analyst on what that report leaves unfinished.
- Send the findings of a change's checks to the editor that made the change, with SendMessage. A change's reviewer sends its findings to the change's editors, and each editor sends its fixes to that reviewer: relay none of them. Launch a fresh reviewer for a change's first review, and for a later review only where a line below gives one.
- Where the `controlled_markdown` check reports a `quotes` call that a change to the documents broke, send that finding to a code editor in place of the doc editor: launch one, with each call the check reports as an item, to repair as [Prose in code](src/controlled_markdown/writing.md#prose-in-code) gives, and the files of those calls as the files it may edit.
- Where a doc reviewer's reply does not open with `no finding stands`, decide each finding it gives that no editor's reply leaves for a decision as a finding an editor leaves for a decision, by [Findings an editor leaves](#findings-an-editor-leaves). Where a decision gives an edit that no running editor of the change takes, launch an editor with that edit as its item, and a fresh reviewer for the change's next review.
- Where you take up a change that another agent held or whose editors another agent launched, wait until `uv run python scripts/profile_runs.py --running <id>` lists no agent whose launch description or calls show it works on the change, with that agent's id from your brief or a message, or else the agent id in the bracket of the latest `assigned` line of its ticket's log, other than your own, that gives one: run a command whose loop repeats it until then, led by `: 'unattended-wait: <the agents you wait on>';`.
    - Then, where your brief, a message or the latest line of its ticket's log that gives a worktree gives one that stands, continue the change in that worktree, and launch a new editor for each part of the change and a fresh reviewer for its next review.
    - Send no message to an editor or reviewer that other agent launched.
- Run the changes you launch at the same time.

### Findings an editor leaves
- Judge each finding a change's editor leaves with a reason against the change's worktree and that reason: keep it only where it is so and no decision already made rules it out. Record each finding you drop, with its reason, in your reply.
- Where the editor leaves a finding, or an item unfinished, for a decision, decide the question it raises, from the reason the editor gives, as [How a decision is made](prompts/agents/notes/decisions.md#how-a-decision-is-made) gives.
- Send the editor each finding you drop, as dropped, and each you keep that needs no decision, as kept, each with your reason, and each decision, only where a finding you keep or a decision you make gives the editor an edit, or where the change has a doc editor.

### Merging a change
- Where a kept finding of a change raises a decision that goes to the user, leave that change unmerged, and give its branch and worktree with that decision in your reply. The session that gets the user's ruling, or carries out that decision's default, merges the change.
- Before you merge a change, read the diff of each accepted gate output its briefs list, and send each difference there that those briefs do not ask for to the change's editor as a finding of its checks.
- Merge a change only once it passes, with `uv run python scripts/merge_change.py <worktree> -m <message>`, and commit in no other way.
- Where that script exits with status 1, leave the worktree as it is.
- Where that script does not merge the change, act on what it reports:
    - Where it reports that the rebase conflicts and that it moved the branch onto `master`, or a failed check, send what it reports to the change's editor as a finding of its checks.
        - Where the failed check is the gate, give in that finding, for each `DIFF` line that the change's briefs ask for, the accepted output under `tests/gate/accepted/` to update.
    - Where it reports that the rebase conflicts and that the worktree is as it was, put the change in its worktree yourself onto what it rebased it onto, resolving each conflict, then run that script again.
        * comment: Decision a3fdafaa399f0c20c on 6-1429, from the user's words on 6-1417: "it gets sent to you and you handle it". Trial afa894d8d289e9d58 took it as the case below.
    - Where it reports anything else, give the worktree and the script's message in your reply.
- Once a change is merged, and before you close its ticket, run each step and each check its ticket's Scope places at or after the merge, and file each one that fails as a `bug` ticket on the change. Give each such check whose subject is an event that has not happened at the merge in your reply as unfinished, with that reason. Run a check of what a running Claude Code session reads only at its start, such as its hooks, in a `claude -p` session you start in the main worktree after the merge, and not in an agent you launch.
- Once a change is merged, move to `tickets/closed/` its ticket, then each `question` ticket filed on it that still stands outside `tickets/closed/`, with `fixed`, the change's number and the hash `master` stands at after the merge as the note.
- Once a change is merged, close each `refactor` ticket outside `tickets/closed/` whose title ends in `many ideas in one place` and cites a module that a code editor of the change reports it split, with `fixed`, the change's number where it has a ticket, and the hash `master` stands at after the merge as the note. Where that report gives a part of the module as left unsplit, write that part as a log line on the ticket in place of closing it.

### A denied merge
- Where your merge call of a change is denied, move the change's ticket to `tickets/blocked/`, with a note that opens with `user` and gives the call, the denial's text and the worktree.
- Where your merge of a change whose merge call an agent you launched gave as denied goes through, send an operator, once you have moved the change's ticket to `tickets/closed/` as [Merging a change](#merging-a-change) gives, the line `Merged: <number>`, with the change's number, as [Operators](prompts/agents/notes/launching.md#operators) gives.
