+ budget: 1500
* comment: when editing this doc
    - The decision analyst loads this document from [Jobs](prompts/agents/decision-analyst.md#jobs), when its brief gives what a change's editors leave, to judge it.
    - Acts, each with its section:
        - Sending kept findings to an editor, leaving the change's ticket as it stands, settling `question` tickets on the change, and judging standing `refactor` places: [An editor's findings](#an-editors-findings).

# An editor's findings
- Send the editor, as kept, each declined part that a log line of the coordinator on the change's ticket vetoes and that the worktree does not hold.
- That change's ticket is no ticket you resolve: leave it in the status it stands in, whatever your resolution of what its editors leave.
- Close each `question` ticket on the change that you decide with its resolution word, and move each whose decision [The user's part](prompts/agents/notes/decisions.md#the-users-part) brings to the user to `tickets/blocked/`, with a note that opens with `user` and gives the decision.
- Judge each `refactor` place that your brief gives as standing, by the reason it gives. Close the `refactor` ticket of each place you keep as standing at once, `wontfix` with the judgment, wherever under `tickets/` it stands, and send each other to the editor as a kept finding.
