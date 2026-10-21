"""The ticket dashboard: an HTTP server whose page gives an overseer of the
operations, on a phone, from the main tree's tracker, the usage cache and
the states the last reads of each session's operators recorded and the
live agents from their transcripts, what is
moving, what is next and the week's pace, and updates itself in the
browser as the tracker, usage observations or operator record sources change.

    uv run python scripts/ticket_dashboard.py <address> <port>

serves GET alone, at four routes. `/` renders the page on each request, as
one HTML document with its CSS and JavaScript inline: a strip at its top,
and the sections Health, Active, Queued, Since you looked, Pace, Queue,
Find and Blocked, the last three of them folded. It keeps
the search's entries of that render. `SEARCH_ROUTE` gives the HTML of the
search's hits of the `q` parameter among the entries of the latest render,
and `TICKET_ROUTE` the sheet of the ticket its `n` parameter gives; each
renders the page first where none has run. The server gzips the body of
each where the request accepts it. `EVENTS` is a Server-Sent Events stream that sends an
event when the stream opens, then at the first read of `fingerprint`, every
`POLL` seconds while the client is connected, that differs from the one of
the last event and comes `MIN_EVENT` seconds or more after it; on that event the page fetches `/`
and replaces its content in place, and the page holds no stream while it
is hidden. The server serves no ticket file, and writes no file.

Where a file of a module the server loaded from the repo's `scripts/` or
`src/` changes (`code_files`), the server stops taking requests, waits
for those it serves other than streams, and runs itself again in its own
process with the same arguments; the open page's `EventSource` connects
again by its own retry.

This module holds the server; `dashboard_reads` the reads the page is
rendered from, `dashboard_html` the HTML of its sections, `dashboard_search`
the search, and `dashboard_template` the page around its sections."""

import argparse
import gzip
import os
import sys
import threading
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import kept_reads
from dashboard_html import Rendered, page
from dashboard_reads import CodexLimits, CodexWindow, operator_records
from dashboard_search import results, sheet, words
from dashboard_template import EVENTS, SEARCH_ROUTE, TICKET_ROUTE
from file_ticket import main_tickets
from idle_sessions import MAIN, named_main
from shown_state import SHOWN
from ticket_numbers import SESSIONS, indexes
from tree_reads import scratch
from state_reads import new_state
from usage_limit import read, usage_file

from ticketing.vocabulary import Status

POLL = 3.0
"""The seconds between two reads of `fingerprint` for a connected client."""

MIN_EVENT = 15.0
"""The fewest seconds between two events of the stream to one client, so
that renders do not run back to back while the tracker changes every few
seconds."""


WATCH = 1.0
"""The seconds between two reads of the stamps of `code_files`."""

ROOT = Path(__file__).resolve().parents[1]
"""The root of the tree the server runs from."""


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


def render(tickets: Path) -> Rendered:
    """The page of `tickets` as it stands at the call: a new state of the
    held reads (`state_reads.new_state`), so that no read gives a file as
    an earlier render read it."""
    now = new_state()
    if kept_reads.store() is None:
        kept_reads.open_store()
    undecided: list[str] = []
    return page(tickets, now, read(now, undecided), operator_records(tickets, now, undecided), undecided, CODEX.read(now))


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


@dataclass
class Latest:
    """The latest render of a server, None before its first."""
    rendered: Rendered | None = None


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
    """Serves `/`, `SEARCH_ROUTE`, `TICKET_ROUTE` and `EVENTS` of the tracker `tickets`, and
    nothing else. Each render runs on the one thread of `renderer`: the
    reads it makes keep a SQLite store (`kept_reads`) that only the thread
    that opened it may use."""
    tickets: Path
    renderer: ThreadPoolExecutor
    latest: Latest
    serving: Serving

    def rendered_now(self) -> Rendered:
        """A render on `renderer`, kept as the latest."""
        r = self.renderer.submit(render, self.tickets).result()
        self.latest.rendered = r
        return r

    def rendered_last(self) -> Rendered:
        """The latest render, or a render now where none has run."""
        r = self.latest.rendered
        return self.rendered_now() if r is None else r

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

    def serve_page(self, path: str, query: str) -> None:
        match path:
            case "/":
                began = time.monotonic()
                self.send_html(self.rendered_now().text, began)
            case p if p == SEARCH_ROUTE:
                began = time.monotonic()
                self.send_html(results(self.rendered_last().entries, words(parse_qs(query))), began)
            case p if p == TICKET_ROUTE:
                began = time.monotonic()
                given = parse_qs(query).get("n")
                if given is None:
                    self.send_error(400, "no ticket number is given (`n`)")
                    return
                n = given[-1]
                e = self.rendered_last().entries.get(n)
                if e is None:
                    self.send_error(404, f"no ticket {n}")
                    return
                self.send_html(sheet(e, time.time()), began)
            case _:
                self.send_error(404)

    def send_html(self, text: str, began: float) -> None:
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
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        if zipped:
            self.send_header("Content-Encoding", "gzip")
        self.send_header("Vary", "Accept-Encoding")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def stream(self) -> None:
        """Sends an event on opening, then at the first read of `fingerprint`
        that differs from the one at the last event and comes `MIN_EVENT`
        seconds or more after it, and a comment line at each other read,
        so that a closed client ends the loop."""
        sent, sent_at = fingerprint(self.tickets), time.monotonic()
        try:
            self.wfile.write(b"data: changed\n\n")
            self.wfile.flush()
            while True:
                time.sleep(POLL)
                now = fingerprint(self.tickets)
                due = now != sent and time.monotonic() - sent_at >= MIN_EVENT
                self.wfile.write(b"data: changed\n\n" if due else b": same\n\n")
                self.wfile.flush()
                if due:
                    sent, sent_at = now, time.monotonic()
        except (BrokenPipeError, ConnectionResetError):
            return


def serve(address: str, port: int, tickets: Path, serving: Serving) -> ThreadingHTTPServer:
    """A server of `tickets` bound to `address` and `port`, not yet
    serving, that counts its requests in `serving`."""
    handler = type("Bound", (Handler,), {"tickets": tickets, "latest": Latest(),
                                         "renderer": ThreadPoolExecutor(max_workers=1), "serving": serving})
    server = ThreadingHTTPServer((address, port), handler)
    server.daemon_threads = True
    return server


def watch(server: ThreadingHTTPServer, files: list[Path], changed: threading.Event) -> None:
    """Sets `changed` and stops `server` at the first read, every `WATCH`
    seconds, of the stamps of `files` that differs from the first."""
    first = code_stamps(files)
    while code_stamps(files) == first:
        time.sleep(WATCH)
    changed.set()
    server.shutdown()


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("address")
    parser.add_argument("port", type=int)
    parser.add_argument("--tickets", type=Path, default=None,
                        help="the tracker to serve; the main tree's `tickets/` where not given")
    args = parser.parse_args(argv)
    serving = Serving()
    server = serve(args.address, args.port, args.tickets or main_tickets(), serving)
    files = code_files()
    changed = threading.Event()
    threading.Thread(target=watch, args=(server, files, changed), daemon=True).start()
    print(f"serving http://{args.address}:{args.port}/", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    if not changed.is_set():
        return 0
    serving.wait_idle()
    server.server_close()
    print("code changed: restarting", flush=True)
    os.execv(sys.executable, [sys.executable, *sys.orig_argv[1:]])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
