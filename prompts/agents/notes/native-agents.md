+ document-size-budget: 4200
* comment: when editing this doc
    - Codex agents receive [Native tools](#native-tools) with their rendered role instructions, and read each other section when that section's act is required.
    - Acts, each with its section:
        - Reading an assignment, choosing a tool and placing temporary files: [Native tools](#native-tools).
        - Launching an agent: [Launches](#launches).
        - Sending a message or changing a child's assignment: [Messages](#messages).
        - Waiting for children and accepting their reports: [Completion](#completion).
        - Returning a call or a decision to the owning operator: [Operator input](#operator-input).

# Native agent notes
- Native tools for the calls a Codex agent's role documents allow.

## Native tools
- This render leaves out the linked procedures.
- Write each temporary file you make in your scratch directory, and in no other directory.
    + xref: scripts/codex_ticket.py:NATIVE_IDENTITY
    * comment: Change 11-3796, Intent and Grounds: the user's words, session 2384db39-7d21-4d8d-8dda-bfd52bd69360, 2026-10-23T18:18:33Z: "we need to give codex their own scratchpads and make it clear". Codex root a57f8628a40d36948 in that session wrote its listings to `/tmp/cost-audit-*` and overwrote two existing files, while its first input gave its scratch directory.
- Run each `scripts/codex_ticket.py` command in the main tree.
- Use your assignment's operations agent id in commands that take an agent id, and native agent ids in native tools.
- For an Agent call your role's documents give, read [Launches](#launches).
- For a SendMessage your role's documents give, read [Messages](#messages).
- Where you launch a child, read [Completion](#completion) for its result and before ending your turn.
- Where a call requires Claude or work needs an external decision, read [Operator input](#operator-input).

## Launches
- Write an Agent call's parameters to a JSON file and run `uv run python scripts/codex_ticket.py prepare <scratch> <parameters>`, with your assigned scratch directory and that file.
    + xref: scripts/codex_ticket.py:main, scripts/codex_ticket.py:prepare
- Where a command gives a native call, make that call with its printed arguments. After submission, run `uv run python scripts/codex_ticket.py reconcile <scratch> <agent> <native>`, with the child's operations and native ids.
    + xref: scripts/codex_ticket.py:main, scripts/codex_ticket.py:reconcile
- Where a command gives a `needs-operator` outcome, use [Operator input](#operator-input).
    + xref: scripts/codex_reports.py:Outcome

## Messages
- Resolve an operations agent id with `uv run python scripts/codex_ticket.py target <scratch> <agent>`. Use the returned native id with `send_message` for a running recipient.
    + xref: scripts/codex_ticket.py:main, scripts/codex_ticket.py:Store.target
- Before changing a child's assignment or following up a finished child, write the revised launch parameters to a JSON file and run `uv run python scripts/codex_ticket.py prepare <scratch> <parameters> --previous <agent>`. Make the returned call and reconcile its execution as [Launches](#launches) gives.
    + xref: scripts/codex_ticket.py:main, scripts/codex_ticket.py:prepare
- Where the recipient is outside your native tree, use [Operator input](#operator-input).

## Completion
- Use `list_agents` to observe your children and `wait_agent` to wait for their updates.
- After a child ends, reconcile its execution as [Launches](#launches) gives, then run `uv run python scripts/codex_ticket.py accept <scratch> <agent> --outcome <outcome>`, with its operations id. Take the outcome from `codex-dispatch.json` in that child's assigned scratch directory, or use `finished` where that file is absent.
    + xref: scripts/codex_ticket.py:main, scripts/codex_ticket.py:accept
- Use a child's result after that validator accepts it. Follow up an invalid result as [Messages](#messages) gives.
- For a child's `needs-operator` result, file that dispatch's call or decision as [Operator input](#operator-input) gives.
- Before ending your turn, wait for your descendants to end and reconcile their execution.

## Operator input
- Write unfinished findings to your assigned report. Run `uv run python scripts/codex_ticket.py dispatch <scratch>` for an external decision, or add `--call <file>` for a call written to a JSON file with its tool and arguments, including the full text to send.
    + xref: scripts/codex_ticket.py:main
- A `needs-operator` result from `prepare` has already filed that dispatch.
    + xref: scripts/codex_ticket.py:prepare
- The root's Claude launcher makes the dispatch's call and resumes the root with its result after its turn and descendants end. A dispatch with no call reaches the owning operator through the root's report.
    + xref: scripts/codex_agent.py:main
