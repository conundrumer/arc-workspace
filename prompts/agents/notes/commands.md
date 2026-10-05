# Command notes
- The statements on running commands and waiting on them, that more than one entry point inlines.

## commands
- Run each command in the foreground, with a timeout of 600000 ms on the Bash call.
- End your turn only once each command you started has finished.
- Where the harness moves a command to the background, wait in a foreground Bash call with a timeout of 600000 ms, whose until-loop gives up just under that timeout, and repeat the call until the command's completion notification has arrived.
    - Lead its command with `: 'unattended-wait: <the command you wait on>, since a turn that ends while it runs ends my run';`. A command so led is exempt from the PreToolUse hook that blocks waits, `~/.claude/scripts/no-poll-wait.sh`.
        * comment: Without the hook's script given here, a doc reviewer checking this section searched for it from `/`, and macOS prompted the user for access to the user's media: issue `1791149774-commands-review-doc-reviewer-1`.
    - Loop on the completion where you can observe it, and otherwise on the time alone.

## launched-agents
- Wait for the agents you launched by ending your turn with a line that names each one still running, and run no command to wait on them. The harness resumes you when one of them completes or sends you a message.
- Call SubagentHandback only with your final reply.
    * comment: With the harness's reminder that the call ends the run in its context, an operator waited with `echo waiting` and `true`, and once the hook denied `true`, it called SubagentHandback with `PLACEHOLDER` while its agents ran: agent `a37be74e20c8008ae` of session `dc433af1-cf87-408d-ab9d-9a1ede6b1b2a`. With that reminder and its line on giving decisions in its final reply in its context, a triage agent of that session called SubagentHandback while its code editor ran, then sent its final report by SendMessage: agent `ac26fe1a2bcf9beb5`, lines 47 and 80 to 84.
