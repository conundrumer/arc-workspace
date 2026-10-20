+ document-size-budget: 3414
* comment: when editing this doc
    - The decision analyst receives this document from the step command as it enters the judging of what a change's editors leave, once it has read its brief.
    - Acts, each with its section:
        - Judging findings, items and standing places, those of a review at its round cap included, sending the editors its judgments, leaving the change's ticket as it stands, and settling `question` tickets on the change: [An editor's findings](#an-editors-findings), with [Findings that block a change](prompts/agents/notes/launching.md#findings-that-block-a-change).

# An editor's findings
- When you send the editors your judgments, send as kept each declined part that a log line of the coordinator on the change's ticket vetoes and that the worktree does not hold.
- That change's ticket is no ticket you resolve: leave it in the status it stands in, whatever your resolution of what its editors leave.
- When you settle the `question` tickets on the change, close each that you decide with its resolution word, and move each whose decision [The user's part](prompts/agents/decision-analyst.md#the-users-part) brings to the user to `tickets/blocked/`, with a note that opens with `user` and gives the decision.
    + xref: prompts/agents/decision-analyst.md#the-users-part
- Judge a `refactor` place that your brief gives as standing by the reason it gives. Close the `refactor` ticket of each place you keep as standing at once, `wontfix` with the judgment, wherever under `tickets/` it stands, and send each other that blocks the change, as [Findings that block a change](prompts/agents/notes/launching.md#findings-that-block-a-change) gives, to the editor as a kept finding.
    + xref: prompts/agents/notes/launching.md#findings-that-block-a-change
- Give each other place in your reply as decided, with the `refactor` ticket that records it, or, where none does, a `refactor` ticket you file on it, which does not block the change.
- A finding at the round cap is one that your brief gives from the item checker's last review round of the change or from the check after its review round cap, one that your brief gives on a change past its cost budget, one of a doc reviewer's reply that opens with `at the round cap`, or one an editor leaves with a reason that opens with `at the round cap`. Send no finding at the round cap to the editor as kept. For each, do one of these:
    + xref: src/operations/briefs.py:CAP_REPLY
    - Drop it, with its reason, where it is wrong or blocks the change by no item.
    - Bring it to the user, where [The user's part](prompts/agents/decision-analyst.md#the-users-part) gives its decision as the user's.
        + xref: prompts/agents/decision-analyst.md#the-users-part
    - Where a small, clear edit fixes it, give the editor that edit as a decision.
    - Where no such edit fixes it within the change, file a new `change` ticket with the item it breaks, and give that item in your reply as decided, with that ticket's number.
- Where your brief gives the check after the change's review round cap, or the change as past its cost budget, give the editor, as a decision, each edit without which the change's merge is refused, the resolution of a rebase conflict that stands in the change's worktree among them, and no other edit: file a new `change` ticket with the item of each finding and each unfinished item it gives that you do not drop, bring to the user or fix by such an edit.
