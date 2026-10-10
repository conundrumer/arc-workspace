"""Turn spans of a session's transcript into a `request`, a brief and a
follow-up's span line. `HELP`, which `--help` prints, says how the
coordinator and a ticket analyst call it."""

import re
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from controlled_markdown import mctx
from engine import checkout
from handbook.paths import importable

importable(checkout.scripts())

from file_ticket import file_ticket, main_tickets, run  # noqa: E402
from run_reads import blocks, message_text  # noqa: E402
from senders import Origin, origin  # noqa: E402
from ticket_files import ticket_name, ticket_path, ticket_status  # noqa: E402
from ticket_form import bounds, section  # noqa: E402
from ticket_log import log_moves  # noqa: E402
from ticket_numbers import TicketNumber, session_id, ticket_number  # noqa: E402
from ticketing.text import SECTIONS, heading, ticket_text  # noqa: E402
from ticketing.times import TIME_FORM, stamp_time, utc_stamp  # noqa: E402
from ticketing.vocabulary import COORDINATOR, Domain, Kind, Status  # noqa: E402
from ticket_vocabulary import ticked  # noqa: E402
from transcripts import Entry, Refused, epoch, find, read_entries  # noqa: E402

INVOCATION = "uv run python scripts/spans.py"

TRANSCRIPT, GROUNDS = SECTIONS[Kind.REQUEST]


class Route(Enum):
    """The routes of work that write a request, a brief or a span."""
    DIRECT = "direct"
    SEND = "send"
    HOTFIX = "hotfix"
    FILE = "file"
    DRAFT = "draft"


ROUTES = ticked(r.value for r in Route)

HELD = (Route.DIRECT, Route.HOTFIX)
"""The routes whose request the coordinator holds while it carries the
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
    - `{invocation} file <route> [{inferred}] <subject> <title> <start words> <end words>` files a `request` whose span runs from the message `<start words>` gives to the one `<end words>` gives, with the Grounds lines on its stdin, and prints its path.
    - `{invocation} brief [--route <route>] <number>` prints the brief of the request `<number>`.
    - `{invocation} brief --route <route> <start words> <end words>` prints the brief of that span, with the Grounds lines on its stdin.
    - `{invocation} append [{inferred}] <number> <start words> <end words>` appends that span to the request `<number>`, with a log line, and prints its path. Its route is `{follow_up}`, for a follow-up on that request and for a ruling the user gives on it.
    - Usage:
        ```
        {invocation} file send <namespace>-<short-title> '<target>: <what the user asks for>' '<start words>' '<end words>' <<'EOF'
        - <one addition to what the span gives, with its source>
        EOF
        ```
    - `<route>` is one of {routes}. `{inferred}` marks a route the coordinator inferred, which waits on the user's reply.
    - `<subject>` and `<title>` are a `request`'s, as `uv run python scripts/file_ticket.py --help` gives them.
    - A message is a message of the user, or the text of one of the coordinator's replies, in the session whose id the shell holds in `CLAUDE_CODE_SESSION_ID`.
    - A words argument matches a message whose words hold its words in a row, where a word is a run of letters and digits, compared in lower case, and each other character only separates words.
    - A words argument that is a time in the form `{time_form}` names the one message of the session at that time, in place of a match of words.
    - The command refuses, and prints each match, where a words argument matches no message or more than one, and ends the refusal on a words argument that matches more than one message with a line that says the argument may give one of the printed times in its place, and refuses where the end comes before the start.
    - A span is the line `<session id> <start> <end>` under the request's `{transcript}`, with each time in UTC to the second, and holds each message from its start to its end, inclusive.
    - `file` writes the request with `{transcript}` and `{grounds}`, and files it as `uv run python scripts/file_ticket.py` files. On `draft`, and on a route given with `{inferred}`, it then moves the request to `tickets/draft/`. On each of {held} with no `{inferred}`, it then moves the request to `tickets/assigned/`, with an `assigned` line whose holder is the session id the shell holds in `CLAUDE_CODE_SESSION_ID`.
    - A brief gives each message of each span of the request, in full and in time order, each with its time and its sender, and then its Grounds.
    - `append` adds the span line under the request's `{transcript}`, and writes a log line in the status the request stands in.
    - `file`, `append`, and `brief` with `--route` end with a readback prompt, which gives the route and the first and the last message of the span. `brief` prints that prompt on stderr, so that its stdout is the brief alone.
    """)

READBACK = mctx("""
    - Read the route back to the user now: `{route}`{inferred}, your restatement of the work in your own words, and the span's first and last message.
    - First: {first}
    - Last: {last}
    """)

INFERRED_NOTE = mctx(", inferred, so wait for the user's reply before you act")

DRAFT_NOTE = mctx("route `{route}`")

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


def readback_prompt(route: Route | FollowUp, first: Message, last: Message, inferred: bool) -> str:
    return READBACK.format(route=route_label(route), inferred=INFERRED_NOTE if inferred else "",
                           first=first.render(), last=last.render())


def span_readback(route: Route | FollowUp, spans: list[Span], inferred: bool) -> str:
    return readback_prompt(route, span_messages(spans[0])[0], span_messages(spans[-1])[-1], inferred)


def route_of(word: str) -> Route:
    try:
        return Route(word)
    except ValueError:
        raise Refused(mctx("`{word}` is no route: the routes are {routes}").format(
            word=word, routes=ROUTES))


def grounds_lines() -> str:
    return sys.stdin.read().strip("\n")


def file_request(route: Route, inferred: bool, subject: str, title: str, start_words: str,
                 end_words: str) -> str:
    span = resolve_span(start_words, end_words)
    text = ticket_text(Kind.REQUEST, title, {TRANSCRIPT: span.line(), GROUNDS: grounds_lines()})
    tickets = main_tickets()
    path = file_ticket(tickets, Domain.CHANGE.value, subject, COORDINATOR, text)
    number = ticket_name(path).number
    if route is Route.DRAFT or inferred:
        path = log_moves(tickets, number, Status.DRAFT, COORDINATOR, Status.OPEN,
                         None, DRAFT_NOTE.format(route=route.value)).moved[0]
    elif route in HELD:
        path = log_moves(tickets, number, Status.ASSIGNED, COORDINATOR, Status.OPEN,
                         session_id(), None).moved[0]
    return f"{path}\n\n{span_readback(route, [span], inferred)}"


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


def render_brief(spans: list[Span], grounds: str) -> str:
    held = [m for s in spans for m in span_messages(s)]
    return "\n\n".join([*(m.render() for m in held), heading(GROUNDS), grounds]).rstrip("\n")


def brief(*args: str) -> str:
    route = None
    rest = list(args)
    if rest[:1] == ["--route"] and len(rest) >= 2:
        route = route_of(rest[1])
        rest = rest[2:]
    if len(rest) == 1:
        text = ticket_path(main_tickets(), ticket_number(rest[0])).read_text()
        spans, grounds = spans_of(text), section(text, GROUNDS)
    elif len(rest) == 2 and route is not None:
        spans, grounds = [resolve_span(*rest)], grounds_lines()
    else:
        raise no_form()
    if route is not None:
        print(span_readback(route, spans, False), file=sys.stderr)
    return render_brief(spans, grounds)


def append(inferred: bool, number: str, start_words: str, end_words: str) -> str:
    span = resolve_span(start_words, end_words)
    tickets = main_tickets()
    ref = ticket_number(number)
    path = ticket_path(tickets, ref)
    text = path.read_text()
    _, cut = bounds(text, TRANSCRIPT)
    rest = text[cut:]
    path.write_text(f"{text[:cut].rstrip(chr(10))}\n{span.line()}\n" + (f"\n{rest}" if rest else ""))
    status = ticket_status(path)
    moved = log_moves(tickets, ref, status, COORDINATOR, status, None,
                      SPAN_NOTE.format(span=span.line())).moved[0]
    return f"{moved}\n\n{span_readback(FollowUp(ref), [span], inferred)}"


def marked(args: tuple[str, ...], count: int) -> tuple[bool, list[str]]:
    inferred = args[:1] == (INFERRED,)
    rest = list(args[1 if inferred else 0:])
    if len(rest) != count:
        raise no_form()
    return inferred, rest


def file_command(*args: str) -> str:
    if not args:
        raise no_form()
    inferred, rest = marked(args[1:], 4)
    return file_request(route_of(args[0]), inferred, *rest)


def append_command(*args: str) -> str:
    inferred, rest = marked(args, 3)
    return append(inferred, *rest)


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
                       transcript=heading(TRANSCRIPT), follow_up=FOLLOW_UP.format(number="<number>"), grounds=heading(GROUNDS))
    act = SUBCOMMANDS.get(args[0]) if args else None
    if act is None:
        return run(args, text, 1, unknown, False, args)
    return run(args[1:], text, None, act, False, args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
