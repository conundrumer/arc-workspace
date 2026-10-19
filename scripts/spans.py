"""Turn spans of a session's transcript into a `request`, a brief and a
follow-up's span line. `HELP`, which `--help` prints, says how the
coordinator and a ticket analyst call it."""

import re
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from controlled_markdown import mctx
from handbook.paths import scripts_importable

scripts_importable()

from file_ticket import Call, file_ticket, main_tickets, run  # noqa: E402
from run_reads import blocks, message_text  # noqa: E402
from senders import Origin, origin  # noqa: E402
from ticket_files import ticket_name, ticket_path, ticket_status  # noqa: E402
from ticket_form import bounds, section, section_head  # noqa: E402
from ticket_log import log_moves  # noqa: E402
from ticket_numbers import TicketNumber, session_id, ticket_number  # noqa: E402
from ticketing.text import SECTIONS, heading, ticket_text  # noqa: E402
from ticketing.times import TIME_FORM, stamp_time, utc_stamp  # noqa: E402
from ticketing.vocabulary import COORDINATOR, ROUTE_NOTE, Domain, Kind, Note, Route, Status, queued  # noqa: E402
from ticket_vocabulary import ticked  # noqa: E402
from transcripts import find  # noqa: E402
from entry_reads import read_entries  # noqa: E402
from transcript_entries import epoch  # noqa: E402
from transcript_snapshots import Entry, Refused  # noqa: E402

INVOCATION = "uv run python scripts/spans.py"

GOAL, TRANSCRIPT, GROUNDS = SECTIONS[Kind.REQUEST]


ROUTES = ticked(r.value for r in Route)

HELD = (Route.DIRECT, Route.HOTFIX)
"""The routes whose request the coordinator holds while it makes the
change itself."""


INFERRED = "--inferred"

FOLLOW_UP = "re {number}"
"""The route of a follow-up on the request `number`, and of a ruling the
user gives on it."""


@dataclass(frozen=True)
class FollowUp:
    """The route `FOLLOW_UP` of the request `number`."""
    number: TicketNumber


def route_label(route: Route | FollowUp) -> str:
    return route.value if isinstance(route, Route) else FOLLOW_UP.format(number=route.number)


HELP = mctx("""
    - `{invocation} file <route> [{inferred}] <subject> <title> <goal> <start words> <end words>` files a `request` whose span runs from the message `<start words>` gives to the one `<end words>` gives, with the Grounds lines on its stdin, and prints its path.
        - Each Grounds line is `- <one addition to what the span gives, with its source>`.
        - On `op draft`, and on a route given with `{inferred}`, it moves the request to `tickets/draft/`, and on each of {held} with no `{inferred}`, to `tickets/assigned/`, with an `assigned` line whose holder is the session id the shell holds in `CLAUDE_CODE_SESSION_ID`.
    - `{invocation} brief [--route <route>] <number>` prints the brief of the request `<number>`.
    - `{invocation} brief --route <route> <start words> <end words> <goal>` prints the brief of that span and `<goal>`, with the Grounds lines on its stdin.
    - `{invocation} append [{inferred}] [--route <route>] [{goal_flag} <goal>] <number> <start words> <end words>` appends that span to the request `<number>`, with a log line, and prints its path.
        - With `--route` and a route other than `op draft`, it moves a request under `tickets/draft/` to where `file` puts a request on that route with no `{inferred}`.
        - `{goal_flag}` gives `<goal>` as the request's `{goal}`, in place of the one it holds, or before its `{transcript}` where it holds none.
    - `<goal>` holds at most {goal_words} words.
    - `<route>` is one of {routes}, and `{inferred}` marks a route the coordinator inferred.
    - `<subject>` and `<title>` are a `request`'s, as `uv run python scripts/file_ticket.py --help request` gives them.
    - A message is a message of the user, or the text of one of the coordinator's replies, in the session whose id the shell holds in `CLAUDE_CODE_SESSION_ID`.
    - A words argument matches a message whose words hold its words in a row, where a word is a run of letters and digits, compared in lower case, and each other character only separates words.
    - A words argument that is a time in the form `{time_form}` names the one message of the session at that time.
    - `file`, `append`, and `brief` with `--route` end with a readback prompt, which `brief` prints on stderr, so that its stdout is the brief alone.
    """)

READBACK = mctx("""
    - Read the route back to the user now: `{route}`{inferred}, the goal word for word where the line below gives one, and your restatement of the work in your own words.
    {goal_line}
    """)

GOAL_LINE = mctx("- Goal: {goal}")

NO_GOAL_LINE = mctx("- The request holds no goal.")

INFERRED_NOTE = mctx(", inferred")


SPAN_NOTE = mctx("span added: {span}")


class Sender(Enum):
    USER = "user"
    COORDINATOR = "coordinator"


@dataclass(frozen=True)
class Message:
    time: str
    sender: Sender
    text: str

    def render(self) -> str:
        return f"{self.time} {self.sender.value}:\n{self.text}"


@dataclass(frozen=True)
class Span:
    session: str
    start: str
    end: str

    def line(self) -> str:
        return f"{self.session} {self.start} {self.end}"


def fold(text: str) -> str:
    return " ".join(re.findall(r"[^\W_]+", text.lower()))


def message(entry: Entry) -> Message | None:
    """The message `entry` gives, or None where it gives none of the user
    or the coordinator."""
    if "timestamp" not in entry:
        return None
    time = utc_stamp(epoch(entry["timestamp"]))
    if entry.get("type") == "assistant":
        text = "\n".join(b.get("text", "") for b in blocks(entry, "text")).strip()
        return Message(time, Sender.COORDINATOR, text) if text else None
    if origin(entry)[1] is Origin.HUMAN:
        return Message(time, Sender.USER, message_text(entry))
    return None


def messages(session: str) -> list[Message]:
    found = (message(e) for e in read_entries(find(session)))
    return sorted((m for m in found if m is not None), key=lambda m: m.time)


def is_time(words: str) -> bool:
    """Whether `words` is a time in `TIME_FORM`."""
    try:
        stamp_time(words)
    except ValueError:
        return False
    return True


def resolve(words: str, session: str) -> Message:
    """The one message of `session` that `words` matches, or that stands at
    `words` where it is a time, as `--help` gives them."""
    stamp = words.strip()
    if is_time(stamp):
        matches = [m for m in messages(session) if m.time == stamp]
        subject = mctx("the time `{words}`").format(words=stamp)
    else:
        folded = fold(words)
        if not folded:
            raise Refused(mctx("`{words}` holds no word").format(words=words))
        matches = [m for m in messages(session) if f" {folded} " in f" {fold(m.text)} "]
        subject = mctx("`{words}`").format(words=words)
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise Refused(mctx("{subject} matches no message of session `{session}`").format(
            subject=subject, session=session))
    head = mctx("{subject} matches more than one message:").format(subject=subject)
    tail = [] if is_time(stamp) else [mctx("The argument may give one of these times in its place.")]
    raise Refused("\n\n".join([head, *(m.render() for m in matches), *tail]))


def span_messages(span: Span) -> list[Message]:
    return [m for m in messages(span.session) if span.start <= m.time <= span.end]


def resolve_span(start_words: str, end_words: str) -> Span:
    session = session_id()
    start, end = resolve(start_words, session), resolve(end_words, session)
    if end.time < start.time:
        raise Refused(mctx("the end, at {end}, comes before the start, at {start}").format(
            end=end.time, start=start.time))
    return Span(session, start.time, end.time)


def readback_prompt(route: Route | FollowUp, goal: str | None, inferred: bool) -> str:
    line = NO_GOAL_LINE if goal is None else GOAL_LINE.format(goal=goal)
    return READBACK.format(route=route_label(route), inferred=INFERRED_NOTE if inferred else "",
                           goal_line=line)


def route_of(word: str) -> Route:
    try:
        return Route(word)
    except ValueError:
        raise Refused(mctx("`{word}` is no route: the routes are {routes}").format(
            word=word, routes=ROUTES))


def grounds_lines() -> str:
    return sys.stdin.read().strip("\n")


def file_request(route: Route, inferred: bool, subject: str, title: str, goal: str, start_words: str,
                 end_words: str) -> str:
    check_goal(goal)
    span = resolve_span(start_words, end_words)
    text = ticket_text(Kind.REQUEST, title, {GOAL: goal, TRANSCRIPT: span.line(), GROUNDS: grounds_lines()})
    tickets = main_tickets()
    route_note = ROUTE_NOTE.format(route=route)
    path = file_ticket(tickets, Domain.CHANGE.value, subject, COORDINATOR, text,
                       filed=f"{Note.FILED}: {route_note}")
    number = ticket_name(path).number
    path = move_routed(tickets, number, Route.DRAFT if inferred else route,
                       queued(None, Kind.REQUEST))
    return f"{path}\n\n{readback_prompt(route, goal, inferred)}"


def move_routed(tickets: Path, number: TicketNumber, route: Route, source: Status) -> Path:
    """Moves the request `number`, which stands in `source`, to where
    `route` places it, as `HELP` gives, with the note `ROUTE_NOTE`, and
    returns its path."""
    to = (Status.DRAFT if route is Route.DRAFT else Status.ASSIGNED if route in HELD
          else queued(Status.DRAFT, Kind.REQUEST))
    if to is source:
        return ticket_path(tickets, number)
    return log_moves(tickets, number, to, COORDINATOR, source,
                     session_id() if to is Status.ASSIGNED else None,
                     ROUTE_NOTE.format(route=route)).moved[0]


def no_form() -> Refused:
    return Refused(mctx("the arguments do not have a form `--help` gives"))


def spans_of(text: str) -> list[Span]:
    spans = []
    for line in section(text, TRANSCRIPT).splitlines():
        parts = line.split()
        if len(parts) != 3:
            raise Refused(mctx("`{line}` is no span line").format(line=line))
        spans.append(Span(*parts))
    return spans


def request_goal(text: str) -> str | None:
    """The goal of a request's `text`, or None where it holds no goal
    section, as a request filed before requests held one does."""
    return section(text, GOAL) if section_head(text, GOAL) is not None else None


def with_goal(text: str, goal: str) -> str:
    if section_head(text, GOAL) is not None:
        start, end = bounds(text, GOAL)
        return f"{text[:start]}\n{goal}\n\n{text[end:]}"
    start, _ = bounds(text, TRANSCRIPT)
    head = text.rfind("\n", 0, start) + 1
    return f"{text[:head]}{heading(GOAL)}\n{goal}\n\n{text[head:]}"


def render_brief(goal: str | None, spans: list[Span], grounds: str) -> str:
    held = [m for s in spans for m in span_messages(s)]
    lead = [] if goal is None else [heading(GOAL), goal]
    return "\n\n".join([*lead, *(m.render() for m in held), heading(GROUNDS), grounds]).rstrip("\n")


def brief(*args: str) -> str:
    route = None
    rest = list(args)
    if rest[:1] == ["--route"] and len(rest) >= 2:
        route = route_of(rest[1])
        rest = rest[2:]
    if len(rest) == 1:
        text = ticket_path(main_tickets(), ticket_number(rest[0])).read_text()
        goal, spans, grounds = request_goal(text), spans_of(text), section(text, GROUNDS)
    elif len(rest) == 3 and route is not None:
        goal = check_goal(rest[2])
        spans, grounds = [resolve_span(rest[0], rest[1])], grounds_lines()
    else:
        raise no_form()
    if route is not None:
        print(readback_prompt(route, goal, False), file=sys.stderr)
    return render_brief(goal, spans, grounds)


def append(inferred: bool, route: Route | None, goal: str | None, number: str, start_words: str,
           end_words: str) -> str:
    if goal is not None:
        check_goal(goal)
    span = resolve_span(start_words, end_words)
    tickets = main_tickets()
    ref = ticket_number(number)
    path = ticket_path(tickets, ref)
    if route is not None and (ticket_status(path) is not Status.DRAFT or route is Route.DRAFT):
        raise Refused(mctx("`--route` takes a route other than `{route}`, on a request under "
                           "`tickets/{draft}/`").format(route=Route.DRAFT, draft=Status.DRAFT))
    text = path.read_text()
    if goal is not None:
        text = with_goal(text, goal)
    _, cut = bounds(text, TRANSCRIPT)
    rest = text[cut:]
    path.write_text(f"{text[:cut].rstrip(chr(10))}\n{span.line()}\n" + (f"\n{rest}" if rest else ""))
    status = ticket_status(path)
    moved = log_moves(tickets, ref, status, COORDINATOR, status, None,
                      SPAN_NOTE.format(span=span.line())).moved[0]
    if route is None:
        return f"{moved}\n\n{readback_prompt(FollowUp(ref), request_goal(text), inferred)}"
    moved = move_routed(tickets, ref, route, Status.DRAFT)
    return f"{moved}\n\n{readback_prompt(route, request_goal(text), inferred)}"


def marked(args: tuple[str, ...], count: int | None) -> tuple[bool, list[str]]:
    """Whether `args` open with `INFERRED`, and the rest of them, which
    number `count` where it is given."""
    inferred = args[:1] == (INFERRED,)
    rest = list(args[1 if inferred else 0:])
    if count is not None and len(rest) != count:
        raise no_form()
    return inferred, rest


def file_command(*args: str) -> str:
    if not args:
        raise no_form()
    inferred, rest = marked(args[1:], 5)
    return file_request(route_of(args[0]), inferred, *rest)


GOAL_FLAG = "--goal"

GOAL_WORDS = 10
"""The most words a goal given on the command line may hold. It was
set above the word counts of the goals of the 40 latest requests, each
rewritten to the point of its work alone, with no elaboration: each of
them fits but one outlier. Measure it again the same way to change
it."""


def check_goal(goal: str) -> str:
    count = len(goal.split())
    if count > GOAL_WORDS:
        raise Refused(mctx("the goal holds {count} words, over the limit of {bound}: give the point of the work in place of its means").format(
            count=count, bound=GOAL_WORDS))
    return goal


def append_command(*args: str) -> str:
    inferred, rest = marked(args, None)
    route = None
    if rest[:1] == ["--route"] and len(rest) >= 2:
        route, rest = route_of(rest[1]), rest[2:]
    goal = None
    if rest[:1] == [GOAL_FLAG] and len(rest) >= 2:
        goal, rest = rest[1], rest[2:]
    if len(rest) != 3:
        raise no_form()
    return append(inferred, route, goal, *rest)


SUBCOMMANDS = {
    "file": file_command,
    "append": append_command,
    "brief": brief,
}


def unknown(word: str) -> str:
    raise Refused(mctx("`{word}` is no subcommand of `{invocation}`").format(
        word=word, invocation=INVOCATION))


def main(args: list[str]) -> int:
    text = HELP.format(invocation=INVOCATION, inferred=INFERRED, routes=ROUTES,
                       held=ticked(r.value for r in HELD), time_form=TIME_FORM,
                       goal=heading(GOAL), goal_flag=GOAL_FLAG, goal_words=GOAL_WORDS, transcript=heading(TRANSCRIPT), follow_up=FOLLOW_UP.format(number="<number>"), grounds=heading(GROUNDS))
    act = SUBCOMMANDS.get(args[0]) if args else None
    if act is None:
        return run(args, Call(INVOCATION, args, text, 1, unknown, False))
    return run(args[1:], Call(INVOCATION, args, text, None, act, False))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
