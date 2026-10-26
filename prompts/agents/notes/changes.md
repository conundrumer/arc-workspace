+ document-size-budget: 15345
* comment: when editing this doc
    - The coordinator loads Making a change, Merging a change and A denied merge by the links of the [Changes](prompts/agents/notes/ops.md#changes) section of Ops, at the steps they give; the decision analyst loads Findings an editor leaves by a link of [An editor's findings](prompts/agents/decision-analyst/findings.md), where its brief gives findings an editor left.
    - Acts, each with its section:
        - Having an editor write a change, and taking it through its review and checks: [Making a change](#making-a-change).
        - Judging the findings and items an editor leaves: [Findings an editor leaves](#findings-an-editor-leaves).
        - Merging a change: [Merging a change](#merging-a-change).
        - Acting on a denied merge call: [A denied merge](#a-denied-merge).

# Change notes
- The statements on a change to the code or the documents, from who writes it to its commit, that more than one entry point inlines or links.

## Changes

### Making a change
- Have an editor write each change to the code or the documents. The `handbook-expanded` agent writes the part of a change in [lib.dl](programs/lib.dl), in the modules under [lib](programs/lib) and in the solvers under [solvers](programs/solvers), and a code editor in the same worktree writes the part in each other file outside the documents. A code editor drafts the text of each `mctx` fragment its code needs, and a doc editor writes that text once the code editors have reported.
- A change is one editor's edit, or one edit for each part the line above splits it into, and each edit that fixes what its review or its checks found.
- A change's ticket is the `change` ticket that gives that change.
- Make the worktree of a change with `uv run python scripts/change_worktree.py <number> <agent>`, with the number of its ticket, or, where it has no ticket, with `uv run python scripts/change_worktree.py --name <name>`, with a name for the change that `--help` allows.
    + xref: scripts/change_worktree.py:main
- In the rules on when a change passes, the documents include the `///` and `//!` comments of [lib.dl](programs/lib.dl) and of the modules under [lib](programs/lib) and the text of `mctx` fragments.
- A change that the coordinator runs on `hotfix`, and a change whose merge the user asks for, passes when each editor that worked on it, where any did, has given its final reply.
- Any other change passes when each of these holds:
    - Each editor that worked on it has given its final reply.
    - Each item an editor reports unfinished is decided.
    - No item its editors report done needs an item they report unfinished.
    - Where it changes the documents, a reply of the doc reviewer that follows the last edit of those changes says no finding stands, or a decision analyst launched on its reply at the round cap has replied.
        + xref: src/operations/reports.py:NO_FINDING
    - Where it changes the documents, `uv run python -m controlled_markdown check` passes in its worktree.
    - Its items are checked: for each editor other than the `handbook-expanded` agent, an item checker's check that follows that editor's last report, or that sent no message and ends its reply with the line `Worktree: <digest>`, with the digest `uv run python scripts/change_worktree.py --fingerprint <worktree>` prints for the change's worktree now, unless that editor reported after the launch of a decision analyst on the change that followed that check, finds each of that editor's items shown to hold or decided.
        + xref: scripts/change_worktree.py:main
    - Where a code editor or the `handbook-expanded` agent worked on it, a design reviewer launched after each such editor's first report since its ticket's last move out of `tickets/draft/`, and after each report since then of an editor's resolution of a rebase conflict in a path that is not a document, and after each such resolution you make yourself, has given its final reply.
    - Each `question` ticket that such a design reviewer filed with `change` as `<domain>` and the change's number as `<subject>` is settled, or a decision analyst launched after its filing has replied.
- Where a change that the operator's command runs spends more subscription dollars, Claude and Codex together, than the budget in its ticket's log, where a measured part alone, Claude or Codex, that passes the budget establishes it while the other is unknown, the command writes once per take a line to that log that gives the budget and the spend, and the change goes on, as a change within its budget does, to its item check, its design review and its merge.
    + xref: src/operations/change_budget.py:past_budget, src/operations/change_overrun.py:over_budget
- Once each editor of a change other than a `hotfix` change and a change whose merge the user asks for has reported, where its items are not checked, as the rules above on when a change passes give, launch an `item-checker` agent to check them, with the latest report of each editor other than the `handbook-expanded` agent that has reported since the last item checker's launch on the change, then a decision analyst on what its reply leaves for a decision, where it leaves any.
    - At the same time, on such a change that a code editor or the `handbook-expanded` agent worked on, launch a `design-reviewer` agent, once for each move of its ticket out of `tickets/draft/` and once more after each report of an editor's resolution of a rebase conflict in a path that is not a document and after each such resolution you make yourself, then a decision analyst on the `question` tickets it files with `change` as `<domain>`, where it files any.
    - An item checker, a design reviewer or a decision analyst of the two lines above that an editor of the change launched counts as one you launched: launch it no second time.
- Each kind of review of a built change runs at most the rounds `REVIEW_ROUNDS` in [constants.py](src/operations/constants.py) gives, since its ticket's last move out of `tickets/draft/`.
    + xref: src/operations/constants.py:REVIEW_ROUNDS
    - The findings of a review's last round that block the change go to a decision analyst, and the change goes into no further round of that review.
    - A round of the item check is an item checker's launch.
    - A round of the doc review, or of a review an item has an editor make, is each review its reviewer or editor makes.
    - The brief of a doc reviewer, or of an editor that an item has make a review, gives the rounds it has of that review: one round where an agent of its kind was launched on the change before it since its ticket's last move out of `tickets/draft/`, and otherwise `REVIEW_ROUNDS`.
        + xref: src/operations/briefs.py:review_rounds
    - An item checker launched after the item check's last round makes the check after the review round cap: it checks only the edits that the decision analysts' decisions give, and is no round.
        + xref: src/operations/item_check.py
    - The edits that a decision analyst's decisions on a doc reviewer's reply at the round cap give get the change's next item check: a round of the item check where one remains, and otherwise the check after the review round cap.
        + xref: src/operations/item_check.py
- Where the latest report of the `handbook-expanded` agent on a change does not open with `done` and follows the last decision analyst's launch on the change, launch a decision analyst on what that report leaves unfinished.
- Send the findings of a change's checks to the editor that made the change, with SendMessage. A change's reviewer sends its findings to the change's editors, and each editor sends its fixes to that reviewer: relay none of them. Launch a fresh reviewer for the first review of a change other than a `hotfix` change and a change whose merge the user asks for, and for a later review only where a line below gives one.
- Where the `controlled_markdown` check reports a `quotes` call that a change to the documents broke, send that finding to a code editor in place of the doc editor: launch one, with each call the check reports as an item, to repair as [Prose in code](src/controlled_markdown/writing.md#prose-in-code) gives, and the files of those calls as the files it may edit.
    + xref: src/controlled_markdown/writing.md#prose-in-code
- Where a doc reviewer's reply opens with `at the round cap`, launch a decision analyst on the findings it gives, and launch no reviewer for the change's next review.
    + xref: src/operations/reports.py:AT_CAP
- Where a doc reviewer's reply opens with neither that nor `no finding stands`, decide each finding it gives that no editor's reply leaves for a decision as a finding an editor leaves for a decision, by [Findings an editor leaves](#findings-an-editor-leaves). Where a decision gives an edit that no running editor of the change takes, launch an editor with that edit as its item, and, on a change other than a `hotfix` change and a change whose merge the user asks for, a fresh reviewer for the change's next review.
    + xref: prompts/agents/notes/changes.md#findings-an-editor-leaves, src/operations/reports.py:NO_FINDING
- Where you take up a change that another agent held or whose editors another agent launched, wait until `uv run python scripts/profile_runs.py --running <id>` lists no agent whose launch description or calls show it works on the change, with that agent's id from your brief or a message, or else the agent id in the bracket of the latest `assigned` line of its ticket's log, other than your own, that gives one: run a command whose loop repeats it until then, led by `: 'unattended-wait: <the agents you wait on>';`.
    + xref: scripts/profile_runs.py:parser
    - Then, where your brief, a message or the latest line of its ticket's log that gives a worktree gives one that stands, continue the change in that worktree with the editors your session launched on it since its ticket's last move out of `tickets/draft/`: resume each of them that the usage limit stopped, and, on a change other than a `hotfix` change and a change whose merge the user asks for, launch a fresh reviewer for its next review, and a new editor only for a part of the change that none of them works on.
        * comment: The user's words in the span of request 11-705: "I want agents to resume so they keep context.": ticket 11-741.
    - Send no message to an editor or reviewer that another session launched.
- Run the changes you launch at the same time.

### Findings an editor leaves
- Judge each finding a change's editor leaves with a reason against the change's worktree and that reason: keep it only where it is so and no decision already made rules it out. Record each finding you drop, with its reason, in your reply.
- Where the editor leaves a finding, or an item unfinished, for a decision, decide the question it raises, from the reason the editor gives, as [How a decision is made](prompts/agents/notes/decisions.md#how-a-decision-is-made) gives.
    + xref: prompts/agents/notes/decisions.md#how-a-decision-is-made
- On each part of what the editors leave that you do not decline, send the editor each finding you drop, as dropped, and each you keep that needs no decision, as kept, each with your reason, and each decision, only where a finding you keep or a decision you make gives the editor an edit, where the editor is a doc editor, or where its report gives a finding a doc reviewer sent it as left unfixed.

### Merging a change
- Where a kept finding of a change raises a decision that goes to the user, leave that change unmerged, and give its branch and worktree with that decision in your reply. The session that gets the user's ruling, or applies that decision's default, merges the change.
- Merge a change only once it passes, with `uv run python scripts/merge_change.py <worktree> -m <message>`, and commit in no other way.
    + xref: scripts/merge_change.py:merge_main
- Where that script does not merge the change, act on what it reports:
    - Where it reports that the rebase conflicts and that it moved the branch onto `master`, or a failed check, send what it reports to the change's editor as a finding of its checks.
    - Where it reports that the rebase conflicts and that the worktree is as it was, put the change in its worktree yourself onto what it rebased it onto, resolving each conflict, then run that script again.
        * comment: Decision a3fdafaa399f0c20c on 6-1429, from the user's words on 6-1417: "it gets sent to you and you handle it". Trial afa894d8d289e9d58 took it as the case below.
    - Where it reports anything else, give the worktree and the script's message in your reply.
- Once a change is merged, and before you close its ticket, run each step and each check its ticket's Scope places at or after the merge, and file each one that fails as a `bug` ticket on the change. Give each such check whose subject is an event that has not happened at the merge in your reply as unfinished, with that reason. Run a check of what a running Claude Code session reads only at its start, such as its hooks, in a `claude -p` session you start in the main worktree after the merge, and not in an agent you launch.
- Once a change is merged, move to `tickets/closed/` its `change` ticket, where an agent you launched gave its merge as denied, then each `question` ticket filed with `change` as `<domain>` and its number as `<subject>` that stands untaken or under `tickets/assigned/`, with `fixed`, the change's number and the hash `master` stands at after the merge as the note.
- Once a change is merged, close each `refactor` ticket outside `tickets/closed/` whose title ends in `many ideas in one place` and cites a module that a code editor of the change reports it split, with `fixed`, the change's number where it has a ticket, and the hash `master` stands at after the merge as the note. Where that report gives a part of the module as left unsplit, write that part as a log line on the ticket in place of closing it.

### A denied merge
- Where your merge call of a change is denied, move the change's ticket to `tickets/blocked/`, with a note that opens with `user` and gives the call, the denial's text and the worktree.
- Where your merge of a change whose merge call an agent you launched gave as denied goes through, send an operator, once you have moved the change's ticket to `tickets/closed/` as [Merging a change](#merging-a-change) gives, the line `Op merged: <number>`, with the change's number, as [Operators](prompts/agents/notes/launching.md#operators) gives.
    + xref: prompts/agents/notes/launching.md#operators, prompts/agents/notes/launching.md#an-operators-brief
