"""The prints of the agents whose work is open under a run, of the messages
from a run's parent, and of the run's received report, as
`profile_runs.py --help running` and `profile_runs.py --help one` give them."""

from collections.abc import Callable
from dataclasses import asdict
from datetime import datetime
import json

from agent_reports import Report
from budgets import GroupBudget, brief_items, of_budget, past_budget, role_group
from codex_transcript import Coverage, activity, read as codex_transcript
from context_bound_hook import bounded, context_bound, past_bound
from controlled_markdown import mctx
from open_agents import Listed, received_reports
from run_profile import clock, dollars, minutes, minutes_or_unknown, one_line
from run_records import Run, Span
from run_reads import MAIN
from ticketing.times import utc_stamp
from tree_reads import main_tree
from operations.roles import Role
from spends import union_seconds
from handbook.agents import agent_names


def print_codex(r: Run, budgets: GroupBudget | None) -> None:
    """Print fresh Codex measurements separately from the launcher profile."""
    result = codex_transcript(r.path)
    print(f"  Codex: {result.coverage}")
    if result.coverage is Coverage.NONE:
        return
    print(f"    transcript: uv run python scripts/codex_transcript.py {r.label}")
    codex = result.spend
    if r.cost is not None and codex.dollars_known:
        print(f"    total run cost: {dollars(r.cost + codex.dollars())} subscription dollars")
    else:
        print(f"    total run cost: unknown, at least "
              f"{dollars((r.cost or 0.0) + codex.dollars())} subscription dollars "
              f"(Claude cost unknown or Codex usage unpriced)")
    for role in sorted({s.role for s in result.spend.sources}):
        turns = [(s, t) for s, _, t in result.turns if s.role == role]
        sources = [s for s in result.spend.sources if s.role == role]
        complete = len(turns) == len(sources) and all(t.ended is not None for _, t in turns)
        elapsed = union_seconds([(t.started, t.ended) for _, t in turns
                                 if t.ended is not None]) if complete else None
        try:
            work_role = Role(role)
        except ValueError:
            work_role = None
        group = role_group(work_role) if work_role is not None else role if role in agent_names() else None
        budget = (budgets(group, brief_items(r))
                  if budgets is not None and group is not None else None)
        mark = ("past budget" if elapsed is not None and budget is not None and elapsed > budget
                else "review required: unknown budget or incomplete work evidence"
                if budget is None or elapsed is None or result.gaps else "within budget")
        print(f"    role {role}: elapsed {elapsed if elapsed is not None else 'unknown'} s; "
              f"budget {budget if budget is not None else 'unknown'} s; {mark}")
        print(f"      cost: {dollars(codex.dollars(role))} subscription dollars"
              + ("" if all(s.dollars is not None for s in sources) else " (some usage unpriced)"))
        print(f"      tokens: {json.dumps(asdict(result.spend.totals(role)))}")
    for source, path, turn in result.turns:
        rows = activity(turn)
        results = {row['payload'].get('call_id'): row for row in rows
                   if row.get('type') == 'response_item' and row['payload'].get('type') in
                   ('function_call_output', 'custom_tool_call_output')}
        print(f"    thread {source.thread}; turn {source.turn}; source {path}; "
              f"start {turn.started}; end {turn.ended}; state {turn.end_state or 'unfinished'}")
        for row in rows:
            p = row.get('payload', {})
            kind = p.get('type', '')
            if row.get('type') == 'response_item' and kind.endswith('_call'):
                ended = results.get(p.get('call_id'))
                start, end = row.get('timestamp'), ended.get('timestamp') if ended else None
                duration = (datetime.fromisoformat(end).timestamp() -
                            datetime.fromisoformat(start).timestamp()) if start and end else None
                print(f"      call {p.get('name', kind)} at {start}; "
                      f"elapsed {duration if duration is not None else 'unknown'} s")
            elif row.get('type') == 'event_msg' and kind in ('exec_command_begin', 'exec_command_end', 'item_started', 'item_completed'):
                item = p.get('item', p)
                if kind in ('item_started', 'item_completed') and item.get('type') in ('AgentMessage', 'Reasoning'):
                    continue
                print(f"      call {item.get('type', kind)} at {row.get('timestamp')}; "
                      f"recorded duration {item.get('duration_ms', 'unknown')} ms")
    for gap in result.gaps:
        print(f"    gap: {gap}")

# The number of a listed agent's last calls that `--running` prints.
RECENT_CALLS = 8


def print_span(m: Span, time_text: str) -> None:
    command = f": {one_line(m.command)}" if m.command else ""
    print(f"    {time_text:>8}  {m.label}{command}")


def active_of(listed: Listed, now: float) -> float | None:
    """The active time `--running` gives a listed agent, or None where it is
    unknown."""
    return latest_of(listed, listed.run.active_from, lambda: listed.run.active_at(now))


def self_of(listed: Listed, now: float) -> float | None:
    """The self time `--running` gives a listed agent, or None where it is
    unknown."""
    return latest_of(listed, listed.run.self_from, lambda: listed.run.self_at(now))


def latest_of(listed: Listed, over: Callable[[int], float | None],
              running: Callable[[], float | None]) -> float | None:
    """`over` of the latest message from a listed agent's parent where its
    turn has ended, and `running` otherwise."""
    r = listed.run
    return over(len(r.messages) - 1) if listed.ended and r.messages else running()


def print_running(agents: list[Listed], now: float, calls_since: float | None,
                  undecided: list[str]) -> None:
    bound = context_bound(main_tree())
    for listed in agents:
        r = listed.run
        since = minutes_or_unknown(now - r.start if r.start is not None else None)
        last = len(r.messages) - 1
        active_time = active_of(listed, now)
        period_end = r.period_end(last) if r.messages else None
        to = (" " + mctx("to {time}").format(time=clock(period_end.time))
              if period_end else "")
        active = (mctx("{active} since {time}{to}").format(
            active=minutes(active_time), time=clock(r.messages[-1].time), to=to)
            if active_time is not None else "?")
        self_time = self_of(listed, now)
        self_text = minutes_or_unknown(self_time)
        note_unknown(r, undecided)
        context = f"{r.context:,}" if r.context is not None else "?"
        past = "past " if past_bound(r.context, bound) else ""
        mark = (" " + mctx("{past}bound {bound:,}").format(
            past=past, bound=bound) if bounded(r.agent_type) else "")
        print(f"{r.label} {r.agent_type}  parent {listed.parent}  {since}  "
              f"active {active}  self {self_text}  "
              f"context {context} tokens{mark}: {r.description}")
        print(f"  cwd: {r.cwd or '?'}")
        if listed.ended:
            print_ended(r, listed.end, now, undecided)
            print_report_line(r, listed.found)
        print(f"  said: {one_line(r.said, tail=True) if r.said is not None else '-'}")
        for title, spans in (("in flight", r.in_flight), ("running", listed.running)):
            if spans:
                print(f"  {title}:")
            for m in spans:
                print_span(m, minutes(now - m.start))
        recent = r.spans[-RECENT_CALLS:]
        if calls_since is None:
            print("  recent:")
        else:
            recent = [m for m in recent if m.end is None or m.end >= calls_since]
            since_text = utc_stamp(calls_since)
            none = "" if recent else " " + mctx("none")
            print("  " + mctx("recent since {time}:{none}").format(
                time=since_text, none=none))
        for m in recent:
            print_span(m, minutes(m.end - m.start) if m.end is not None else "pending")


def print_ended(r: Run, end: float | None, now: float,
                undecided: list[str]) -> None:
    if end is None:
        undecided.append(mctx("{run}: no timestamped entry of its transcripts "
                              "ends a turn, so when its turn ended is unknown").format(
            run=r.label))
        print("  " + mctx("turn ended: ?"))
        return
    print("  " + mctx("turn ended: {time}, {ago} ago").format(
        time=clock(end), ago=minutes(now - end)))


def note_unknown(r: Run, undecided: list[str]) -> None:
    """Name in `undecided` each message to `r` whose sender is unknown."""
    for text in r.unknown:
        undecided.append(mctx("{run}: the sender of the message `{text}` is "
                              "unknown, so the run has no active time and no "
                              "self time").format(run=r.label, text=one_line(text)))


def print_messages(r: Run, undecided: list[str], budget: float | None) -> None:
    """Print each message from the parent of `r` with its active time and its
    self time, with `budget`, the run's budget in minutes, marking each self
    time past it."""
    if r.agent_type == MAIN:
        return
    note_unknown(r, undecided)
    print("  messages from the parent:")
    for i, m in enumerate(r.messages):
        active, self_time = r.active_from(i), r.self_from(i)
        past = "  past budget" if past_budget(self_time, budget) else ""
        active_text = minutes_or_unknown(active)
        self_text = minutes_or_unknown(self_time)
        print(f"    {clock(m.time)}  active {active_text}  self {self_text}"
              f"{of_budget(budget)}{past}")


def print_report_line(r: Run, found: list[Report] | None) -> None:
    if found is None:
        print("  " + mctx("received report: ?"))
    elif not found:
        print("  " + mctx("received report: none after the message at "
                          "{time}").format(time=clock(r.messages[-1].time)))
    else:
        last = found[-1]
        print("  " + mctx("received report: {time} {kind}: {text}").format(
            time=clock(last.time), kind=last.kind.value, text=one_line(last.text)))


def print_report(r: Run, undecided: list[str]) -> None:
    """Print the latest received report of the subagent of `r`, as
    `profile_runs.py --help one` gives it."""
    if r.agent_type != MAIN:
        print_report_line(r, received_reports(r, undecided))
