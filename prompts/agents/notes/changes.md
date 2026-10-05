# Change notes
- The statements on carrying a change to the code or the documents from who writes it to its commit, that more than one entry point inlines or links.

## Changes
- Have an editor write each change to the code or the documents.
- A change is one editor's edit, and each edit that fixes what its review or its checks found.
- A change passes when each code editor that worked on it reports done, and, where it changes the documents, the `///` and `//!` comments of [lib.dl](programs/lib.dl) and of the modules under [lib](programs/lib) among them, when the doc review of those changes leaves no finding that is kept and `uv run python -m controlled_markdown check` passes in its worktree.
- Where you did not launch a change's editor, return the kept findings on that change and the decisions on it in your reply in place of sending them to that editor.
- Send the findings of a change's review and of its checks to the editor that made the change, and that editor's fixes to the reviewer that reviewed it, each with SendMessage. Launch a fresh reviewer only for a change's first review.
- Where you are the operator, have a triage agent judge the findings the editor leaves and decide each one the editor leaves for a decision, and give that agent only those findings, with the editor's reasons. Send the editor the findings triage keeps, as kept, with triage's reasons, and the decisions it returns.
- Where you are not the operator, judge each finding the editor leaves with a reason against the change's worktree, that reason, and [The ladder](prompts/agents/notes/decisions.md#the-ladder): keep it only where it is so, acting on it serves a rung, and no decision already made rules it out. Record each finding you drop, with its reason, in your reply, and send the editor each you keep that needs no decision, as kept, with your reason.
- Where you are not the operator and the editor leaves a finding for a decision, decide the question it raises, from the reason the editor gives, as [How a decision is made](prompts/agents/notes/decisions.md#how-a-decision-is-made) gives, and send the editor the decision.
- Where the `controlled_markdown` check reports a `quotes` call that a change to the documents broke, send that finding to a code editor in place of the doc editor: launch one in the change's worktree, with each call the check reports as an item, to repair as [Prose in code](src/controlled_markdown/writing.md#prose-in-code) gives, and the files of those calls as the files it may edit.
- Where a doc review reports a finding on one of those comments that a code editor wrote, send that finding to a doc editor in place of the code editor, with SendMessage. Where the change has no doc editor, first launch one in the change's worktree, with an Intent that says what those comments' readers need to know, taken from the items of the code editor's brief.
- In each message that sends a reviewer fixes, give what has been settled about the change since its brief, and each request the user added to the change since its brief.
- Launch the first editor of a change with the Agent tool's `isolation: "worktree"`, and take the change's worktree from the Agent tool's completion notification for that editor.
- Give that worktree, by its path, in the brief of each later agent that works on the change.
- Run the changes you launch at the same time.
- Where a kept finding of a change raises a decision that goes to the user, leave that change unmerged, and give its branch and worktree with that decision in your reply. The session that gets the user's ruling, or carries out that decision's default, merges the change.
- Before you merge a change, read the diff of each accepted gate output its briefs list, and send each difference there that no item of those briefs makes to the change's editor as a finding of its checks.
- Merge a change only once it passes, with `uv run python scripts/merge_change.py <worktree> -m <message>`, and commit in no other way.
- Where that script exits with status 1, leave the worktree as it is. Where it reports that the rebase conflicts, run the change again with a new first editor, and give the old worktree and its branch in your reply. Where it reports a failed check, send what it reports to the change's editor as a finding of its checks. Otherwise, give the worktree and the script's message in your reply.
    - Where the failed check is the gate, give in that finding, for each `DIFF` line that an item of the change's briefs makes, the accepted output under `tests/gate/accepted/` to update.

## worktree
- The worktree of the change you work on is the one the message that launches you gives, or, where it gives none, your working directory at start. Run each command in it, and take each path in the repo from it.
- A later message may add a request to the change, in the form your brief gives one, and that request is part of what the change is to do.
