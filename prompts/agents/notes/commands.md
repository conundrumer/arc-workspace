# Command notes
- The statements on running commands and waiting on them, that more than one entry point inlines.

## commands
- Run each command in the foreground, with a timeout of 600000 ms on the Bash call.
- End your turn only once each command you started has finished.
- Where the harness moves a command to the background, wait in a foreground Bash call with a timeout of 600000 ms, whose until-loop gives up just under that timeout, and repeat the call until the command's completion notification has arrived.
    - Lead its command with `: 'unattended-wait: <the command you wait on>';`. A command so led is exempt from the PreToolUse hook that blocks waits, `~/.claude/scripts/no-poll-wait.sh`.
        * comment: Without the hook's script given here, a doc reviewer checking this section searched for it from `/`, and macOS prompted the user for access to the user's media: ticket `1791149774-commands-review-doc-reviewer-1`.
    - Loop on the completion where you can observe it, and otherwise on the time alone.

## background-work
- When you end your turn while a command of yours runs on in the background and no agent you launched is running, the harness reports you to the session that launched you as stopped. It does not while an agent you launched is running.
- While no agent you launched is running, other than one that a notification has said has not reported yet:
    * inline: #commands
    - Wait on a command you ran in the background yourself as on one the harness moved there.
- While an agent you launched is running, other than one that a notification has said has not reported yet, run each command that can outlast the Bash call's default timeout in the background, and when no other work is ready, end your turn with a line that names each agent you launched and each command of yours that is still running, and run no command to wait on them. The harness resumes you when one of them completes or an agent sends you a message.
- A notification that says an agent you launched has not reported yet means that agent has stopped without its report while background work of its own runs. From then until that agent reports, while no other agent you launched is running, wait in place of ending your turn: run a Bash call with a timeout of 600000 ms whose loop, on time alone, gives up just under that timeout, led by `: 'unattended-wait: <the agent id>, which has not reported yet';`, and repeat it.
    - Where the harness asks for your report while that agent has not reported, go on waiting that way, and call no SubagentHandback.
    * comment: Two agents of session `dc433af1-cf87-408d-ab9d-9a1ede6b1b2a` ended their turn after this notification, the harness demanded their report, and each handed back mid-batch: agent `aa217e04abc30c823`, lines 266 to 270, and agent `ad4b827e59837a39f`, lines 228 to 232.
- Call SubagentHandback only with your final reply.
    * comment: With the harness's reminder that the call ends the run in its context, an operator waited with `echo waiting` and `true`, and once the hook denied `true`, it called SubagentHandback with `PLACEHOLDER` while its agents ran: agent `a37be74e20c8008ae` of session `dc433af1-cf87-408d-ab9d-9a1ede6b1b2a`. With that reminder and its line on giving decisions in its final reply in its context, an assignee of that session, then named `triage`, called SubagentHandback while its code editor ran, then sent its final report by SendMessage: agent `ac26fe1a2bcf9beb5`, lines 47 and 80 to 84.
