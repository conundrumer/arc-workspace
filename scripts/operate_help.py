"""The help text of `operate.py`: `USAGE`, which `--help` prints, gives
its usage forms, and `PARTS` the rest of its help, a part at a time."""

from enum import StrEnum

from controlled_markdown import mctx
from operations import concept_faults
from operations.monitor import ALERTS


class HelpPart(StrEnum):
    """Each part of the help, by the word `--help` takes to print it, in the
    order the bare `--help` lists them."""
    NEXT = "next"
    JOURNAL = "journal"
    RULINGS = "rulings"
    RUN = "run"
    PACE = "pace"
    SEND = "send"
    RELAY = "relay"
    REVIEW = "review"
    WAIT = "wait"
    ALERTS = "alerts"


USAGE = mctx("""
    - Usage:
        ```
        uv run python scripts/operate.py next <agent id>
        uv run python scripts/operate.py relay <agent id>
        uv run python scripts/operate.py review <agent id>
        uv run python scripts/operate.py wait <agent id>
        uv run python scripts/operate.py send
        uv run python scripts/operate.py start --run <run> <task id> <pass> ...
        uv run python scripts/operate.py claim <task id>
        uv run python scripts/operate.py set-aside <task id> analyze|create
        uv run python scripts/operate.py restore <task id> [<reason>]
        uv run python scripts/operate.py release <task id>
        uv run python scripts/operate.py waits <ticket number>
        uv run python scripts/operate.py bound [<tokens>|default]
        uv run python scripts/operate.py codex [on|off]
        uv run python scripts/operate.py trial [on|off]
        ```
    - Where `next`, `relay` or `review` is given the agent id of an agent other than the one its part of this help gives, it prints that the agent is none that form serves, and what that agent does.
    {parts}
    - `claim` claims a task for the session, and, where a claim on the task stands, fails and prints the session that holds it.
    - `set-aside` sets aside a task's earlier work in the main worktree before an Analyze or a Create pass.
    - `restore` puts that work back, removes the task's claim and records the call.
        - `<reason>` is the reason the task's pipeline stopped, or empty where that pipeline ran to its end, and `next` then takes that pipeline as ended with that reason.
    - `release` removes the task's claim.
    - `waits` prints the paths of links from a ticket, as `--help alerts` gives them, from the state `next` reads for the session.
    - `bound` prints the context bound of an operator and an operator launcher in force, and its source, as `500000 override` or `100000 default`. Given `<tokens>`, a positive whole number, it first writes that number as the override, which holds for every session on the machine; given `default`, it first removes the override.
    - `codex` prints `on` or `off`. Given either word, it first sets Codex mode for every session on the machine. It is off where the main tree has no `.cache/codex`. While on, every launch outside the operator and solver passes whose model is not Haiku, including one with no model, runs through a Haiku Codex launcher that gives the role's work to Codex. The model is the step's override, else the role's agent document or brief's model, before either mode switch. Haiku launches, operators and the solver passes `analyze`, `create` and `refine` stay on Claude. Each command holds the switch value for its run.
    - `trial` prints `on` or `off`. Given either word, it first sets trial mode for every session on the machine. It is off where the main tree has no `.cache/trial`. While on, every launch the operator or `review` prints gives Haiku as its model, whatever its role, agent document or step gives. Each command holds the switch value for its run.
    - The session is the one `CLAUDE_CODE_SESSION_ID` gives.
    """)
"""The help the bare `--help` prints."""

PURPOSES = {
    HelpPart.NEXT: mctx("what `next` prints"),
    HelpPart.JOURNAL: mctx("how `next` runs each Bash step, records each step it gives, and tells whether a step is done"),
    HelpPart.RULINGS: mctx("the forms of the rulings `next` applies"),
    HelpPart.RUN: mctx("the `Op run:` line and the run script `next` reads"),
    HelpPart.PACE: mctx("the `Op pace:` line, which sets the Claude usage pace"),
    HelpPart.SEND: mctx("how `send` records the coordinator's lines for the operators"),
    HelpPart.RELAY: mctx("what `relay` prints"),
    HelpPart.REVIEW: mctx("what `review` prints"),
    HelpPart.WAIT: mctx("how `wait` blocks"),
    HelpPart.ALERTS: mctx("the alerts `next` sends, the paths of links from a ticket, and the messages it sends the coordinator on waits and on concept faults"),
}
"""What each part of the help gives."""

WAITS_HELP = mctx("""
    - The paths of links from a ticket are a nested list of the tickets outside `tickets/closed/` that a chain of links reaches from it, a link as [Change tickets](prompts/agents/notes/tickets.md#change-tickets) gives one.
        + xref: prompts/agents/notes/tickets.md#change-tickets
        - A ticket that two paths reach is given in full at its first place, and at each later place by its number alone.
        - Each ticket that does not move gives why, the first of these that holds:
            - It waits on the user, since its last move into `tickets/blocked/`.
            - It has had no step since its last progress, while an operator's step is due on it.
            - It waits on nothing that moves it: no agent of it is pending, each entry of its `depends-on` is closed, and no exit of it has a party that stands, where the operator's step that leaves it out names that party.
            - It stands on a cycle of links, which it gives in order.
            - It stands under `tickets/draft/`.
            - The read of the tracker left it out.
            - It stands in a take's queue, as `uv run python scripts/file_ticket.py log --help-all` gives it, each ticket of its `depends-on` is closed, and the run scripts' `takes`, the `Op pause.` line, the `Op scope: own.` line or the usage pace holds it.
        - A ticket that gives no reason waits in turn.
    - Where a change waits on its `depends-on`, its log has had no line for `STUCK_SECONDS`, and its paths hold a ticket that stands on a cycle, that waits on nothing that moves it, or that waits on the user and is no entry of the change's own `depends-on` off a cycle, `next` sends the coordinator the change's paths, with the step to take.
        - It sends it once per change and set of such tickets after the change's last log line, or, where the paths reach a cycle of links through such a ticket, once per cycle after the last log line of the cycle's tickets, whichever change waits.
    - The message on a ticket that has had no step gives the paths of each change that waits on it.
    - Where a ticket outside `tickets/closed/` has waited on nothing that moves it for `AGAIN_SECONDS`, `next` sends the coordinator a message on it once, with its log and its agents, and records it in a `bug` ticket; one message gives each such ticket that no earlier message gave.
    """)
"""The help on the paths of links and the message on them."""

PARTS = {
    HelpPart.NEXT: mctx("""
    - `next` prints the next step of the operator whose agent id it is given: one call to make, or several launches to make in one message, with their parameters, or the final reply.
        - With a launch, it also prints each further launch that it gives on the state with the launches before it made, until one of these holds:
            - A step that `next` prints ahead of every launch is ready and the output does not hold it.
            - The operator is past its context bound.
            - The pending agents of the session's operators, the launches included, number the harness's limit of concurrent subagents, as `--help pace` gives it.
            - It gives no further launch.
        - Among those further launches, it passes over each step that is no launch, and each launch on a held step that a reply landing during its read of the state can end, and a later call gives each step it passes over.
        - Before the final reply, it prints a SendMessage call that sends the reply's text to the agent that launched the operator.
        - It then prints the SubagentHandback call whose message is the line that says so.
        - It writes the brief of a launch, and a message to an agent other than the coordinator, to a file under the session's scratchpad, and the call's prompt or message gives that file's path.
        - The value of a prompt or a message parameter it prints stands between two lines of three backticks, and the value to pass is the text between those lines, without them.
        - A message to the coordinator that gives labeled items keeps its first line and gives the path of the file that holds its items.
        - The brief of a launch other than a solver pass's gives the file the agent writes its final reply to.
        - The brief of a code editor's launch ends with the line `Budget: N minutes`, followed on that line by what the agent does at its budget, where `profile_runs.py --help budget` gives a budget for the brief, as a brief of the type `code-editor`, over every run under the project directories.
            - N is that budget in minutes, rounded up.
        - An agent whose latest notification has the status `failed` and a summary that gives `{rate_limit}` was stopped by the usage limit.
            - `next` counts such an agent as running, and takes nothing from that notification as its report.
            - The usage cache is `$CLAUDE_CONFIG_DIR/usage-api.json`, or `~/.claude/usage-api.json` where that is unset. A read of it first runs `~/.claude/scripts/fetch-usage-api.sh` where the cache is missing or past the age from which that script fetches again.
            - A cache fetched less than {stale} seconds ago gives the usage limit as in force where a window is at `used_pct` 100 or more, and as lifted where each window is under 100. Any other reading leaves the limit unknown.
            - Once the cache gives the limit as lifted, after that stop, `next` prints, ahead of every other step, a SendMessage call that asks the agent to continue its work, once for each such stop.
        - Where no other step is ready and a launch it would give is of an agent type that the operator's agent listing lacks and whose rendered definition `.claude/agents/<agent type>.md` stands in the main tree, it prints the launch of an agent whose end resumes the operator, unless one such runs, then that the operator ends its turn.
        - Where no step is ready, it blocks for up to {block} seconds until one is, then prints it, or prints that the operator runs it again.
            - The block also ends, and it prints that the operator runs it again, once a message to the operator waits that the harness accepted after the latest `user` entry of the operator's transcript before the call.
        - Where its calls in a row have found no step ready for {idle} seconds or more, from the start of the first of them, it prints, in place of that the operator runs it again:
            - Where an agent the operator launched is pending, or a call of `wait` by the operator runs, that the operator ends its turn, after a call of `wait` in the background where none runs.
            - Otherwise the final reply for a wait, which hands the operator's lines to the operator launched after it.
        - Where state read/planning has no result after {limit} seconds, it prints a failure report for the coordinator and ends with failure. Send the report, then run the command again to continue your procedure.
            * comment: Change 11-2484: 11-2473 records repeated interrupted reads reported as nothing ready.
        - A call of `next` or `relay` ends each call of either for the same agent id that runs.
    - Before the call it prints, `next` prints that step's key, on a line that gives the command to run after the call, and before several launches, one line that gives each launch's key, in their order, and the command to run after them.
        - The key is the same at each read of the state that gives the same step.
    - A ticket file whose read refuses or fails, other than a file that moved during the read, leaves its ticket out of every procedure.
        - A ticket that depends on it waits.
        - `next` gives that file, once for each content it has and once its last write is {write} seconds old, to a ticket analyst it launches, as a step it cannot place, with the read's failure, and goes on with every other procedure.
        - Where the file still does not read once that analyst returned, the final reply gives it.
    """),
    HelpPart.JOURNAL: mctx("""
    - `next` runs each Bash step itself, in the main tree, and prints no Bash call.
        - Before it reads the state, it waits for each Bash step of the session that runs, that of another operator of the session included, for up to {block} seconds from its start, and where one still runs then, it prints that the operator runs it again.
        - A Bash step runs with the environment of `next`, which `uv run` sets, with no input, and its output goes to a file under the session's scratchpad, which `next` reads once the step ends.
        - It ends a Bash step that runs past {run} seconds, and that step counts as failed.
    - `next` records each step it gives, by its key, in the session's step journal, `{journal}` under the session's scratchpad, and tells from that journal alone whether a step is in flight, done or failed.
        - A printed message counts as made by a SendMessage call to its recipient that holds its text, and a printed launch by an Agent call that gives its description, that the operator made after the call of `next` that printed it and before its next call of `next`, and the step's outcome is that call's.
        - Where the operator ran `next` again first, or its work ended with no such call, the step counts as failed.
        - A step in flight is not given again, to that operator or to one that takes over.
        - A step's key is taken over what the step is, what it acts on and the event it answers, never over its text.
            - The key of a launch or a command of a held change also takes in the version of the change's inputs: the time of the latest of the change's filing, a report of an agent that an operator of any session launched on it, the filing of a ticket on it, and a line of its log that no operator wrote, other than a take or a release.
        - A step that is done is not given again, other than a launch or a command of a held change that the change's procedure still gives once a wait has passed after its done outcome, which `next` gives once more.
            - Where that step is done a second time, `next` gives in its place, once that wait has passed after that outcome, a message to the coordinator on the change, with the line that makes the step due once more.
        - The times a step was given in a row are the times it was given and failed, other than a launch the harness refused at its limit of {subagents} concurrent subagents.
            - `next` gives such a launch again once a wait has passed after the refusal, a wait that doubles at each such refusal in a row, up to a cap.
                - While such a launch waits, `next` gives no final reply, and where no other step is ready, it waits for one as it does where no step is ready.
        - An end of turn that `next` prints with the launch of an agent whose end resumes the operator counts as a time the launch it holds back was given and failed.
        - Once a step was given {bound} times in a row, `next` gives it no more: it retires the step for each operator of the session, files one `bug` on it with its key and the function that gives it, and goes on to the next step, and the final reply gives the step.
            - Where a held change's procedure still gives a retired launch or command, `next` gives in its place the message to the coordinator on the change that a step done a second time gets.
            - The retirement of a launch or a command of a held change holds at each version of the change's inputs, until an `Op override: give again` ruling on the step's key without the version.
    """),
    HelpPart.RULINGS: mctx("""
    - `next` applies the rulings that the coordinator gives an operator of the session, and that the reply of a ticket analyst on a held step gives, each a line in one of these forms, matched whole, past a list marker:
        - `Op decision: <decision key> <choice>` rules a held step, with one of the choices that step gives.
        - `Op override: <task id> <pass> <override>` gives the override, labelled as an override, in the brief of the next launch of that pass on that task.
        - `Op override: pass over <step key>` passes over the step whose key it gives, for each operator.
            - `next` gives that step, once, as one its procedure waits on, to a ticket analyst it launches to rule it, other than a launch of a ticket analyst to rule a step, and goes on with the other procedures.
            - A pipeline whose next pass is passed over stops instead.
            - A ruling on a solver pass holds for each pipeline on its task, unless the work set aside for an earlier pipeline on that task went back (`restore`) after the ruling and before that pipeline's line or `start` call.
            - A solver pass's key is `<task id>-<pass>`, its task id and its pass (`analyze`, `create` or `refine`).
                - A ruling can name a pass that was never printed.
        - `Op override: give again <step key>` makes the step whose key it gives due again, for each operator: `next` counts for nothing the outcomes of that step that came before the ruling, its retirement among them, and an earlier `pass over` ruling on it.
    - A coordinator's line that opens with `Op override:` or `Op decision:` in none of these forms goes back to the coordinator once, as undecided.
    - A ticket analyst's reply on a step that gives its decision key, with no ruling in these forms, goes back to it once.
        - Where its answer gives none either, the step stays held.
        - Where the first line of the step gives one ticket or more, each as `change <number>` or `draft <number>`, and each stands under `tickets/closed/`, the reply does not go back.
    - A step `next` cannot place gives no decision key: its ticket analyst makes the act it needs and gives no ruling.
    """),
    HelpPart.RUN: mctx("""
    - `next` reads a coordinator's line `Op run: <path>` as a run: the solver pipelines that the Python script at `<path>`, absolute or relative to the main tree, starts.
        - Write a run script under `work/runs/` in the main tree.
        - It defines `starts(run: Run) -> Iterable[Start]`, with `Run` and `Start(task, passes)` from the module `operations.runs`, each `passes` a non-empty sequence whose every item is `analyze`, `create` or `refine`.
        - `run.queue` gives the task ids of the queue, in the order of their names, less each task a claim file gives and each task of the run's pipelines.
        - `run.running` and `run.ended` give the run's pipelines, each with `task`, `passes`, `stopped`, `held` and `passing`.
            - `stopped` gives, for an ended one, the reason it stopped, or None where it ran to its end.
            - `held` gives whether an `interference` ticket on its task, filed since it started, holds its next pass or its end.
            - `passing` gives whether a pass of it runs, or is to launch while it is not `held`.
        - Once an `interference` ticket on a task closes while a solver stands for that task and no solver pass of the session on that task was launched at or after that closure, `next` launches an agent that fixes in place what that closure leaves wrong in the solver. Until that fix returns, a pipeline of the session on that task launches no further pass and does not end, and that wait makes neither `held` nor `passing` true.
        - At each read of the state, `next` loads the script again and calls `starts`.
        - `next` gives as a step the `start` of the first item `starts` gives whose task no pipeline of the session runs on, and on which no such fix is due or runs, and that matches no pipeline of the run by task and passes, and passes over each other item.
            - That `start` has as `<run>` the time of the line's message and its path.
        - A `start` on a task whose claim file stands ends that pipeline, with the failure's text as its reason.
        - The line is done once no pipeline of the run runs, no fault of the load or of `starts` stands, and `starts` gives nothing to start.
        - The script may define `takes(ticket: RunTicket) -> bool`, with `RunTicket` from the module `operations.runs`, which the same load calls on each ticket outside `tickets/closed/` and `tickets/deferred/`.
            - A `RunTicket` gives:
                - `number`, `kind`, `status`, `domain`, `subject`, `filer` and `depends_on`: the ticket's.
                - `waits_on`: the change it waits on, or None.
                - `filed_by_run`: whether a pipeline of the run, running or ended, filed it.
                - `reached_by_run`: whether a chain of `depends_on` and `waits_on` links reaches it from a ticket such a pipeline filed.
            - From the line on, also once it is done, the operator launches a ticket analyst on an untaken ticket, and takes an untaken change, only where the `takes` of each run whose script defines one gives `True` for it.
                - A ticket an `Op expedite:` line gives passes, and so does a change that an operator took before and that went to `tickets/released/`.
    - A fault of a script that an `Op run:` or an `Op pace:` line gives is a load that fails, a call of one of its functions that raises or gives a result in no form this help or `--help pace` gives for it, or a load and calls that run past {script} seconds.
        - While a fault stands, the result of each call it touches is held back: a fault of a call touches that call, and a fault of the load or of the time touches each call.
        - With `starts` held back, the run starts nothing.
        - With `takes` held back, the run takes no ticket, unless the script loaded and defines no `takes`.
        - The coordinator gets the text of each fault, once for each distinct text.
    """),
    # User, session 2384db39-7d21-4d8d-8dda-bfd52bd69360, 2026-10-20T18:03:23Z:
    # "i just dont want claude usage pacing to limit it unnecessarily". Ticket 11-2458.
    HelpPart.PACE: mctx("""
    - `next` reads a coordinator's line `Op pace: <preset> [<argument> ...]` or `Op pace: <path>` as the Claude usage pace of each operator of the session, and the last line in one of these forms stands. An `Op pace:` line in neither form goes back to the coordinator and leaves the pace as it was.
        - In the first form, presets joined by `;`, such as `Op pace: even --window five_hour; by 2026-10-21T20:00:00-04:00`, give one pace: within it where each preset's pace is, and its cap is the smallest of the presets' caps.
        - Past the pace, `next` holds Claude launches and resumes. Codex launches and resumes, including their Haiku wrappers, are exempt. A resume keeps its launch's pace treatment across a mode switch. Messages that start no run and steps that run no agent stand.
        - Outside Codex mode, the pace also holds untaken tickets and changes. In Codex mode, tickets and changes can reach their concrete next launch, which the pace holds where it is Claude work.
        - While an `Op pause.` line stands, one call of `next` takes each change an `Op expedite:` line gives, each change that settles an `interference` ticket and each change an operator took before, and at most one other change, so that the pause is read again before each further take.
        - An `Op pace:` line of presets caps pending Claude workers of the session's operators, including launches of that call and excluding Codex wrappers. For each preset, the cap is the larger of 1 and the ceiling of {subagents} times the slack over {band} percentage points, and at most {subagents}.
            - The slack is the number of percentage points by which the window's `used_pct` falls below the bound that the preset gives.
            - Where the pending Claude workers number the cap or more, `next` holds Claude starts as past the pace and can continue to eligible Codex work.
        - The harness's limit of {subagents} concurrent subagents counts all pending agents.
        - Where no step is ready and the pace holds back a step, `next` prints that the operator runs it again, with the time from which a preset's pace admits agent starts, with the path of the script whose pace holds them back, or with the cap that holds them back.
    - The Claude pace reads the usage cache that `--help next` gives: for each of its windows, `used_pct`, `elapsed_pct` and the time it resets.
    - The presets:
        - `even [--factor F] [--window W]`, with F {factor} and W `{window}` by default: within the pace while the window's `used_pct` is at most F times its `elapsed_pct`.
        - `by <ISO 8601 time> [--window W]`, the time with its time zone and W `{window}` by default: within the pace while the window's `used_pct` is at most the percentage that has passed of the time from the window's start to the given time, and always from that time on.
        - `asap`: always within the pace.
    - The pace `even --factor 1 --window five_hour` holds under each `Op pace:` line of presets, joined to them as `;` joins presets, unless one of them reads the `five_hour` window. It holds as well under each `Op pace: <path>` line, with its cap, while the script's `paces` gives `True`, and counts as past there where the usage cache holds no fresh reading of the `five_hour` window. With no `Op pace:` line, it is the pace.
    - Where the usage cache holds no reading of a preset's window fetched less than {stale} seconds ago, that preset's pace counts as past, and the coordinator gets a line that says so.
    - `Op pace: <path>` gives the Python script at `<path>`, absolute or relative to the main tree, which `next` loads at each read of the state.
        - It defines `paces(usage: Usage) -> bool`, with `Usage` from the module `operations.pacing`, which gives `True` where the pace admits agent starts now.
        - `usage.now` is the time in seconds since the epoch, and `usage.windows` maps the name of each window of which the usage cache holds a reading fetched less than {stale} seconds ago to a `Window` with `used_pct`, `elapsed_pct` and `resets_at`, the last in seconds since the epoch.
        - With `paces` held back by a fault of the script, as `--help run` gives it, the pace counts as past.
    """),
    HelpPart.SEND: mctx("""
    - `send` records each non-blank line of its stdin, with the time of the call, in the session's store, under `.cache/op-lines/` of the main tree, for the operators of the session.
        - Each line is in a form the brief of an operator gives, as [An operator's brief](prompts/agents/notes/launching.md#an-operators-brief) gives it.
        - Where any line is in no form `next` reads, or is a ruling, an `Op pace:`, an `Op scope:`, an `Op pause` or an `Op resume` line in no fixed form, it records no line, prints the lines it refused, and fails.
        - Before recording, it checks the releases of explicitly listed draft requests in `Op expedite:` lines. A refusal records no line and moves no ticket.
        - After recording, it releases those requests to their normal untaken queue. If a release is refused, `send` fails and prints the reason. Run `send` again with the same lines to finish pending releases.
        - On success it prints the message that the coordinator sends alone to its running operator launcher, or, where none runs, gives as the brief of a new operator launcher.
    - `next` reads each recorded line as a line of the coordinator's to the operator of the session that ran at the time of its record, or, where none ran, to the next operator launched.
    - After the session's first recorded line, `next` reads each line of a message of the coordinator's, other than the message `send` prints, as in no form, and gives it back to the coordinator once as undecided.
    """),
    HelpPart.RELAY: mctx("""
    - `relay` prints the next step of the operator launcher whose agent id it is given, in the forms of `next`.
        - Where an operator of the launcher's runs and no message of the coordinator's waits for it, it prints at once, with no block, that the launcher ends its turn with no call.
            - Where a message to the launcher waits that the harness accepted during the call, as the block of `next` reads one, it prints instead that the launcher runs the command again.
        - Its first step launches an operator whose brief is the launcher's brief.
        - Each later message of the coordinator's to the launcher goes, unchanged, to the operator of the launcher's that runs, or, where none runs or the one that runs sent the launcher its final reply, into the brief of the next operator it launches, which is the message `send` prints where no message waits.
        - Where an operator's final reply ends it for its context, it launches a fresh operator.
            - Where the launcher's context is past the bound `uv run python scripts/operate.py bound` prints, it sends the coordinator instead the launcher's final reply, which asks for a fresh operator launcher whose brief is that of the next operator, and gives it.
        - Where an operator's final reply ends it for a wait, and no message of the coordinator's waits, it prints a call of `wait` in the background and that the launcher ends its turn, or, where that call runs, the end of the turn alone; once that call has completed, or once a message waits, it acts as after a final reply for the operator's context.
        - Where an operator ends with no final reply, it acts as after a final reply for the operator's context, unless the operator launched before it also ended with no final reply and each of the two ended within {idle} seconds of its launch.
        - It sends the coordinator any other final reply of an operator, and the end with no final reply that follows a quick end with none, after a line that gives that operator's agent id.
            - It then prints the launcher's final reply, unless a message of the coordinator's waits for a next operator.
    """),
    HelpPart.REVIEW: mctx("""
    - `review` prints, to the code editor or the doc editor whose agent id it is given, which an operator of the session launched, the step `next` would give next on its change with that editor ended, where that step is the launch of a design reviewer, an item checker, a decision analyst or a doc reviewer, in the form of `next`'s, with the brief `next` gives that agent and the editor as its launcher.
        - Where its call is not one that counts for the editor, it prints, with no block and no read of the state, the call in the form that counts and that the editor runs it in the foreground and does as it prints.
            - A call counts where it is a command of its own, with no word such as `timeout` before it, and no other tool call follows it.
        - It takes as the editor's report the text of the report file the editor's brief gives.
            - Where that file does not exist, it prints that the editor writes it and then runs `review` again.
        - Where the change is past its cost budget, it prints instead that the operator takes the change's next step, and that the editor gives its final reply.
        - Where an editor the change's ticket gives has no agent in the worktree, or another editor of the change there ended with no report since its launch or its last resume, it prints instead that the operator launches the checks, and that the editor gives its final reply.
        - Where an agent that another editor of the change launched has not given its final reply, or another editor of the change there has not ended, it blocks, as the block of `next` does, until this help gives the editor another line, and then prints that line, or, where the block ends first, that the editor runs `review` again.
            - An editor has reported while its last tool call is a `review` call, from the start of the first of its `review` calls since its last other call.
            - Where each other editor there that has not ended has reported, and each agent another editor of the change launched has given its final reply, of the editor and those editors, the one whose report is latest, or of those with the latest, the one of the first agent id in sort order, gets with no block the line this help gives where each of the others had ended, and each other one blocks.
        - Where that step is none and an agent the editor launched has not given its final reply, it prints that the editor waits on each such agent, and runs `review` again each time one of them gives its final reply.
        - Otherwise it prints that the editor gives its final reply.
        - It reads the state as the editor's operator's `next` reads it, with the same foreground bound and timeout report.
    """),
    HelpPart.WAIT: mctx("""
    - `wait` blocks for the operator whose agent id it is given, or, for an operator launcher's, for the last operator that launcher launched, and prints nothing: its caller runs `next` or `relay` again once it completes.
        - It reads the state as that operator's `next` reads it, and blocks as the block of `next` does, until a step is ready other than that the operator runs `next` again and its final reply for a wait, the pace's hold on the operator's steps ends, or {cap} seconds pass.
        - Where the pace holds the operator's steps until a time, the block ends by that time.
        - Where a call of `wait` for the same agent id runs, it ends at once.
    """),
    HelpPart.ALERTS: ALERTS + "\n" + WAITS_HELP + "\n" + concept_faults.HELP,
}
"""The text of each part of the help."""
