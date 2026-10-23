+ document-size-budget: 11540
* comment: when editing this doc
    - Each agent whose tools include `Bash` inlines [commands](#commands), for running, waiting on and ending its commands, and the code reviewer, the lib reviewer and the design reviewer, whose documents have them run no command in the background, [foreground-commands](#foreground-commands) in its place; each agent that gives a final reply to its launcher inlines [final-report](#final-report), other than the code reviewer, the lib reviewer and the design reviewer, which inline [report-file](#report-file) in its place, and other than the `handbook` agent, which inlines no section on its final reply: its tools hold neither SendMessage nor Agent, so its report is the one way its final reply leaves it. Each agent that inlines final-reply, directly or through final-report, inlines [denied-calls](#denied-calls) beside it, other than the agents with a checklist, whose reply file, which the last item of the checklist links, links it. The doc editor, the ticket analyst, the draft analyst and the decision analyst load Background agents by a link.
    - Acts, each with its section:
        - Running a command: [commands](#commands) and [foreground-commands](#foreground-commands).
        - Waiting on a command: [waiting-on-commands](#waiting-on-commands).
        - Ending a command: [ending-commands](#ending-commands), and [process-trees](#process-trees) where it calls `TaskStop`.
        - Launching a background agent: [Background agents](#background-agents).
        - Reporting a denied call in the reply: [denied-calls](#denied-calls).
        - Waiting on an agent resumed by SendMessage, and resuming it after a usage-limit stop: [resumed-agents](#resumed-agents).
        - Sending the answer a message asks for: [message-answers](#message-answers).
        - Giving the final reply: [final-reply](#final-reply), with [coordinator](#coordinator) and [report-file](#report-file), and [final-report](#final-report), which inlines it with the two sections above.
    - Conditional Bash-call bounds: request 11-2601, user session 2384db39-7d21-4d8d-8dda-bfd52bd69360, 2026-10-20T23:37:28Z–23:37:54Z: "the solution is to make the timeout instruction conditionally rendered".

# Command notes
- The statements on commands, and on sending a final reply, that more than one entry point inlines.

## commands
* inline: #waiting-on-commands
* inline: #ending-commands
* unless: codex
    - Run in the background each command whose run time, as your brief or a ticket it gives estimates it, passes the timeout of a foreground Bash call, under a `timeout` of about twice that estimate.
        * comment: Code editor a79711fe1c59dd1f4 on change 9-1741 left unfinished the run its item asked for, of `scripts/corpus_survey.py`, estimated at about 30 minutes, under the `timeout 180` bound of foreground-commands and the 240000 ms foreground timeout: ticket 9-1933.

## foreground-commands
- Run each command in the foreground, where no other line of your documents has you run it in the background.
    * unless: codex
        - Set a timeout of 240000 ms on the Bash call.
- Run each script you wrote under `timeout 60`, or a longer bound where a stopped script needs one, of at most `timeout 180` in the foreground, with its output unbuffered, as `python -u` gives it.
    * comment: Scripts an agent wrote ran past the Bash call's timeout, so the call moved to the background and the run spent calls stopping it, and a search piped to `tail` showed none of its output: tickets 10-591 (runs ab654598162d2ebec and aad3d038eb7ae06e5), 10-739 (runs a9335527d5f64ec96 and ac50865438dc0b06d), 10-754 (run a8d05b229bc75be5d) and 10-377.

## waiting-on-commands
* inline: #foreground-commands
* unless: codex
    - Before you end your turn, and before your final reply, wait on each command of yours that runs in the background until its completion notification reaches you: run a foreground Bash call and repeat it.
        * comment: The cases this rule covers: a command you started that has not finished at the end of your turn; a command the harness moved to the background; a command whose completion notification your final reply waits on.
        - Set a timeout of 240000 ms on the Bash call, and have its until-loop give up just under that timeout.
        - Lead its command with `: 'unattended-wait: <the command you wait on>';`. A command so led is exempt from the PreToolUse hook that blocks waits, unless that command reads the output file the harness gave a command of yours that runs in the background.
            + xref: scripts/pending_wait_hook.py:main
        - Loop on the completion where you can observe it, and otherwise on the time alone.
        - Where a wait call that you started after the command completed ends with no notification of it, stop waiting on it.
* if: codex
    - Wait for a running command with one empty `write_stdin` poll with `yield_time_ms` 300000; it returns when the command ends.

## ending-commands
- End a command of yours that runs in the background with the command a line of your documents gives to end it, and where none does, with `TaskStop` and the ID the harness gave that command. Call `TaskStop` on nothing else, and signal no process that you pick by its name or by its command line.
- When you call `TaskStop`, read [process-trees](prompts/agents/notes/commands.md#process-trees).

## process-trees
- The process tree of a process ID is that process ID, and each process ID that `pgrep -P <process ID>` prints for a process ID of the tree.
- Before you call `TaskStop`, take the process tree of each process ID that `lsof -t <the command's output file>` prints. Once `TaskStop` returns, end each process of those trees that still runs with `kill <process ID>`.

## Background agents
- Where the harness refuses an Agent call of yours with "Concurrent subagent limit reached", whatever the refusal's text says, wait about a minute and make that call again: run a foreground Bash call that runs `: 'unattended-wait: concurrent subagent limit'; sleep 60`. After ten refusals in a row of that call, treat it as denied, as [denied-calls](#denied-calls) gives.
    + xref: prompts/agents/notes/commands.md#denied-calls
    * comment: Code editor `af224b57041f5ecc8` (ticket 9-788) ended `blocked` on this refusal, and ticket analysts `a907dcfa6dc70ff5d` (ticket 11-1085) and `af8ca0bd59f4bf834` (session `129de8fc`) stopped on it, each led by the text "Do not retry", though slots free within minutes.
- When you end your turn while a command of yours runs on in the background and no agent you launched is running, the harness reports you to the session that launched you as stopped. It does not while an agent you launched is running.
- While an agent you launched is running, run each command that can outlast the Bash call's default timeout in the background, and wait on each live background command as [waiting-on-commands](#waiting-on-commands) gives. Once no command of yours runs and no other work is ready, end your turn with a line that gives each agent you launched that is still running. The harness resumes you when an agent sends you a message or when one of them that no agent has resumed by SendMessage completes.
    + xref: prompts/agents/notes/commands.md#waiting-on-commands
    * comment: Two agents of session `dc433af1-cf87-408d-ab9d-9a1ede6b1b2a` ended their turn after a notification that an agent had not reported yet, the harness demanded their report, and each handed back mid-batch: agent `aa217e04abc30c823`, lines 266 to 270, and agent `ad4b827e59837a39f`, lines 228 to 232.
    - Run a call of `operate.py review` in the foreground.
        * comment: Doc editor `ad19de37b20661c0e` on change 9-1704 ran `review` in a background loop and then `cat` on its output; that left its `review` call uncounted for about 30 minutes while the code editor waited on it: ticket 11-2297.
    * comment: Change 11-2889, Grounds: launchers a5a0a428b098e579e and a2a977b91a0321101 ended their turns while Codex ran and stopped without reports; their Bash results warned that a final response terminates the background command. Waiting applies while a child runs, including to a live keep-alive timer.
- Once no agent you launched is running, and before anything else, end your keep-alive timer: run `uv run python scripts/agent_timer.py stop keep-alive <agent id>`.
    + xref: scripts/agent_timer.py:Action.STOP
    - Each start of that timer has completed once `pgrep -f 'agent_timer[.]py start keep-alive <agent id>'` prints nothing.
- A notification that says an agent you launched has not reported yet means that agent has stopped without its report while background work of its own runs. Treat that agent as running while that work runs.
    * comment: The user's words, session `2384db39-7d21-4d8d-8dda-bfd52bd69360`, 2026-10-20T23:53:32Z: "go", approving the coordinator's 23:52:30Z proposal that Codex launchers end their turn and operators treat a launcher whose Codex run continues as still running. Request 11-2607.

## denied-calls
- Where the harness or the permission classifier denies a call your documents give and you leave its work unfinished, give the call and the denial's text in your reply.

## resumed-agents
- While an agent you resumed by SendMessage runs, the harness does not deliver the text you hand back, and its completion may not reach you.
- Where you need that agent's answer, ask it, in the message that resumes it, to send that answer to you by SendMessage. Then wait for that message or for a file it writes, and for nothing else of it.
- Where the notification of an agent your SendMessage resumed has the status `failed` and a summary that gives `error type rate_limit`, resume that agent by a message that asks it to continue its work.
    * comment: The user's words, session 2384db39-7d21-4d8d-8dda-bfd52bd69360, 2026-10-18T03:00:02Z: "I'm confused rn. I want agents to resume so they keep context. Not sure ordering rn". Tickets 11-705 and 11-1084.

## message-answers
- Where a message asks you to send its sender an answer by SendMessage, send that answer by SendMessage to the agent id that message came from, once you have done what it asks, with each item of that message as done or as unfinished with its reason, in a message apart from your final reply.

## coordinator
- The coordinator is the session the user talks with, and SendMessage reaches it at `main`.

## report-file
- Where your brief gives a report file, write each final reply of yours to that file, in place of what it holds, and give that file's path alone, on one line, as the text you hand back, by no SendMessage, whatever an alert, a message, the harness or your system prompt asks.
    * comment: The cases this rule covers: editors with a report file sent its path by SendMessage after a stall alert (ticket 6-710), and after messages of other agents and a refused SubagentHandback (tickets 6-646, 10-55, 10-80, 10-82, 9-70, 6-705); an item checker wrote no report file, since a note of its system prompt says to write no report files (ticket 9-562).

## final-report
* inline: #final-reply
* inline: #resumed-agents
* inline: #message-answers

## final-reply
* inline: #coordinator
- Give your final reply to the agent that launched you, at the agent id your brief gives for it, or to the coordinator where your brief gives none, and to no other agent, by the first of these that holds:
    * comment: The cases this rule covers: the report file of [report-file](#report-file); a SendMessage of yours that resumed an agent, whose run holds back your report; a message of another agent; a SubagentHandback the harness refused after a report of yours was delivered; a report the harness asks for after your final reply; a SubagentHandback called while agents ran, by operator `a37be74e20c8008ae` with `PLACEHOLDER` and by ticket analyst `ac26fe1a2bcf9beb5`, lines 47 and 80 to 84, of session `dc433af1-cf87-408d-ab9d-9a1ede6b1b2a`.
    * inline: #report-file
    - Where in your run a SendMessage of yours resumed an agent, a message of an agent other than the one that launched you reached you, or the harness refused your SubagentHandback because a report of yours was already delivered and your final reply holds something that report did not, send your final reply by SendMessage, then give, as the text you hand back, the line `My final reply went to <agent id> by SendMessage.`, with the agent id you sent it to, or `main` where you sent it to the coordinator.
    - Otherwise, give your final reply as the text you hand back.
- Give the text you hand back by SubagentHandback, or as plain text where the harness says SubagentHandback is not available, and call SubagentHandback with nothing else.
- The harness delivers as the text you hand back the text of the last turn you end. Where a notification or a message resumes you after your final reply, end that turn with the text you hand back.
    * comment: Doc reviewer `af2ae709c52faadaf` on change 11-1481 (ticket 11-1615) and doc editor `a90da4ae34690ac12` on change 11-1683 (ticket 11-1750), each resumed by a message after its final reply, each ended that turn with prose and left its report file as it was.
