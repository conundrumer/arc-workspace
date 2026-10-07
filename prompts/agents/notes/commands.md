# Command notes
- The statements on running commands, waiting on them, and sending a final reply, that more than one entry point inlines.

## commands
- Run each command in the foreground, with a timeout of 240000 ms on the Bash call, other than a budget timer your documents have you start.
- End your turn only once each command you started has finished, other than that timer.
- Where the harness moves a command to the background, wait in a foreground Bash call with a timeout of 240000 ms, whose until-loop gives up just under that timeout, and repeat the call until the command's completion notification has arrived.
    - Lead its command with `: 'unattended-wait: <the command you wait on>';`. A command so led is exempt from the PreToolUse hook that blocks waits, `~/.claude/scripts/no-poll-wait.sh`.
        * comment: Without the hook's script given here, a doc reviewer checking this section searched for it from `/`, and macOS prompted the user for access to the user's media: ticket `1791149774-commands-review-doc-reviewer-1`.
    - Loop on the completion where you can observe it, and otherwise on the time alone.

## background-work
- When you end your turn while a command of yours runs on in the background and no agent you launched is running, the harness reports you to the session that launched you as stopped. It does not while an agent you launched is running.
- While no agent you launched is running, other than one that a notification has said has not reported yet:
    * inline: #commands
    - Wait on a command you ran in the background yourself as on one the harness moved there.
- While an agent you launched is running, other than one that a notification has said has not reported yet, run each command that can outlast the Bash call's default timeout in the background, and when no other work is ready, start your keep-alive timer where you launched no agent in this turn whose brief asks only for a reply, then end your turn with a line that names each agent you launched and each command of yours that is still running, and run no other command to wait on them. The harness resumes you when an agent sends you a message, when one of them that no agent has resumed by SendMessage completes, or when a command of yours that runs in the background completes.
    - Start your keep-alive timer by running this command in the background, with your own agent id as `<agent id>`:
        ```
        : 'unattended-wait: keep-alive timer'; uv run python scripts/keep_alive.py start <agent id>
        ```
    - Where your keep-alive timer has completed 11 times in a row with no message and no other notification reaching you between, start it no more until one does. The runs of that command that complete together count as one completion.
- Once no agent you launched is running, other than one that a notification has said has not reported yet, and before anything else, end your keep-alive timer: run `uv run python scripts/keep_alive.py stop <agent id>`.
- A notification that says an agent you launched has not reported yet means that agent has stopped without its report while background work of its own runs. From then until that agent reports, while no other agent you launched is running, wait in place of ending your turn: run a Bash call with a timeout of 240000 ms whose loop, on time alone, gives up just under that timeout, led by `: 'unattended-wait: <the agent id>, which has not reported yet';`, and repeat it.
    - Where the harness asks for your report while that agent has not reported, go on waiting that way, and call no SubagentHandback.
    * comment: Two agents of session `dc433af1-cf87-408d-ab9d-9a1ede6b1b2a` ended their turn after this notification, the harness demanded their report, and each handed back mid-batch: agent `aa217e04abc30c823`, lines 266 to 270, and agent `ad4b827e59837a39f`, lines 228 to 232.
- Call SubagentHandback only with your final reply, or with the line that says where it went.
    * comment: With the harness's reminder that the call ends the run in its context, an operator waited with `echo waiting` and `true`, and once the hook denied `true`, it called SubagentHandback with `PLACEHOLDER` while its agents ran: agent `a37be74e20c8008ae` of session `dc433af1-cf87-408d-ab9d-9a1ede6b1b2a`. With that reminder and its line on giving decisions in its final reply in its context, a ticket analyst of that session, then named `triage`, called SubagentHandback while its code editor ran, then sent its final report by SendMessage: agent `ac26fe1a2bcf9beb5`, lines 47 and 80 to 84.

## denied-calls
- Where the harness or the permission classifier denies a call your documents give and you leave its work unfinished, give the call and the denial's text in your reply.

## resumed-agents
- While an agent you resumed by SendMessage runs, the harness does not deliver your report, and its completion may not reach you.
- Where you need that agent's answer, ask it, in the message that resumes it, to send that answer to you by SendMessage. Then wait for that message or for a file it writes, and for nothing else of it.
- The harness delivers as your report the text of the last turn you end. Where a notification resumes you after your final reply, end that turn with the report you gave at your final reply: your final reply in full, or the one line that says where it went.

## coordinator
- The coordinator is the session the user talks with, and SendMessage reaches it at `main`.

## final-report
* inline: #denied-calls
* inline: #coordinator
- Where, in your run, a SendMessage of yours resumed an agent, or a message of an agent other than the one that launched you reached you, or the harness refused your SubagentHandback because a report of yours was already delivered, send your final reply by SendMessage to the agent that launched you, at the agent id your brief gives for it, or to the coordinator where your brief gives none, and to no other agent. Then give, as the report the harness asks for, one line that says your final reply went to that agent: your SubagentHandback, or plain text where the harness says SubagentHandback is not available.
* inline: #resumed-agents
