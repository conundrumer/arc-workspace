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
- Wait for an agent you launched by ending your turn with no message to the session that launched you, and run no sleep on it. The harness resumes you when that agent completes or sends a message.
