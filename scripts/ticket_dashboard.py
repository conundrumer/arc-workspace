"""The ticket dashboard: an HTTP server whose page gives an overseer of the
operations, on a phone, from the main tree's tracker, the usage cache and
the states the last reads of each session's operators recorded and the
live agents from their transcripts, what is
moving, what is next and the week's pace, and updates itself in the
browser as the tracker, usage observations or operator record sources change.

    uv run python scripts/ticket_dashboard.py <address> <port>

serves GET at four routes, and POST at `CLEAR_ROUTE`. `/` gives the latest published page,
with its search entries available through `SEARCH_ROUTE` and `TICKET_ROUTE`.
Before the first render, those routes give status 503; `/` gives a page
that shows when the first read began. The server gzips HTML where accepted.
One daemon thread renders first from operator records, then with live agents,
and polls `fingerprint` every `POLL` seconds. While a page watches, changes
cause a render at least `MIN_EVENT` seconds after the last began. Failed
renders leave the published page in place. `EVENTS` sends each published
version to connected clients, which fetch `/` and replace their content.
A hidden page closes its stream. The server serves no ticket file.

The server runs under `script_calls.ALLOCATOR_ENV`, which it adds to its
environment by running itself again at its start where it is missing.

Where a file of a module the server loaded from the repo's `scripts/` or
`src/` changes (`code_files`), or the render thread finds, after a live
render, that the server holds more than the larger of
`script_calls.FOOTPRINT_BOUND` and `GROWTH` over what it held after its
first live render (`Footprint`), the server stops taking requests, waits
for those it serves other than streams, and runs itself again in its own
process with the same arguments; the open page's `EventSource` connects
again by its own retry.

This module holds the server; `dashboard_reads` the reads the page is
rendered from, `dashboard_html` the HTML of its sections, `dashboard_search`
the search, and `dashboard_template` the page around its sections."""

import argparse
import gzip
import math
import os
import sys
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import traceback
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import kept_reads
import script_calls
from dashboard_html import Rendered, filled, page
from dashboard_reads import CodexLimits, CodexWindow, clear, cleared, operator_records
from dashboard_search import results, sheet, words
from dashboard_template import CLEAR_ROUTE, EVENTS, FOLD, SEARCH_ROUTE, TEMPLATE, TICKET_ROUTE
from dashboard_words import clock
from engine import checkout
from file_ticket import main_tickets
from idle_sessions import MAIN, named_main
from shown_state import SHOWN
from ticket_numbers import SESSIONS, indexes
from tree_reads import scratch
from state_reads import new_state
from usage_limit import read, usage_file

from ticketing.vocabulary import Status

POLL = 3.0
"""The seconds between polls by the renderer and waits by a stream."""

MIN_EVENT = 15.0
"""The fewest seconds between the starts of refresh renders."""

REST = 4.0
"""How many times the length of the last render the render thread rests
before the next refresh render starts, so that it uses at most 1 / (1 +
`REST`) of a core while it refreshes."""


WATCH = 1.0
"""The seconds between two reads of the stamps of `code_files`."""

ROOT = Path(__file__).resolve().parents[1]
"""The root of the tree the server runs from."""


GROWTH = 128 * 2**20
"""The bytes the server may hold after a render over what it held after its
first live render, before it restarts for size."""

CODEX = CodexLimits(Path.home())


type Stamp = tuple[Path, tuple[int, int, int, int] | None]


def stamp(path: Path) -> Stamp:
    """The path with its device, inode, modification time and size, or
    with None where its metadata is unavailable."""
    try:
        st = path.stat()
    except OSError:
        return (path, None)
    return (path, (st.st_dev, st.st_ino, st.st_mtime_ns, st.st_size))


def fingerprint(tickets: Path) -> tuple[Stamp | CodexWindow | int | None, ...]:
    """The stamps of each status directory of `tickets`, of each ticket file
    outside `tickets/closed/` (a log line appended to a file changes its
    time and not its directory's), of session selection files and candidate
    operator records before freshness or parse filters, of the usage cache,
    and of the current Codex weekly observation. Missing record paths are
    included. A time bucket also refreshes live agent activity every
    `MIN_EVENT` seconds."""
    out: list[Stamp] = []
    for s in Status:
        d = tickets / s.value
        out.append(stamp(d))
        if s is not Status.CLOSED and d.is_dir():
            out.extend(stamp(p) for p in sorted(d.iterdir()))
    ids = indexes(tickets)
    sessions = {session for names in ids.values() for session in names}
    main = named_main(tickets)
    if main is not None:
        sessions.add(main)
    sources = {tickets / MAIN, tickets / SESSIONS,
               *(tickets / SESSIONS / str(i) for i in ids),
               *(scratch(session) / SHOWN for session in sessions)}
    out.extend(stamp(p) for p in sorted(sources))
    return (*out, stamp(usage_file()), CODEX.read(time.time()), int(time.time() // MIN_EVENT))


def code_files() -> list[Path]:
    """The files of the modules loaded from `scripts/` and `src/` under
    `ROOT`."""
    dirs = (ROOT / "scripts", ROOT / "src")
    found = {Path(f).resolve() for m in list(sys.modules.values())
             if isinstance(f := getattr(m, "__file__", None), str)}
    return sorted(p for p in found if any(p.is_relative_to(d) for d in dirs))


def code_stamps(files: list[Path]) -> tuple[Stamp, ...]:
    return tuple(stamp(p) for p in files)


def render(tickets: Path, live_agents: bool = True) -> Rendered:
    """The page of `tickets` as it stands at the call: a new state of the
    held reads (`state_reads.new_state`), so that no read gives a file as
    an earlier render read it."""
    now = new_state()
    if kept_reads.store() is None:
        kept_reads.open_store()
    undecided: list[str] = []
    return page(tickets, now, read(now, undecided), operator_records(tickets, now, undecided, live_agents), CODEX.read(now), cleared())


def accepts_gzip(header: str | None) -> bool:
    """Whether the `Accept-Encoding` value `header` gives `gzip` with a
    weight above 0."""
    for part in (header or "").split(","):
        coding, *weights = (w.strip() for w in part.split(";"))
        if coding.lower() != "gzip":
            continue
        q = [w[2:] for w in weights if w.lower().startswith("q=")]
        try:
            return not q or float(q[-1]) > 0
        except ValueError:
            return False
    return False


CLEAR_LOG = "dashboard-clear.log"
"""The file, under `.cache/` of the main tree, that holds one line for each
POST to the clear route."""


@dataclass
class Latest:
    """The published render, its version, and the streams that watch it."""
    rendered: Rendered | None = None
    version: int = 0
    condition: threading.Condition = field(default_factory=threading.Condition)
    streams: int = 0
    began: float = field(default_factory=time.time)
    poke: threading.Event = field(default_factory=threading.Event)
    """Set to make the render thread publish at once."""
    published: float = 0.0
    """The `time.monotonic()` of the last publish."""
    took: float = 0.0
    """The seconds the last render took."""

    def gap(self) -> float:
        """The fewest seconds between the starts of two refresh renders:
        `MIN_EVENT`, or `REST` times the last render if that is longer."""
        return max(MIN_EVENT, REST * self.took)


class Reason(StrEnum):
    """Why the server stopped, as `main` prints it before it restarts."""
    CODE = "code changed"
    MEMORY = "memory over bound"


class Stopping:
    """The reason the server stopped, set by the first thread to stop it."""

    def __init__(self) -> None:
        self.reason: Reason | None = None

    def stop(self, server: ThreadingHTTPServer, reason: Reason) -> None:
        """Stops `server`, and keeps `reason` unless one is already kept."""
        if self.reason is None:
            self.reason = reason
        server.shutdown()


class Footprint:
    """The bytes a server may hold after a render: the larger of
    `script_calls.FOOTPRINT_BOUND` and `GROWTH` over what it held after its
    first live render. Before that render there is no bound."""

    def __init__(self) -> None:
        self.first: int | None = None

    def over(self, held: int) -> bool:
        """Whether `held` bytes, held after a live render, pass the bound."""
        if self.first is None:
            self.first = held
        return held > max(script_calls.FOOTPRINT_BOUND, self.first + GROWTH)


def render_loop(tickets: Path, latest: Latest, stop: Callable[[Reason], None]) -> None:
    """Publish startup renders, then changed state while a stream watches.
    After each live render it calls `stop` with `Reason.MEMORY` and returns
    where the server holds more than the `Footprint` bound.
    All cached state reads of the server run on this thread."""
    def publish(live_agents: bool) -> tuple[Stamp | CodexWindow | int | None, ...]:
        state = fingerprint(tickets)
        start = time.monotonic()
        rendered = render(tickets, live_agents)
        with latest.condition:
            latest.took = time.monotonic() - start
            latest.rendered = rendered
            latest.version += 1
            latest.published = time.monotonic()
            latest.condition.notify_all()
        return state

    footprint = Footprint()
    previous = None
    began = time.monotonic()
    for live_agents in (False, True):
        try:
            began = time.monotonic()
            previous = publish(live_agents)
            if live_agents and footprint.over(script_calls.collected_footprint()):
                return stop(Reason.MEMORY)
        except Exception:
            traceback.print_exc()
    while True:
        poked = latest.poke.wait(POLL)
        latest.poke.clear()
        try:
            with latest.condition:
                watched = latest.streams > 0
            if poked or (watched and time.monotonic() - began >= latest.gap()
                         and fingerprint(tickets) != previous):
                began = time.monotonic()
                previous = publish(True)
                if footprint.over(script_calls.collected_footprint()):
                    return stop(Reason.MEMORY)
        except Exception:
            traceback.print_exc()


class Serving:
    """The count of the requests a server serves other than streams, and
    the wait for none."""

    def __init__(self) -> None:
        self.count = 0
        self.idle = threading.Condition()

    def __enter__(self) -> None:
        with self.idle:
            self.count += 1

    def __exit__(self, *_: object) -> None:
        with self.idle:
            self.count -= 1
            self.idle.notify_all()

    def wait_idle(self) -> None:
        with self.idle:
            self.idle.wait_for(lambda: self.count == 0)


class Handler(BaseHTTPRequestHandler):
    """Serves `/`, `SEARCH_ROUTE`, `TICKET_ROUTE` and `EVENTS` of the tracker `tickets`,
    and `CLEAR_ROUTE` by POST, and nothing else. Each render runs on the daemon render thread: the
    reads it makes keep a SQLite store (`kept_reads`) that only the thread
    that opened it may use."""
    tickets: Path
    latest: Latest
    serving: Serving

    def do_GET(self) -> None:
        url = urlsplit(self.path)
        if url.path == EVENTS:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.stream()
            return
        with self.serving:
            self.serve_page(url.path, url.query)

    def do_POST(self) -> None:
        """Move the mark of Updates to the time in the body, and publish a
        new render. Each POST adds a line to `CLEAR_LOG`."""
        body = ""
        before = cleared()
        status = 200
        try:
            if urlsplit(self.path).path != CLEAR_ROUTE:
                status = 404
                self.send_error(404)
                return
            try:
                body = self.rfile.read(int(self.headers.get("Content-Length", "0"))).decode("utf-8", "replace")
                at = float(body)
                if not math.isfinite(at):
                    raise ValueError
            except ValueError:
                status = 400
                self.send_error(400, "the body is not a time")
                return
            clear(at)
            self.latest.poke.set()
            status = 204
            self.send_response(204)
            self.send_header("Content-Length", "0")
            self.end_headers()
        except BaseException as error:
            status = f"{type(error).__name__}"
            raise
        finally:
            self.log_clear(body, before, status)

    def log_clear(self, body: str, before: float, status: int | str) -> None:
        """Add one line for a POST to `CLEAR_LOG`: time, path, body, the mark
        before and after, and the status."""
        try:
            path = checkout.caches() / CLEAR_LOG
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a") as log:
                log.write(f"{time.time():.3f} {self.path} body={body!r} before={before!r} after={cleared()!r} status={status}\n")
        except OSError:
            pass

    def serve_page(self, path: str, query: str) -> None:
        began = time.monotonic()
        latest = self.latest
        with latest.condition:
            stale = latest.rendered is not None and time.monotonic() - latest.published >= latest.gap()
        if stale:
            # The render thread publishes unasked only while a stream watches.
            # This request serves the older render, and the next one is fresh.
            latest.poke.set()
        with latest.condition:
            rendered = latest.rendered
        if path not in ("/", SEARCH_ROUTE, TICKET_ROUTE):
            self.send_error(404)
            return
        if rendered is None:
            line = f"First read of the state in progress · began {clock(self.latest.began, time.time())}"
            text = filled(TEMPLATE, {"BODY": f'<main><div class="meta">{line}</div></main>',
                                    "EVENTS": EVENTS, "SEARCH": SEARCH_ROUTE, "TICKET": TICKET_ROUTE,
                                    "CLEAR": CLEAR_ROUTE, "FOLD": FOLD}) if path == "/" else line
            self.send_html(text, began, 503)
            return
        match path:
            case "/":
                self.send_html(rendered.text, began)
            case p if p == SEARCH_ROUTE:
                self.send_html(results(rendered.entries, words(parse_qs(query))), began)
            case p if p == TICKET_ROUTE:
                given = parse_qs(query).get("n")
                if given is None:
                    self.send_error(400, "no ticket number is given (`n`)")
                    return
                n = given[-1]
                e = rendered.entries.get(n)
                if e is None:
                    self.send_error(404, f"no ticket {n}")
                    return
                self.send_html(sheet(e, time.time()), began)
            case _:
                self.send_error(404)

    def send_html(self, text: str, began: float, status: int = 200) -> None:
        """Sends `text` as the HTML of the response, gzipped where the
        request accepts it, and logs its size and the time since
        `began`."""
        body = text.encode()
        size = len(body)
        zipped = accepts_gzip(self.headers.get("Accept-Encoding"))
        if zipped:
            body = gzip.compress(body)
        self.log_message("%s: %d bytes, %d sent, in %.2f s", self.path, size, len(body),
                         time.monotonic() - began)
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        if zipped:
            self.send_header("Content-Encoding", "gzip")
        self.send_header("Vary", "Accept-Encoding")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def stream(self) -> None:
        """Send published versions and comments until the client closes."""
        latest = self.latest
        with latest.condition:
            latest.streams += 1
        sent = 0
        try:
            while True:
                with latest.condition:
                    latest.condition.wait_for(lambda: latest.version > sent, timeout=POLL)
                    version = latest.version
                self.wfile.write(b"data: changed\n\n" if version > sent else b": same\n\n")
                self.wfile.flush()
                sent = version
        except (BrokenPipeError, ConnectionResetError):
            return
        finally:
            with latest.condition:
                latest.streams -= 1


def serve(address: str, port: int, tickets: Path, serving: Serving,
          stopping: Stopping) -> ThreadingHTTPServer:
    """A server of `tickets` bound to `address` and `port`, not yet
    serving, that counts its requests in `serving` and stops by `stopping`
    when it holds too much."""
    latest = Latest()
    handler = type("Bound", (Handler,), {"tickets": tickets, "latest": latest, "serving": serving})
    server = ThreadingHTTPServer((address, port), handler)
    server.daemon_threads = True
    threading.Thread(target=render_loop, daemon=True,
                     args=(tickets, latest, lambda reason: stopping.stop(server, reason))).start()
    return server


def watch(server: ThreadingHTTPServer, files: list[Path], stopping: Stopping) -> None:
    """Stops `server` for `Reason.CODE` by `stopping` at the first read,
    every `WATCH` seconds, of the stamps of `files` that differs from the
    first."""
    first = code_stamps(files)
    while code_stamps(files) == first:
        time.sleep(WATCH)
    stopping.stop(server, Reason.CODE)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("address")
    parser.add_argument("port", type=int)
    parser.add_argument("--tickets", type=Path, default=None,
                        help="the tracker to serve; the main tree's `tickets/` where not given")
    args = parser.parse_args(argv)
    if any(os.environ.get(name) != value for name, value in script_calls.ALLOCATOR_ENV.items()):
        os.execve(sys.executable, [sys.executable, *sys.orig_argv[1:]],
                  {**os.environ, **script_calls.ALLOCATOR_ENV})
    serving = Serving()
    stopping = Stopping()
    server = serve(args.address, args.port, args.tickets or main_tickets(), serving, stopping)
    files = code_files()
    threading.Thread(target=watch, args=(server, files, stopping), daemon=True).start()
    print(f"serving http://{args.address}:{args.port}/", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    if stopping.reason is None:
        return 0
    serving.wait_idle()
    server.server_close()
    print(f"{stopping.reason}: restarting", flush=True)
    os.execv(sys.executable, [sys.executable, *sys.orig_argv[1:]])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
