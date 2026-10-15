+ budget: 9800
* comment: when editing this doc
    - Each agent whose tools include `Bash` inlines [commands](#commands), for running, waiting on and ending its commands; each agent that gives a final reply to its launcher inlines [final-report](#final-report), and the code reviewer [report-file](#report-file). The doc editor and the ticket analyst load Background agents by a link, where a command prints an Agent call.
    - Acts, each with its section:
        - Running a command: [commands](#commands).
        - Waiting on a command: [waiting-on-commands](#waiting-on-commands).
        - Ending a command: [ending-commands](#ending-commands).
        - Launching a background agent a command prints: [Background agents](#background-agents).
        - Reporting a denied call: [denied-calls](#denied-calls).
        - Waiting on an agent resumed by SendMessage: [resumed-agents](#resumed-agents).
        - Giving the final reply: [final-report](#final-report), with [coordinator](#coordinator) and [report-file](#report-file).

# Command notes
- The statements on commands, and on sending a final reply, that more than one entry point inlines.

## commands
* inline: #waiting-on-commands
* inline: #ending-commands

## waiting-on-commands
- Run each command in the foreground, with a timeout of 240000 ms on the Bash call, other than a budget timer your documents have you start, which runs in the background. A turn that does not end with your final reply may end while that timer runs.
- Before you end your turn, and before your final reply, wait on each command of yours that runs in the background, other than a budget timer you have not ended, until its completion notification reaches you: run a foreground Bash call with a timeout of 240000 ms, whose until-loop gives up just under that timeout, and repeat the call.
    * comment: The cases this rule covers: a command you started that has not finished at the end of your turn; a command the harness moved to the background; a command whose completion notification your final reply waits on; a budget timer once you have ended it.
    - Lead its command with `: 'unattended-wait: <the command you wait on>';`. A command so led is exempt from the PreToolUse hook that blocks waits, unless that command reads the output file the harness gave a command of yours that runs in the background.
    - Loop on the completion where you can observe it, and otherwise on the time alone.
    - Where a wait call that you started after the command completed ends with no notification of it, stop waiting on it.

## ending-commands
- End a command of yours that runs in the background with the command a line of your documents gives to end it, and where none does, with `TaskStop` and the ID the harness gave that command. Call `TaskStop` on nothing else, and signal no process that you pick by its name or by its command line.
- The process tree of a process ID is that process ID, and each process ID that `pgrep -P <process ID>` prints for a process ID of the tree.
- Before you call `TaskStop`, take the process tree of each process ID that `lsof -t <the command's output file>` prints. Once `TaskStop` returns, end each process of those trees that still runs with `kill <process ID>`.
- Where you start a process with `&` or `nohup`, print its process ID with `echo $!` in that Bash call. To end it, take the process tree of that process ID, and end each process of that tree with `kill <process ID>`.

## Background agents
- When you end your turn while a command of yours runs on in the background and no agent you launched is running, the harness reports you to the session that launched you as stopped. It does not while an agent you launched is running.
- While an agent you launched is running, no line of [waiting-on-commands](#waiting-on-commands) holds: run each command that can outlast the Bash call's default timeout in the background, and when no other work is ready, start your keep-alive timer, then end your turn with a line that gives each agent you launched and each command of yours that is still running, and run no other command to wait on them. The harness resumes you when an agent sends you a message, when one of them that no agent has resumed by SendMessage completes, or when a command of yours that runs in the background completes.
    * comment: The cases this rule covers: waiting while an agent you launched runs; the start of the keep-alive timer before you end your turn; waiting, once no agent you launched runs, on each command you ran in the background, which [waiting-on-commands](#waiting-on-commands) covers once this rule no longer holds.
    - Start your keep-alive timer, where you launched no agent in this turn whose brief asks only for a wait and then a reply, by running this command in the background, with your own agent id as `<agent id>`:
        ```
        : 'unattended-wait: keep-alive timer'; uv run python scripts/agent_timer.py start keep-alive <agent id>
        ```
    - Where your keep-alive timer has completed 11 times in a row with no message and no other notification reaching you between, start it no more until one does. The runs of that command that complete together count as one completion.
- Once no agent you launched is running, and before anything else, end your keep-alive timer: run `uv run python scripts/agent_timer.py stop keep-alive <agent id>`.
    - Each start of that timer has completed once `pgrep -f 'agent_timer[.]py start keep-alive <agent id>'` prints nothing.
- A notification that says an agent you launched has not reported yet means that agent has stopped without its report while background work of its own runs, and it counts as not running from then on. Until it reports, while no other agent you launched is running, wait on it in place of ending your turn, and call no SubagentHandback, also where the harness asks for your report: run a Bash call with a timeout of 240000 ms whose loop, on time alone, gives up just under that timeout, led by `: 'unattended-wait: <the agent id>, which has not reported yet';`, and repeat it.
    * comment: Two agents of session `dc433af1-cf87-408d-ab9d-9a1ede6b1b2a` ended their turn after this notification, the harness demanded their report, and each handed back mid-batch: agent `aa217e04abc30c823`, lines 266 to 270, and agent `ad4b827e59837a39f`, lines 228 to 232.

## denied-calls
- Where the harness or the permission classifier denies a call your documents give and you leave its work unfinished, give the call and the denial's text in your reply.

## resumed-agents
- While an agent you resumed by SendMessage runs, the harness does not deliver your report, and its completion may not reach you.
- Where you need that agent's answer, ask it, in the message that resumes it, to send that answer to you by SendMessage. Then wait for that message or for a file it writes, and for nothing else of it.
- Where a message asks you to send its sender an answer by SendMessage, send that answer by SendMessage to the agent id that message came from, once you have done what it asks, with each item of that message as done or as unfinished with its reason, in a message apart from your final reply.

## coordinator
- The coordinator is the session the user talks with, and SendMessage reaches it at `main`.

## report-file
- Where your brief gives a report file, write each final reply of yours to that file, in place of what it holds, and give that file's path alone, on one line, as the final reply itself, by no SendMessage, whatever an alert, a message or the harness asks.
    * comment: The cases this rule covers: editors with a report file sent its path by SendMessage after a stall alert (ticket 6-710), and after messages of other agents and a refused SubagentHandback (tickets 6-646, 10-55, 10-80, 10-82, 9-70, 6-705).

## final-report
* inline: #denied-calls
* inline: #coordinator
- Give your final reply to the agent that launched you, at the agent id your brief gives for it, or to the coordinator where your brief gives none, and to no other agent, by the first of these that holds:
    * comment: The cases this rule covers: the report file of [report-file](#report-file); a SendMessage of yours that resumed an agent, whose run holds back your report; a message of another agent; a SubagentHandback the harness refused after a report of yours was delivered; a report the harness asks for after your final reply; a SubagentHandback called while agents ran, by operator `a37be74e20c8008ae` with `PLACEHOLDER` and by ticket analyst `ac26fe1a2bcf9beb5`, lines 47 and 80 to 84, of session `dc433af1-cf87-408d-ab9d-9a1ede6b1b2a`.
    * inline: #report-file
    - Where in your run a SendMessage of yours resumed an agent, a message of an agent other than the one that launched you reached you, or the harness refused your SubagentHandback because a report of yours was already delivered and your final reply holds something that report did not, send your final reply by SendMessage, then give, as your report, the line `My final reply went to <agent id> by SendMessage.`, with the agent id you sent it to, or `main` where you sent it to the coordinator.
    - Otherwise, give your final reply as your report.
- Give your report by SubagentHandback, or as plain text where the harness says SubagentHandback is not available, and call SubagentHandback with nothing else.
- The harness delivers as your report the text of the last turn you end. Where a notification resumes you after your final reply, end that turn with your report.
* inline: #resumed-agents
