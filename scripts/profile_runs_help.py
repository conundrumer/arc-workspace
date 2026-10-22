"""The help text of `profile_runs.py`, in parts: `USAGE`, which `--help`
prints, each part `--help PART` prints, and the values their holes take."""

from enum import StrEnum

from controlled_markdown import mctx
from budgets import BUDGET_FACTOR, LOW_WAIT_PCT, MEDIAN_RUNS
from command_labels import KNOWN, RUN_DL
from context_bound_hook import OPERATOR
from open_agents import HUNG_FACTOR
from run_prints import RECENT_CALLS
from run_profile import COMMAND_WIDTH
from operations.constants import BLOCK_SECONDS
from operations.roles import GENERAL


ISO_TIME = mctx("an ISO date or datetime, in UTC where it gives no offset")
"""The times `utc_time` reads."""

# Kept: ticket 6-145, the coordinator estimated by hand the cost of a switch
# of auditors to Sonnet from repriced figures, and was wrong.
REPRICED = mctx("each token cost is of the same requests at the same token "
                "counts, priced at {model}; it is not what these runs would "
                "cost had they run on {model}")
"""What a token cost repriced at `--price-at MODEL` is."""


class HelpPart(StrEnum):
    """Each part of the help, by the word `--help` takes to print it, in the
    order the bare `--help` lists them."""
    RUNS = "runs"
    ONE = "one"
    MANY = "many"
    BUDGET = "budget"
    UNDER = "under"
    RUNNING = "running"
    MESSAGES = "messages"
    COMMANDS = "commands"
    OPTIONS = "options"


USAGE = mctx("""
    - Usage:
        ```
        uv run python scripts/profile_runs.py ID [ID ...] [--type TYPE[,TYPE]] [--pct P] [--top N] [--runs] [--since DATE] [--price-at MODEL] [--split TIME]
        uv run python scripts/profile_runs.py --each ID [ID ...] [--type TYPE[,TYPE]] [--pct P] [--top N] [--since DATE] [--price-at MODEL] [--split TIME]
        uv run python scripts/profile_runs.py --under ID [--pct P] [--top N] [--since DATE] [--price-at MODEL]
        uv run python scripts/profile_runs.py --running ID [--calls-since TIME]
        uv run python scripts/profile_runs.py --pending ID
        uv run python scripts/profile_runs.py --open ID
        ```
    - An `undecided` line on stderr gives each value the tool cannot give and each fact it cannot decide, with its reason, and each distinct line is printed once.
    {parts}
    """)
"""The help the bare `--help` prints."""

PURPOSES = {
    HelpPart.RUNS: mctx("what an ID names, the zone of the times, how a run's wall time is cut into parts, and its token cost"),
    HelpPart.ONE: mctx("what one run prints"),
    HelpPart.MANY: mctx("what `--each`, more than one run and `--split` print"),
    HelpPart.BUDGET: mctx("the budget of each agent type and role"),
    HelpPart.UNDER: mctx("what `--under` prints"),
    HelpPart.RUNNING: mctx("what `--running`, `--calls-since`, `--pending` and `--open` print"),
    HelpPart.MESSAGES: mctx("the messages from a listed agent's parent, its active time and self time"),
    HelpPart.COMMANDS: mctx("how a call's command is printed and labelled"),
    HelpPart.OPTIONS: mctx("the options, each with what it does"),
}
"""What each part of the help gives."""

# The user's choice, session 2384db39, 2026-10-20T21:45:12Z, "3 ensure":
# "Reviews check what Codex itself did in each run." Ticket 11-2530.
PARTS = {
    HelpPart.RUNS: mctx("""
    - An ID is an agent id, a session id, or the path of a `.jsonl` transcript.
        - A session brings its main transcript, as type `main`, and the run of each of its subagents.
    - A run is the transcript of one agent, or where the top-level session takes a new session id while a subagent runs, that subagent's transcripts under each session's directory.
        - Each such transcript under a later session goes on from the one before it, its first entry answering that one's last.
        - A run's agent type, description and launching call are those the earliest of its transcripts' `.meta.json` files that gives each gives.
        - Where the agent launches Codex, these are the launcher's transcripts; the separate Codex section measures the work attributable to that run.
            + xref: scripts/run_prints.py:print_codex
    - Each time the tool prints is in UTC, as `YYYY-MM-DDTHH:MMZ` where no item below gives another form.
        - A DATE or TIME it reads is {iso_time}.
    - A launcher's wall time, from its first entry to its last, is cut at each entry's time, and each interval goes to one part:
        - `tools`: a tool call is pending.
            - A Bash call is labelled by the known commands it runs, joined by ` + `: {known}, and `{run_dl}` with its subcommand; or, where it runs none, by the first program it runs past setup, and any other call by its tool.
        - `waits`: a foreground Agent, Monitor or TaskOutput call or a poll is pending, or the turn has ended while an agent or command the run backgrounded is running.
            - These are labelled `agent TYPE`, `poll` and `bg LABEL`.
        - `model`: no call is pending and the turn has not ended.
        - `idle`: the turn has ended and nothing the run launched is running.
    - A turn starts at a message the model answers, and at the run's last `user` or `assistant` entry where that is a message the model has not answered yet.
        - A local command, such as /compact, and the harness's note that the user interrupted the run start none.
    - A turn ends at the model's last entry, at the result of a call that ends it, such as SubagentHandback, or at the harness's note that the user interrupted the run, unless the next `user` or `assistant` entry after that note is the model's.
    - Calls that are pending at once share an interval in equal parts.
    - While the model works, backgrounded work that runs goes to `model`.
    - A poll is a Bash call that runs `sleep` and none of the known commands.
    - A command the harness moves to the background on its timeout counts under its own label up to then, and under `bg LABEL` after.
    - A command the run backgrounded runs until a notification of it in the run's transcripts, other than in an assistant entry.
        - Where none follows, it runs while a process holds open the output file its result names, and where no process holds that file, it ended when the file was last written, or, where that file is gone, at the run's last entry.
        - Where its result names no file, whether it runs is unknown, and it counts as running.
        - Where `lsof` writes to stderr, which files a process holds open is unknown, and the ID is refused.
    - A launcher's token cost is the list price of the tokens its requests used, from the price table of `token_prices`, each request priced once at the full usage its entries give.
        - A launcher with a request whose model or usage the table does not price has an unknown cost, printed `?`.
        - A run with unpriced Codex work has an unknown complete cost; the launcher's dollars and Codex token counts stay separate.
            + xref: scripts/run_prints.py:print_codex
    - `--price-at MODEL` prices each launcher request at the prices the table gives MODEL, in place of those of the model that made it, and a MODEL the table does not price is refused.
        - Where it is given, the tool first prints `price at MODEL:` and that {repriced}.
    - A run whose agent type is unknown is refused, and so is an ID that names transcripts that differ and are not the transcripts of one run.
    """),
    HelpPart.ONE: mctx("""
    - One run, and each run `--runs` prints, prints its launcher wall time and its launcher token cost, then these lines:
        - after `repeated:`, each Bash command it ran more than once, with the number of times, or `none`;
        - after `refused:`, the number of its calls whose result gives a refusal;
        - after `hung:`, the number of its calls that ran, or are in flight and have run, past {hung} times the usual time of their label;
            - the usual time of a label is the median duration of the run's own other ended calls with that label, or where it has none, of the other ended calls with that label of the runs profiled, or where none has one, {block} seconds;
        - after `alerts:`, each kind of monitor's alert on it that a message to it holds on a line of its own, with the number of such messages, or `none`.
    - One run prints its parts and its labels by time, with each label's share of the wall time and its calls, and for backgrounded work the time it ran from launch to its notification, or for a command that ended with none, to its end.
    - One run of a subagent, completed or not, also prints each message from its parent, as `--help messages` gives those messages, with the time it arrived, its active time and its self time.
        - A message's active time is the run's wall time less `idle` over that message's period.
        - Its self time is its active time less the run's waits on agents over that period.
        - A wait on agents is an interval in which an Agent call of the run is in flight, in the foreground or the background, and the run is not generating and blocks on no `tools` call.
        - A run with an unknown message prints no active time and no self time.
    - Under `--each`, each run also prints its budget, and marks `past budget` each message whose self time is past that budget.
        - A run's budget is the budget `--help budget` gives its brief, as a brief of the run's type or role, over every run under the project directories.
        - A run with no budget prints none.
    - The Codex section gives the attributable work's role, elapsed time, calls and their timing where recorded, token counts, transcript read command and coverage gaps.
        + xref: scripts/run_prints.py:print_codex
        - Its elapsed time can overlap launcher wall time.
            + xref: scripts/run_prints.py:print_codex
        - Its turn start and end times are Unix timestamps in seconds; call times keep the source's ISO timestamps.
            + xref: scripts/run_prints.py:print_codex
        - Its budget is taken from the work role by the rules of `--help budget`, and its elapsed time is marked `past budget` where it exceeds that budget.
            + xref: scripts/run_prints.py:print_codex
        - A `review required` mark means the budget is unknown or the work evidence is incomplete.
            + xref: scripts/run_prints.py:print_codex
        - A role, budget, duration or complete cost the evidence cannot establish is unknown.
            + xref: scripts/run_prints.py:print_codex
    - One run of a subagent also prints, after `received report:`, the latest report received after the parent's latest message to it, with the entry's time, its kind and the start of its text.
        - Where no report was received after that message, it prints `none after the message at` and that message's time.
        - Reports are read from each transcript of the sessions of the agent's run; `--running` also reads the sessions of the run that launched it.
            + xref: scripts/agent_reports.py:reports, scripts/agent_launches.py:launches
    - An entry gives a report where it is:
        - `notification`: a notification of the agent with the status `completed` and a result, other than one whose note says the agent stopped with background work of its own still running;
        - `result`: the result of a foreground Agent call that launched the agent;
        - `message`: a message from the agent.
    - A report's text is the entry's text, and of a message that delivers the agent's SubagentHandback, that text without the harness's preamble and indent.
        - An entry whose text is the harness's pointer to such a message, or the line an agent gives after it sent its final reply by SendMessage, gives no report.
        - A report whose text is the path alone of a report file that `operate.py next` gives in a brief is that file's text, where it is the latest report that gives that path.
            - An earlier report that gives that path, and a report whose file is gone, keep the path as its text.
    - Where the latest message from the parent is unknown, it prints `?`.
    - A notification or a launch result whose status is of no known form gives no report, and where no `.meta.json` of the run gives a `toolUseId`, no launch result is matched to it.
    - A notification that gives no status, such as a Monitor event or one that says the agent was resumed, gives no report and no sign that the agent stopped.
    - A launch result whose status is of no known form counts as not in the background, wherever it is read.
    """),
    HelpPart.MANY: mctx("""
    - `--each` prints, for each run the IDs bring, in their order, what one run prints, and then, where it profiles more than one run, what more than one run prints.
    - More than one run prints, in order:
        - per agent type, the number of runs, the minimum, median, P-th percentile and maximum of wall time, the total, the median and P-th percentile of active time, which is wall time less `idle`, and each part's share of the total;
        - per agent type, the total token cost of its runs of known cost, its share of that total over all types, the median cost of such a run, and the number of runs of unknown cost it leaves out;
        - each type's labels by time, with the number of runs each appears in.
    - `--split TIME` prints last, per agent type, for its runs whose first entry is before TIME and for those at or after it, apart: the number of runs, the median context per request over all their requests, the median context of a run's first request, and the median token cost of a run of known cost.
        - A request is one that `token_prices.requests` gives, and its context is what `token_prices.request_input` gives for its usage.
        - A type with no run on one side prints `-` for that side.
        - A median over no value prints `?`.
        - A run whose start is unknown joins neither side.
    """),
    HelpPart.BUDGET: mctx("""
    - More than one run also prints the budget of each agent type, which is {factor} times a median wall time, printed with the runs it is taken over.
        - In place of a budget of type `{general}`, it prints one for each role of `operations.roles.GENERAL_ROLES`, taken over the runs of type `{general}` whose description `operations.roles.described` gives that role, and a run of that type whose description gives no such role joins no budget.
    - That median is taken over the runs an operator launched.
        - An operator launched a run where its parent, as `--running` gives it, is an agent of type `{operator}`.
        - A run whose parent's type no transcript of the sessions of the run gives is left out.
    - A brief gives items where its first line is one of the lines `operations.briefs` gives for a brief of several items of the same work, each item a ticket number.
        - Where the brief of some run of a type or a role gives items, it also prints, on a line led by `per item`, the budget per item of that type or role, which is {factor} times the median of the wall time per item, a run's wall time over the number of items its brief gives.
        - That median is taken by the lines below over the runs an operator launched whose brief gives items.
    - The budget of a brief is the budget per item of its type or role times the number of items it gives, where it gives items; where it gives none, it is the budget of its type or role.
    - The lines below narrow the runs each median of this part is taken over.
        - The window of a role of `operations.roles.GENERAL_ROLES` is the runs whose first entry is at or after the last commit that changed `src/operations/briefs.py`.
        - The window of a type that has an agent document under `prompts/agents/` is the runs whose first entry is at or after the last commit that changed one of its prompt's sources.
            - A type's prompt's sources are its agent document, each document that document includes or inlines, each lib file its rendered prompt holds, each script under `scripts/` its rendered prompt names, and each package under `src/` its rendered prompt runs with `-m`.
            - A module such a script or package imports is no source of the prompt.
        - `--since DATE` sets the window of every type to the runs whose first entry is at or after DATE.
        - A type with no agent document has a window only with `--since`.
        - A type or role whose paths no commit changed has no window.
        - Where the window of a type or role holds at least {median_runs} of the runs that median is taken over, the median is taken over the runs in the window.
        - Where a type or role has no window, or its window holds fewer of those runs, the median is taken over those of the runs that median is taken over whose `waits` and `idle` together are under {low_wait_pct}% of wall time.
            - A type or role with fewer such runs gets no budget, and a brief of it gets no `Budget:` line.
    """),
    HelpPart.UNDER: mctx("""
    - `--under ID` profiles the runs under the run ID, where ID is a session id or an agent id: the agents whose `.meta.json` gives the run ID as `parentAgentId`, or for a session gives none, the agents whose `.meta.json` gives one of those, and so on.
        - Its previous call is the latest of these calls of `--under` on the same ID that ran in full:
            - each call an agent of type `{operator}` made, in any transcript under the project directories that changed at or after the run ID's first entry, whose time is that of the entry that makes it, and whose agent is that agent;
            - each Bash step that `next` ran, as the step journal of the run ID's session gives it, whose time is the time `next` gave it, and whose agent is the operator `next` gave it to.
            - The call may write the ID with or without the `agent-` prefix.
            - A call ran in full where its result holds one `left open:` line and one `runs taken:` line, the count on the `runs taken:` line followed by as many agent ids, and:
                - for a call an operator made, its result says the call completed in the foreground with no error and was not interrupted;
                - for a step, it ended with exit status 0.
            - A step's result is its output.
            - An operator's call's lines are read from its result's content, or, where that content is the harness's `<persisted-output>` preview of a large output and the result gives a `stdout`, from that `stdout`.
            - A line counts only where a line break ends it.
            - A call whose result holds more than one `left open:` line counts as none.
        - Where a previous call stands, it considers the runs whose last timestamped entry is after that call's time and each run that call's `left open:` line gives, and where none stands, every run under the ID.
            - Of those, it takes each run whose work is not open, by the rule by which `--running` lists an agent, as `--help running` gives it, and leaves out the others.
        - It prints, in order:
            - `left open:` and the agent id of each run it left out, separated by spaces, or `none`;
            - `runs taken:`, their count, and the agent id of each run taken, separated by spaces;
            - `previous call:` and that call's time, as `YYYY-MM-DDTHH:MM:SSZ`, with `by` and the agent id of that call's agent, or `none`;
            - the line `--runs` prints for each run taken, in the order of their first entries, and what one run or more than one run prints.
    """),
    HelpPart.RUNNING: mctx("""
    - This text gives the rules of `--running`, what it prints for each agent, and then `--calls-since`, `--pending` and `--open`.
    - `--running ID` lists the agents under the run ID whose work is open, where ID is a session id or an agent id.
        - A run that goes on under a later session is listed under that session's id.
        - The agents are listed in launch order, each parent's agents after it.
    - Of the agents the run launched, the agents those launched, and so on, an agent's work is open where its turn is in progress, whether or not its parent's work is open, or where its turn has ended, its parent's work is open, and its work is not closed.
        - A parent's work is open where the parent is `main` or listed, and the run ID's work is open where it is `main` or would be listed under `main`.
        - An agent's turn counts as ended where it has ended, as `--help runs` gives when a turn ends, or where its parent has its result, or a transcript of the sessions of its run or of its parent's run holds a notification of it, and its transcript holds no `user` or `assistant` entry timestamped after the latest of those.
            - Where the turn of its parent, other than `main`, has ended, and the transcripts of its parent's run hold no result of the Agent call that launched it, that call was cut off with its parent's turn.
                + xref: scripts/open_agents.py:cut_off
                - Its turn then counts as ended where its transcript holds no `user` or `assistant` entry timestamped after the end of its parent's turn.
                - The end of its parent's turn is the end of its parent's own call, where that call was cut off; else the later of the time of its parent's last timestamped entry and the time of the latest result or notification of its parent in the transcripts of the run that launched its parent.
                    + xref: scripts/open_agents.py:turn_ended_at
    - A report of an agent received after the parent's latest message to it closes its work.
        - A report and the transcripts it is read from are as `--help one` gives them.
    - Each of these after the latest message the agent received from anyone closes its work:
        - a report;
        - a result of the agent's own SubagentHandback call that says the harness delivered its report;
        - a notification of it of a known status other than `running`, whose note does not say that the agent stopped with background work of its own still running;
        - the harness's note that the user interrupted the run, which is itself no message the agent received.
    - Where the parent's latest message to an agent is unknown, only the entries of that list close its work.
    - Where no transcript of the parent of the run ID, or of a parent above it, gives its launch, whether its work is open is unknown, and it counts as open.
    - Where the rules above give the work of an agent, of the run ID or of a run above it as not open, while its turn has ended and work of its own still runs, whether its work is open is unknown, and it counts as open.
        - An agent's work of its own is:
            - each command it backgrounded that is still running;
            - each agent it launched in the background that this rule does not reach, as `running:` gives such an agent, and whose launch no notification has followed;
            - each agent it launched whose turn is in progress or whose work of its own still runs.
    - For each agent it prints:
        - its agent id, type and launch description;
        - its parent, which is the agent id of the agent that launched it or `main`;
        - the time since its first entry;
        - its active time, with the time of the message it is measured from and, where that message's period has ended, the time it ended;
        - its self time;
        - its context size in tokens, which is the input of its last request;
            - for an agent of type `operator`, after its context size, `bound` and the bound in force, as `uv run python scripts/operate.py bound` prints it, in tokens, led by `past` where its context is past that bound;
        - its working directory, as its first entry gives it;
        - for an agent whose turn has ended, after `turn ended:`, the time its turn ended, which is the time of the last timestamped entry of its transcripts that ends a turn, as `--help runs` gives one, and the time since;
        - for an agent whose turn has ended, after `received report:`, what one run prints there, as `--help one` gives it;
        - its last text output, the end of the text of its last assistant entry that gives text;
        - each call it has in flight, with its label, its command and the time since the call;
        - after `running:`, each command it backgrounded that is still running, and each agent it launched in the background that is itself listed and whose launch no notification in the transcripts of the run that launched it has followed, each with its label, its command and the time since the call;
            - an agent this rule does not reach, because no transcript gives its launch or because no `.meta.json` of the sessions of the run that launched it gives that run as the parent of any agent, is printed there as well;
        - its last {recent} calls in order, each with its label, its command and its duration, or `pending`.
    - `--calls-since TIME` keeps of each listed agent's last {recent} calls only those that ended at or after TIME, and those that are pending.
        - It prints them after `recent since` and TIME, as `YYYY-MM-DDTHH:MM:SSZ`, and where it keeps none, prints `none` after TIME.
    - `--pending ID` prints the agent id of each agent pending to the run ID, one per line, in launch order, where ID is a session id or an agent id.
        - An agent is pending to the run that launched it from the Agent call that launched it, or from the last SendMessage call that resumed it, until the first of these:
            - the run holds the result of that Agent call, and the result does not say the agent runs in the background;
            - a transcript read as `--help one` gives for `--running` holds a notification of the agent, a notification that it stopped with work of its own still running among them;
            - such a transcript holds a message that delivers the agent's SubagentHandback.
        - A SendMessage call that the run or any agent of the run's sessions, main among them, makes resumes the agent.
        - A SendMessage call to an agent whose result says neither that it resumed the agent nor that it queued the message resumes none.
    - `--open ID` prints `open` where the work of the run ID is open, by the rule by which `--running` lists an agent, applied to the run ID, and `not open` otherwise, where ID is an agent id.
        - An ID that names a session's main transcript is refused.
    """),
    HelpPart.MESSAGES: mctx("""
    - The messages from a listed agent's parent are its brief, the messages its first turn answers, and each later message its parent sent: one the harness gives as from the parent's agent id, or, for an agent `main` launched, as from the coordinator or queued with no tag.
        - The origin the harness gives a queued message is the one its attachment gives.
        - A notification of the agent's own backgrounded work, a message from an agent it launched, from the user, from another agent, or, for an agent `main` did not launch, from the coordinator or queued with no tag, and a note of the harness are none.
        - A message from another agent is one the harness gives as from an agent id other than the parent's and those of the agents it launched.
        - A later message whose sender is none of these, or from an agent no transcript of the sessions of the run gives the type of, is unknown.
        - A line of a message from the parent that gives a file `operate.py next` wrote for the message is read as that file's text, or as the line itself where the file is gone.
    - The period of a message from the parent runs from it to the next message from the parent or from another agent, or to the run's last entry.
    - A listed agent's active time is its wall time less `idle` over the period of the latest message from its parent, with its wall time running to now where that period and its turn have not ended.
    - Its self time is that active time less its waits on agents over that period, as `--help one` defines them, with the time since its last entry a wait where it waits on agents at that entry.
    - An agent with an unknown message has no active time and no self time.
    """),
    HelpPart.COMMANDS: mctx("""
    - A call's command and an agent's text output are printed on one line, a command cut to its first {width} characters and a text output to its last {width}.
    - A call's command is:
        - for a Bash call, its command, led by the kind of each ticket it files, as `kind K:`;
        - for an Agent call, its description;
        - for a Write, Edit or NotebookEdit call, the path of the file it writes;
        - for a SendMessage call, its recipient, as `to R:`, and its message;
        - for a SubagentHandback call, its message;
        - for any other call, nothing past its label.
    - A call whose agent type is unknown is labelled `agent ?`.
    - A Bash call with no command is labelled `shell`.
    - A call whose input lacks a field its command reads, of those above but a SendMessage call's message, is printed without that field.
    """),
}
"""The text of each part of the help but `OPTIONS`, which argparse
prints."""

HELP_VALUES = dict(factor=BUDGET_FACTOR, median_runs=MEDIAN_RUNS,
                   low_wait_pct=LOW_WAIT_PCT, recent=RECENT_CALLS,
                   width=COMMAND_WIDTH,
                   iso_time=ISO_TIME, operator=OPERATOR,
                   general=GENERAL,
                   known=", ".join(f"`{label}`" for label in KNOWN.values()), run_dl=RUN_DL,
                   repriced=REPRICED.format(model="MODEL"), hung=HUNG_FACTOR, block=BLOCK_SECONDS)
