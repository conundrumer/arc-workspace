"""Session and checkout scoped transport for resident next, review, wait, waits and refresh reads.

The journal owns issued work. Connections own requests and responses; an
incomplete response is discarded and a retry computes from the journal.
Only the serving thread accesses held reads. Idle expiry does no state read.
The resident's first state read runs in a child that exits once the reads are
in the kept-read store (`child_read`), so that the memory its peak maps ends
with it; the resident then loads those reads from the store.
A state read belongs to the resident: a request whose bound arrives first gets
a response that says the read runs, and the run goes on; the same agent's next
call of the same kind takes over its result. Where a run ends with no client,
that agent's next call of the same kind goes first once in the queue.
A refresh request and a `wait` request give way to a client request: the queue
serves each `next`, `review` and `waits` request first, and a refresh or `wait`
read ends where one arrives (the `wait` client sends its request again). A call
that waits in the queue waits for its response or its bound. Once the
resident serves a call, the resident alone decides the output. A run that has
journaled a give answers with its own output, and no bound or message replaces it.
The request's alarm (`arm`) is a checkpoint that comes whatever the run executes,
through its flush and its response: it touches the beat, answers each queued call
at its bound, and answers the running client at its bound; only the end of the
run at `CARRY_SECONDS` ends the request, and only while its run runs.
"""

import contextlib
import ctypes
import fcntl
import gc
import hashlib
import io
import json
import os
import select
import signal
import socket
import subprocess
import sys
import time
import traceback
from collections.abc import Iterator
from contextvars import ContextVar
from dataclasses import asdict, dataclass, field
from enum import StrEnum
import math
from pathlib import Path
from typing import TYPE_CHECKING, TextIO

if TYPE_CHECKING:
    from operations.steps import Launch

import alarms
import read_interrupts
import script_calls

from engine import checkout
from operations.constants import LIMIT_SECONDS
from operations.pacing import Capped, Pace, pace_fields, pace_of

IDLE_SECONDS = 1800
START_SECONDS = 30
FINISH_SECONDS = 5
"""Time left, at a request's bound, to answer a client that still waits."""
CARRY_SECONDS = 600
"""How long a request's run may last, from its start, once it has no client."""
CODE_ENV = "ARC_OPERATE_CODE"
CODE_CHANGED = 75
"""The exit status of a resident startup that finds the code changed while it
started; `ensure` starts another one."""


# Request cancellation must escape the state cache's failed-read handlers.
class Replaced(BaseException):
    """A code change or refresh requires a retry in a replacement interpreter."""


class Detached(BaseException):
    """The request has no client waiting, so its run publishes nothing."""


class Expired(BaseException):
    """A client's call reached its foreground deadline."""


class Unavailable(BaseException):
    """A resident cannot serve this call; retrying the transport will not help."""


class Kind(StrEnum):
    NEXT = "next"
    REVIEW = "review"
    REFRESH = "refresh"
    WAIT = "wait"
    WAITS = "waits"


YIELDING = (Kind.REFRESH, Kind.WAIT)
"""The kinds whose request gives way to a client request."""


def request_message(message: object) -> tuple[Kind, str, float, float]:
    """Validate the same request form in the queue and serving path."""
    if not isinstance(message, dict) or not {"kind", "subject", "started", "deadline"} <= set(message):
        raise ValueError("invalid request")
    kind = Kind(message["kind"])
    if set(message) != {"kind", "subject", "started", "deadline", *(["pace"] if kind is Kind.WAIT else [])}:
        raise ValueError("invalid request")
    if kind is Kind.WAIT:
        known_pace(message)
    if not isinstance(message["subject"], str) or not message["subject"]:
        raise ValueError("invalid request subject")
    for name in ("started", "deadline"):
        if type(message[name]) not in (int, float) or not math.isfinite(message[name]):
            raise ValueError("invalid request time")
    return kind, message["subject"], float(message["started"]), float(message["deadline"])


def known_pace(message: dict) -> tuple[Pace | Capped | None] | None:
    """The pace that a `wait` request gives, as a one-tuple, or None where the
    request gives none (the client's first request)."""
    given = message["pace"]
    if not isinstance(given, list) or len(given) > 1:
        raise ValueError("invalid request pace")
    return (pace_of(given[0]),) if given else None


@dataclass(frozen=True)
class WaitReply:
    """The resident's answer to a `wait` request: `read` whether a state read
    gave it, `ended` whether that read gives a ready step or a pace other than
    the one the request gave, and the `pace` of a step that is a poll."""
    read: bool
    ended: bool
    pace: Pace | Capped | None
    cpu: float = 0.0
    """The CPU seconds of the read."""


@dataclass(frozen=True)
class ReviewPlan:
    launch: "Launch"
    scratch: Path
    code: str


def review_plan(payload: object) -> ReviewPlan:
    """Refuse malformed launch fields before any foreground preparation."""
    from dataclasses import fields
    from operations.roles import Role, Model
    from operations.steps import Launch
    if not isinstance(payload, dict) or set(payload) != {"tag", "launch", "scratch", "code"}:
        raise ValueError("invalid review plan")
    if payload["tag"] != "review-plan" or not isinstance(payload["scratch"], str) or not isinstance(payload["code"], str):
        raise ValueError("invalid review plan")
    values = payload["launch"]
    if not isinstance(values, dict) or set(values) != {f.name for f in fields(Launch)}:
        raise ValueError("invalid review launch")
    values = values.copy()
    for name in ("subject", "brief", "origin", "occasion"):
        if not isinstance(values[name], str):
            raise ValueError("invalid review text")
    for name in ("again", "reread"):
        if type(values[name]) is not bool:
            raise ValueError("invalid review flag")
    if values["change"] is not None and not isinstance(values["change"], str):
        raise ValueError("invalid review change")
    if values["items"] is not None and type(values["items"]) is not int:
        raise ValueError("invalid review items")
    if values["version"] is not None and (type(values["version"]) not in (int, float) or not math.isfinite(values["version"])):
        raise ValueError("invalid review version")
    values["role"] = Role(values["role"])
    values["model"] = None if values["model"] is None else Model(values["model"])
    return ReviewPlan(Launch(**values), Path(payload["scratch"]), payload["code"])


@dataclass
class Request:
    operator: str
    started: float
    deadline: float
    connection: socket.socket
    listener: socket.socket
    code: str
    stdout: TextIO
    stderr: TextIO
    kind: "Kind" = field(default_factory=lambda: Kind.NEXT)
    phase: str = "state"
    pending: "Pending | None" = None
    begun: float = field(default_factory=time.monotonic)
    waiting: bool = True
    """Whether the client still waits for a response."""
    committed: bool = False
    """Whether the run journaled a give, after which its output is the response."""
    first: bool = False
    """Whether the queue served this request ahead of the others for a run that ended with no client."""
    run_ended: bool = False
    """Whether the run has ended, however it ended: from then on `end_at_carry` ends nothing."""
    alarm: alarms.Alarm = field(init=False, repr=False, compare=False)
    """The request's alarm, which runs `arm`."""

    def __post_init__(self) -> None:
        self.alarm = alarms.Alarm(lambda: arm(self))

    def detach(self, stdout: str = "") -> None:
        """Answer the waiting client with a successful `stdout`; the run goes on without it."""
        if not self.waiting:
            return
        self.waiting = False
        try:
            self.connection.sendall(success(stdout))
        except OSError:
            pass

    def answer_at_bound(self, now: float) -> None:
        """Answer the client with what a read that runs prints where the run runs, the client
        still waits, no give is journaled, and `now` has reached its bound less
        `FINISH_SECONDS`. Once the run has ended, its response goes to the client."""
        if (not self.run_ended and self.waiting and not self.committed
                and now >= self.deadline - FINISH_SECONDS):
            self.detach(read_running(self))

    def check(self, code: bool = False) -> None:
        beat(self.listener)
        end_at_carry(self, time.monotonic())
        self.answer_at_bound(time.monotonic())
        from refresh_locks import try_shared
        from relay_reads import session_id
        lock = try_shared(session_id())
        if lock is None:
            raise Replaced
        lock.close()
        if self.pending is not None:
            self.pending.poll()
            if self.kind in YIELDING and not self.run_ended and self.pending.client_queued():
                raise Detached
        if self.waiting:
            readable, _, _ = select.select([self.connection], [], [], 0)
            if self.connection in readable:
                self.waiting = False
        if code:
            import kept_reads
            if kept_reads.fresh_code("operate") != self.code:
                raise Replaced


BEAT_EVERY = 5.0
BEAT_FRESH = 60.0
_beaten = 0.0


def beat_path(endpoint_path: Path) -> Path:
    """The file whose mtime is the time of the resident's last checkpoint: a
    checkpoint a read reaches, or the alarm of the request that runs."""
    return endpoint_path.with_suffix(".beat")


def beat(listener: socket.socket) -> None:
    """Touch the beat file of the resident that owns `listener`, at most once per `BEAT_EVERY` seconds."""
    global _beaten
    now = time.monotonic()
    if now - _beaten < BEAT_EVERY:
        return
    _beaten = now
    try:
        beat_path(Path(listener.getsockname())).touch()
    except Exception:
        pass


def beat_fresh(operator_endpoint: Path) -> bool:
    """Whether the resident at `operator_endpoint` passed a checkpoint less than `BEAT_FRESH` seconds ago."""
    try:
        return time.time() - beat_path(operator_endpoint).stat().st_mtime < BEAT_FRESH
    except OSError:
        return False


def success(stdout: str) -> bytes:
    """The response line of a call that succeeded with the output `stdout`."""
    return (json.dumps({"status": 0, "stdout": stdout, "stderr": "", "retry": False}) + "\n").encode()


TAKEN = b'{"taken": true}\n'
"""The line the resident sends a `next` or `review` client once it serves the request.
From then on, only the resident's block ends the call on a message
(`operate_loop.waited`, which checks the inbox through `read_interrupts.scope`)."""


def running_text(phase: str, seconds: float) -> str:
    """What a call prints where a state read in `phase`, `seconds` old, outlasts the call."""
    from operations.printed_forms import POLL_AGAIN, READ_RUNNING
    return READ_RUNNING.format(phase=phase, seconds=round(seconds)) + "\n" + POLL_AGAIN + "\n"


def read_running(request: Request) -> str:
    """What a call prints where the state read of `request` outlasts the call."""
    return running_text(request.phase, time.monotonic() - request.begun)


@dataclass
class Pending:
    """Accept queued requests during cooperative reads, without executing them,
    and answer each at its bound while the run of `running` goes on. A poll by
    the alarm of `running` (`arm`) adopts none; adoption stays at a checkpoint.
    While a method of this class runs, `inside` holds and `arm` runs no poll."""
    listener: socket.socket
    connections: dict[socket.socket, tuple[float, dict | None]] = field(default_factory=dict)
    running: Request | None = None
    inside: bool = False
    queued: float = 0.0
    """The seconds the request that `take` gave last waited in the queue."""
    first: bool = False
    """Whether `take` gave its last request ahead of the others."""
    left: dict[tuple[str, str], float] = field(default_factory=dict)
    """The end time of each client run that ended with no client, by subject and kind;
    the next request of that subject and kind goes first, once."""

    @contextlib.contextmanager
    def exclusive(self) -> Iterator[None]:
        """Hold `inside` for the block."""
        before, self.inside = self.inside, True
        try:
            yield
        finally:
            self.inside = before

    def poll(self, adopt: bool = True) -> None:
        """Accept the queued requests, adopt those of the running request's subject and
        kind where `adopt` holds, and answer those whose bound has come."""
        with self.exclusive():
            while select.select([self.listener], [], [], 0)[0]:
                connection, _ = self.listener.accept()
                connection.setblocking(False)
                self.connections[connection] = time.monotonic(), None
            for connection, (arrived, message) in list(self.connections.items()):
                try:
                    if message is None:
                        if not select.select([connection], [], [], 0)[0]:
                            if time.monotonic() - arrived < START_SECONDS:
                                continue
                            raise ValueError("incomplete queued request")
                        line = connection.recv(65537, socket.MSG_PEEK)
                        if not line:
                            raise ValueError("disconnected queued request")
                        if b"\n" not in line:
                            if len(line) <= 65536 and time.monotonic() - arrived < START_SECONDS:
                                continue
                            raise ValueError("incomplete queued request")
                        message = json.loads(line.split(b"\n", 1)[0])
                        request_message(message)
                        self.connections[connection] = arrived, message
                    if adopt and self.adopt(connection, message):
                        continue
                    if (self.running is not None
                            and float(message["deadline"]) - time.monotonic() <= FINISH_SECONDS):
                        connection.sendall(success(read_running(self.running)))
                        raise ValueError("queued request answered at its bound")
                except (OSError, ValueError, KeyError, TypeError):
                    connection.close()
                    self.connections.pop(connection, None)

    def answer_due(self) -> float:
        """The time at which the first complete queued request reaches the bound at which
        `poll` answers it, or infinity where none is queued."""
        return min((float(message["deadline"]) - FINISH_SECONDS
                    for _, message in self.connections.values() if message is not None),
                   default=math.inf)

    def adopt(self, connection: socket.socket, message: dict) -> bool:
        """Give the connection of a complete request to the run of `running` where that run
        has no client and the request has its subject and kind; true where it did."""
        running = self.running
        if (running is None or running.waiting or running.kind in YIELDING
                or message["kind"] != running.kind or message["subject"] != running.operator):
            return False
        peeked = connection.recv(65537, socket.MSG_PEEK)
        connection.recv(len(peeked.split(b"\n", 1)[0]) + 1)
        connection.settimeout(START_SECONDS)
        connection.sendall(TAKEN)
        self.connections.pop(connection, None)
        with contextlib.suppress(OSError):
            running.connection.close()
        running.connection = connection
        running.deadline = float(message["deadline"])
        running.waiting = True
        arm(running)
        return True

    def client_queued(self) -> bool:
        """Whether a complete request of a kind that is no yielding kind waits in the queue."""
        with self.exclusive():
            return any(message is not None and Kind(message["kind"]) not in YIELDING
                       for _, message in self.connections.values())

    def take(self) -> socket.socket | None:
        """The first complete request of a subject and kind whose run ended with no client,
        within `START_SECONDS` + `LIMIT_SECONDS` of that end; else the first complete request
        of a kind that is no yielding kind, else the first of the others."""
        with self.exclusive():
            self.poll()
            now = time.monotonic()
            self.left = {key: end for key, end in self.left.items()
                         if now - end <= START_SECONDS + LIMIT_SECONDS}

            def rank(entry: tuple[socket.socket, float, dict]) -> int:
                message = entry[2]
                if (message["subject"], message["kind"]) in self.left:
                    return 0
                return 2 if Kind(message["kind"]) in YIELDING else 1

            complete = [(connection, arrived, message) for connection, (arrived, message)
                        in self.connections.items() if message is not None]
            for connection, arrived, message in sorted(complete, key=rank):
                self.connections.pop(connection)
                self.queued = now - arrived
                self.first = self.left.pop((message["subject"], message["kind"]), None) is not None
                return connection
            return None

    def close(self) -> None:
        for connection in self.connections:
            connection.close()
        self.connections.clear()


CURRENT: ContextVar[Request | None] = ContextVar("operate_request", default=None)


client_began = 0.0
"""The time at which this resident last began to serve a `next` or `review` request."""


standalone_phase = "state"
"""The phase of the read of a call that runs with no resident request."""


def read_phase(phase: str) -> None:
    """Name the current read in a failure diagnostic."""
    global standalone_phase
    if (request := CURRENT.get()) is not None:
        request.phase = phase
    else:
        standalone_phase = phase


def check() -> None:
    """Validate the active request before a side effect or published result."""
    if (request := CURRENT.get()) is not None:
        request.check()


def commit() -> None:
    """Record that the active request journaled a give; its output is now the response."""
    if (request := CURRENT.get()) is not None:
        request.committed = True


@contextlib.contextmanager
def side_effect() -> Iterator[None]:
    """Exclude a merge while validated request code issues work or publishes a step.

    The bound's signal is deferred until a started Bash run is journaled.
    A request with no client waiting issues and publishes nothing: it raises
    `Detached` before the block runs. Standalone commands keep their existing
    exclusion and watchdog.
    """
    current = CURRENT.get()
    if current is None:
        yield
        return
    from refresh_locks import try_shared
    from relay_reads import session_id
    lock = try_shared(session_id())
    if lock is None:
        raise Replaced
    with lock:
        current.check()
        if not current.waiting:
            raise Detached
        with alarms.blocked():
            yield


@contextlib.contextmanager
def executor() -> Iterator[None]:
    """Serialize journal executors across checkouts of the same session.

    A superseded foreground client can exit before its resident finishes
    recording a run. Its replacement waits for that recording to finish.
    """
    from relay_reads import session_id
    identity = hashlib.sha256(session_id().encode()).hexdigest()[:32]
    path = endpoint(checkout.ROOT, session_id()).parent / f"execute-{identity}.lock"
    with path.open("a") as lock:
        while True:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                pause(0.05)
        yield


def pause(seconds: float) -> None:
    """Wait with cancellation checks when a resident request owns the wait."""
    request = CURRENT.get()
    if request is None:
        time.sleep(seconds)
        return
    end = time.monotonic() + max(seconds, 0)
    while time.monotonic() < end:
        request.check(code=False)
        select.select([request.connection], [], [], max(min(end - time.monotonic(), 0.2), 0))
    request.check(code=False)


def endpoint(main: Path, session: str) -> Path:
    """The private endpoint of this checkout and session; its path fits AF_UNIX."""
    root = Path("/tmp") / f"arc-operate-{os.getuid()}"
    root.mkdir(mode=0o700, exist_ok=True)
    identity = hashlib.sha256(f"{main.resolve()}\0{session}".encode()).hexdigest()[:32]
    return root / f"{identity}.sock"


def connect(path: Path, seconds: float) -> socket.socket:
    connection = socket.socket(socket.AF_UNIX)
    connection.settimeout(max(seconds, 0.001))
    try:
        connection.connect(str(path))
        return connection
    except OSError:
        connection.close()
        raise


def startup_permitted() -> bool:
    """Whether this process can start a resident outside a sandbox.

    The Codex sandbox marker denies startup. On macOS, a failed or unavailable
    libSystem sandbox check also denies startup."""
    if "CODEX_SANDBOX" in os.environ:
        return False
    if sys.platform != "darwin":
        return True
    try:
        check = ctypes.CDLL("/usr/lib/libSystem.B.dylib").sandbox_check
        check.restype = ctypes.c_int
        check.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int]
        return check(os.getpid(), None, 0) == 0
    except (OSError, AttributeError):
        return False


def ensure(main: Path, session: str, deadline: float) -> socket.socket:
    """A resident connection within the deadline. Where startup is permitted,
    at most one interpreter starts under the startup and owner locks; otherwise
    the caller waits for a connection without taking either lock."""
    path = endpoint(main, session)
    if not startup_permitted():
        global REQUEST_SENT
        REQUEST_SENT = False
        while time.monotonic() < deadline:
            try:
                return connect(path, deadline - time.monotonic())
            except OSError:
                time.sleep(0.05)
        raise Expired
    with path.with_suffix(".start").open("a") as lock:
        while True:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise Expired
                time.sleep(0.05)
        try:
            return connect(path, deadline - time.monotonic())
        except OSError:
            pass
        process: subprocess.Popen[bytes] | None = None
        while time.monotonic() < deadline:
            if process is None:
                process = spawn(main, session)
            elif process.poll() is not None:
                if process.returncode != CODE_CHANGED:
                    detail = path.with_suffix(".log").read_text()[-4096:].strip()
                    raise Unavailable(f"resident startup exited ({process.returncode}): "
                                      f"{detail or 'no diagnostic from the resident'}")
                process = None
                continue
            try:
                return connect(path, deadline - time.monotonic())
            except OSError:
                time.sleep(0.05)
        raise Expired


def spawn(main: Path, session: str) -> subprocess.Popen[bytes] | None:
    """Start a resident under the owner lock, or None where another process holds it."""
    path = endpoint(main, session)
    with path.with_suffix(".owner").open("a") as owner:
        try:
            fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return None
        path.unlink(missing_ok=True)
        import kept_reads
        expected = kept_reads.fresh_code("operate")
        with path.with_suffix(".log").open("w") as errors:
            return subprocess.Popen(
                [sys.executable, "-B", "-X", f"pycache_prefix={path.with_suffix('.pyc')}",
                 str(main / "scripts/operate_service.py"), "startup"], cwd=main,
                env={**os.environ, **script_calls.ALLOCATOR_ENV, script_calls.SESSION_ENV: session,
                     CODE_ENV: expected},
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                stderr=errors, start_new_session=True)


def prepare(main: Path, session: str, deadline: float) -> None:
    """Start the relay's service without sending a request to a live owner."""
    path = endpoint(main, session)
    with path.with_suffix(".owner").open("a") as owner:
        try:
            fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
    ensure(main, session, deadline).close()


def exchange(connection: socket.socket, operator: str, started: float, deadline: float, kind: Kind,
             known: tuple[Pace | Capped | None] | None = None
             ) -> tuple[int, str, str] | ReviewPlan | WaitReply | None:
    """A complete response, or None when transport or request validation needs a retry.
    The call waits for the response or its bound. The resident sends `TAKEN` once it
    serves the request, or takes over the run of an earlier request."""
    with connection:
        connection.settimeout(max(deadline - time.monotonic(), 0.001))
        message = {"subject": operator, "started": started, "deadline": deadline, "kind": kind}
        if kind is Kind.WAIT:
            message["pace"] = [] if known is None else [pace_fields(known[0])]
        connection.sendall((json.dumps(message) + "\n").encode())
        global REQUEST_SENT
        REQUEST_SENT = True
        while not select.select([connection], [], [], 1.0)[0]:
            if time.monotonic() >= deadline:
                break
        with connection.makefile("rb") as stream:
            line = stream.readline()
            if line == TAKEN:
                line = stream.readline()
        if not line.endswith(b"\n"):
            return None
        response = json.loads(line)
        if response["retry"]:
            return None
        if "plan" in response:
            if kind != Kind.REVIEW or response["status"] != 0:
                raise ValueError("unexpected review plan")
            return review_plan(response["plan"])
        if kind is Kind.WAIT and response["status"] == 0:
            if "ended" not in response:
                return WaitReply(False, False, None)
            return WaitReply(True, response["ended"], pace_of(response["pace"]), float(response["cpu"]))
        if type(response["status"]) is not int or not all(isinstance(response[k], str) for k in ("stdout", "stderr")):
            raise ValueError("invalid response")
        return response["status"], response["stdout"], response["stderr"]


REQUEST_SENT = False
"""Whether this client has sent its request line to a resident. A connection-only
startup attempt resets it, including after an earlier transport attempt sent."""


def timeout_output(operator: str) -> None:
    from operate_loop import timeout_output as output
    output(operator)


def silent_before(operator: str, kind: Kind) -> bool:
    """Whether the operator's last call of the same action printed `RESIDENT_SILENT`."""
    try:
        from entry_reads import entries_back
        from operations.command_words import Action
        from operations.printed_forms import RESIDENT_SILENT
        from printed_launch_hook import last_next_call
        from transcripts import find
        action = Action.REVIEW if kind == Kind.REVIEW else Action.NEXT
        previous = last_next_call(entries_back(find(operator)), operator, action)
        return previous is not None and RESIDENT_SILENT.format(seconds=LIMIT_SECONDS) in previous.text
    except Exception:
        return False


def resident_beats() -> bool:
    """Whether this session's resident has passed a checkpoint within `BEAT_FRESH` seconds."""
    try:
        from relay_reads import session_id
        return beat_fresh(endpoint(checkout.ROOT, session_id()))
    except Exception:
        return False


def expired_output(operator: str, repeated: bool = False) -> int:
    """Print the output of an expired call and return its exit status: where the
    request reached a resident and either the last call did not end the same way or
    the resident's beat is less than `BEAT_FRESH` seconds old, the line that has the
    operator run the command again; else the failure report. A caller denied
    startup whose connection attempt has sent no request also gets that retry,
    including on repeated calls."""
    if ((not REQUEST_SENT and not startup_permitted())
            or (REQUEST_SENT and (not repeated or resident_beats()))):
        from operations.printed_forms import RESIDENT_SILENT
        print(RESIDENT_SILENT.format(seconds=LIMIT_SECONDS), flush=True)
        return 0
    timeout_output(operator)
    return 1


def client(operator: str, kind: Kind = Kind.NEXT) -> int:
    """Return resident output and publish review plans within the foreground bound;
    `kind` is `NEXT`, `REVIEW` or `WAITS`, and `operator` the request's subject: for
    `WAITS`, the ticket number."""
    from operate_loop import arm_watchdog, single_instance
    from relay_reads import session_id
    from transcript_snapshots import Refused
    global REQUEST_SENT
    repeated = False
    watchdog = None
    try:
        if kind == Kind.REVIEW:
            from operate_review import qualification
            if qualification(operator) is None:
                return 0
        import kept_reads
        loaded_code = kept_reads.fresh_code("operate")
        if kind in (Kind.NEXT, Kind.REVIEW):
            single_instance(operator)
        REQUEST_SENT = False
        repeated = kind in (Kind.NEXT, Kind.REVIEW) and silent_before(operator, kind)
        watchdog = arm_watchdog(operator, lambda me: expired_output(me, repeated))
        started, deadline = time.time(), time.monotonic() + LIMIT_SECONDS
        result = request(checkout.ROOT, session_id(), operator, started, deadline, kind)
        if isinstance(result, ReviewPlan):
            from refresh_locks import try_shared
            from operate_review import publish
            from operations.printed_forms import POLL_AGAIN
            lock = try_shared(session_id())
            if lock is None:
                print(POLL_AGAIN)
                return 0
            with lock:
                if time.monotonic() >= deadline:
                    raise Expired
                if loaded_code != result.code or kept_reads.fresh_code("operate") != loaded_code:
                    print(POLL_AGAIN)
                    return 0
                return publish(operator, result.launch, result.scratch)
        assert isinstance(result, tuple)
        status, stdout, stderr = result
        if status != 0 and kind == Kind.NEXT:
            return failed_next(operator, status, stdout, stderr)
        sys.stdout.write(stdout)
        sys.stderr.write(stderr)
        return status
    except Expired:
        return expired_output(operator, repeated)
    except (Unavailable, Exception) as exc:
        cause = (f"operate: {exc}\n" if isinstance(exc, (Refused, Unavailable))
                 else traceback.format_exc())
        if kind == Kind.NEXT:
            return failed_next(operator, 1, "", cause)
        print(cause, end="", file=sys.stderr)
        return 1
    finally:
        if watchdog is not None:
            watchdog.clear()


def failed_next(operator: str, status: int, stdout: str, stderr: str) -> int:
    """Print a failed call's output as it is, or, where it prints no call and the
    operator's last call of `next` did not print `NEXT_FAILED`, the step that sends
    the coordinator that output and has the operator run the command again."""
    from entry_reads import entries_back
    from operations.command_words import Action
    from operations.constants import COORDINATOR
    from operations.printing import printed
    from operations.printed_forms import AFTER_TIMEOUT, NEXT_FAILED
    from operations.steps import Send
    from printed_bash_check import prints_no_call
    from printed_launch_hook import last_next_call
    from transcripts import find

    output = stdout + stderr
    if prints_no_call(output):
        try:
            previous = last_next_call(entries_back(find(operator)), operator, Action.NEXT)
        except Exception as exc:
            sys.stdout.write(stdout)
            sys.stderr.write(stderr)
            print(f"operate: the last call of next is unreadable: {exc}", file=sys.stderr)
            return status
        report = NEXT_FAILED.format(agent=operator)
        if previous is None or report not in previous.text:
            step = Send(COORDINATOR, report + "\n" + output.strip(), "next-failed")
            print(AFTER_TIMEOUT, flush=True)
            print(printed(step, operator, Path()), flush=True)
            return 1
    sys.stdout.write(stdout)
    sys.stderr.write(stderr)
    return status


def request(main: Path, session: str, operator: str, started: float, deadline: float, kind: Kind,
            known: tuple[Pace | Capped | None] | None = None
            ) -> tuple[int, str, str] | ReviewPlan | WaitReply:
    """Retry transport failures from journal state within the original deadline."""
    from refresh_locks import wait_free
    while time.monotonic() < deadline:
        if not wait_free(session, deadline):
            raise Expired
        try:
            result = exchange(ensure(main, session, deadline), operator, started, deadline, kind, known)
            if result is not None:
                return result
        except (ConnectionError, FileNotFoundError):
            pass
        if kind != Kind.REVIEW:
            started = time.time()
        time.sleep(0.05)
    raise Expired


def poll_wait(operator: str, known: tuple[Pace | Capped | None] | None) -> WaitReply:
    """The resident's answer to a `wait` request for `operator` that gives the pace
    `known`, or none; `Unavailable` where the resident fails the read, and a reply
    of no read where the request reaches its bound."""
    from relay_reads import session_id
    try:
        result = request(checkout.ROOT, session_id(), operator, time.time(),
                         time.monotonic() + LIMIT_SECONDS, Kind.WAIT, known)
    except Expired:
        return WaitReply(False, False, None)
    if not isinstance(result, WaitReply):
        assert isinstance(result, tuple)
        raise Unavailable(result[2].strip() or result[1].strip() or "the resident failed a wait read")
    return result


def refresh_resident(main: Path, session: str, operator: str) -> None:
    """Have the resident of `session`, started where none runs, read the state
    of `operator`. The resident answers once it accepts the request, and the
    read goes on in it."""
    result = request(main, session, operator, time.time(),
                           time.monotonic() + LIMIT_SECONDS, Kind.REFRESH)
    if not isinstance(result, tuple) or result[0]:
        raise RuntimeError("resident refresh failed")


def end_at_carry(current: Request, now: float) -> float:
    """Give the time at which the run of `current` ends, `CARRY_SECONDS` from
    its start, or infinity once the run has ended; raise `Unavailable` where
    the run runs and `now` has reached it."""
    if current.run_ended:
        return math.inf
    end = current.begun + CARRY_SECONDS
    if now >= end:
        raise Unavailable(f"state read did not finish within {CARRY_SECONDS} s "
                          f"while reading {current.phase}")
    return end


def arm(current: Request) -> None:
    """The checkpoint of `current` that its alarm runs: touch the beat, answer the
    client of `current` at its bound, answer the queued requests at theirs
    (`Pending.poll`, with no adoption), end the run at `CARRY_SECONDS`, and set
    the alarm for the earliest of those that has not come, and `BEAT_EVERY` from
    now. Only the end of the run raises, and only while the run runs."""
    beat(current.listener)
    now = time.monotonic()
    due = min(end_at_carry(current, now), now + BEAT_EVERY)
    current.answer_at_bound(now)
    pending = current.pending
    if pending is not None:
        if not pending.inside:
            with contextlib.suppress(OSError):
                pending.poll(adopt=False)
        due = min(due, pending.answer_due())
    if current.waiting and not current.committed and not current.run_ended:
        due = min(due, current.deadline - FINISH_SECONDS)
    current.alarm.set(due)


read_first = True
"""Whether this resident has yet to read the state: its first read runs in a child."""

CHILD_POLL_SECONDS = 0.05
CHILD_ERROR_BYTES = 8192


def child_read(current: Request) -> None:
    """Read the state of `current.operator` in a forked child that exits once
    the reads it computed are in the kept-read store, so that the peak memory
    of this resident's first read ends with the child; the resident's own read
    then loads those records. Where the resident's first read has run, do
    nothing. Cancellation of the request, or the end of its run at
    `CARRY_SECONDS`, kills the child and propagates. A
    child that fails gives the request the outcome of any failed read."""
    global read_first
    if not read_first:
        return
    import kept_reads
    import state_assembly
    while not kept_reads.flush():  # A lock is transient.
        current.check()
        time.sleep(CHILD_POLL_SECONDS)
    read_first = False
    errors, written = os.pipe()
    pid = os.fork()
    if pid == 0:
        code = 1
        try:
            os.close(errors)
            CURRENT.set(None)
            with read_interrupts.request_scope(lambda: None):
                state_assembly.read_state(current.operator)
            while not kept_reads.flush():
                time.sleep(CHILD_POLL_SECONDS)
            code = 0
        except BaseException:
            with contextlib.suppress(OSError):
                os.write(written, traceback.format_exc().encode()[-CHILD_ERROR_BYTES:])
        finally:
            os._exit(code)
    os.close(written)
    status = None
    try:
        while status is None:
            done, wait_status = os.waitpid(pid, os.WNOHANG)
            if done:
                status = wait_status
            else:
                current.check()
                time.sleep(CHILD_POLL_SECONDS)
        if status:
            raise RuntimeError("first state read failed in its child:\n"
                               + os.read(errors, CHILD_ERROR_BYTES).decode(errors="replace"))
    finally:
        if status is None:
            os.kill(pid, signal.SIGKILL)
            os.waitpid(pid, 0)
        os.close(errors)


def publish_response(current: Request, response: dict[str, object]) -> None:
    """Publish a successful reply. A journaled reply remains authoritative
    while replacement holds the refresh lock."""
    data = (json.dumps(response) + "\n").encode()
    if current.committed:
        current.connection.sendall(data)
    else:
        with side_effect():
            current.connection.sendall(data)


@contextlib.contextmanager
def run_scope(current: Request) -> Iterator[None]:
    """Mark the run of `current` as ended when the block ends, however it ends."""
    try:
        yield
    finally:
        current.run_ended = True


def serve_request(connection: socket.socket, listener: socket.socket, code: str,
                  pending: Pending | None = None) -> script_calls.End | None:
    """Serve one request; gives why this interpreter must end, or `None`
    where it serves on."""
    import kept_reads
    import operate
    import state_assembly
    from operations import codex_mode, trial_mode

    connection.settimeout(START_SECONDS)
    with connection.makefile("rb") as stream:
        line = stream.readline(65537)
    if not line:
        return None
    if not line.endswith(b"\n"):
        raise ValueError("incomplete request")
    message = json.loads(line)
    kind, subject, started, deadline = request_message(message)
    global client_began
    stdout, stderr = io.StringIO(), io.StringIO()
    current = Request(subject, started, deadline,
                      connection, listener, code, stdout, stderr, kind=kind, pending=pending,
                      first=pending.first if pending is not None else False)
    if kind != Kind.REFRESH:
        connection.sendall(TAKEN)
    with read_interrupts.request_scope(check):
        token = CURRENT.set(current)
        cutoff = state_assembly.REQUEST_CUTOFF.set(
            state_assembly.Cutoff(current.operator, current.started) if kind == Kind.NEXT else None)
        codex_mode.enabled.cache_clear()
        trial_mode.enabled.cache_clear()
        script_calls.start_request(str(checkout.ROOT), "operate.py",
                                   [kind if kind in (Kind.REVIEW, Kind.WAIT, Kind.WAITS) else "next"],
                                   pending.queued if pending is not None else 0.0)
        from file_reads import stats_stand_but
        stats_stand_but(None)
        status: int | ReviewPlan = 1
        reply: dict[str, object] = {}
        retry, ended = False, None
        if pending is not None:
            pending.running = current
        try:
            with (contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr),
                  run_scope(current)):
                arm(current)
                current.check(code=True)
                if current.kind == Kind.REFRESH:
                    current.detach()
                    # A client read that began after this request began read the new code.
                    if current.started >= client_began:
                        child_read(current)
                        state_assembly.read_state(current.operator)
                    status = 0
                elif current.kind is Kind.WAIT:
                    from operate_loop import ready_read
                    reply = ready_read(current.operator, known_pace(message))
                    status = 0
                elif current.kind is Kind.WAITS:
                    status = operate.main(["waits", current.operator])
                else:
                    client_began = time.time()
                    with executor():
                        child_read(current)
                        if current.kind == Kind.REVIEW:
                            from operate_review import plan
                            outcome = plan(current.operator)
                            if isinstance(outcome, int):
                                status = outcome
                            else:
                                status = ReviewPlan(outcome[0], outcome[1], code)
                        else:
                            status = operate.main(["next", current.operator])
                current.check()
        except Replaced:
            if not current.committed:
                status, retry = 1, True
            ended = script_calls.End.REPLACED
        except Detached:
            retry = kind is Kind.WAIT
        except (Unavailable, kept_reads.Unavailable) as exc:
            status, ended = 1, script_calls.End.UNAVAILABLE
            stdout.seek(0)
            stdout.truncate(0)
            print(f"operate: {exc}", file=stderr)
        except Exception:
            stdout.seek(0)
            stdout.truncate(0)
            traceback.print_exc(file=stderr)
            status, ended = 1, script_calls.End.EXCEPTION
        finally:
            arm(current)  # The alarm covers the flush and the response.
            if not kept_reads.flush():
                store = kept_reads.store()
                if store is None or not store.locked():
                    # A lock is transient: the records stay held for the next request's flush.
                    stdout.seek(0)
                    stdout.truncate(0)
                    status, retry, ended = 1, False, script_calls.End.STORE_FAILURE
                    print(f"operate: kept-read store cannot preserve completed reads: "
                          f"{store.path if store is not None else ''}: "
                          f"{store.write_error if store is not None else ''}", file=stderr)
        response = {"status": 0 if isinstance(status, ReviewPlan) else status,
                    "stdout": "" if retry else stdout.getvalue(),
                    "stderr": "" if retry else stderr.getvalue(),
                    "retry": retry, **reply}
        if isinstance(status, ReviewPlan):
            response["plan"] = {"tag": "review-plan", "launch": asdict(status.launch),
                                "scratch": str(status.scratch), "code": status.code}
        current.connection.settimeout(1)
        try:
            if not current.waiting:
                pass
            elif not retry and response["status"] == 0:
                try:
                    publish_response(current, response)
                except Replaced:
                    ended = script_calls.End.REPLACED
                    current.connection.sendall((json.dumps({"status": 1, "stdout": "", "stderr": "",
                                                    "retry": True}) + "\n").encode())
                except Detached:
                    pass
            else:
                current.connection.sendall((json.dumps(response) + "\n").encode())
        except OSError:
            pass
        finally:
            current.alarm.clear()
            if current.connection is not connection:
                current.connection.close()
            if pending is not None:
                if kind not in YIELDING and not current.waiting and not current.first:
                    pending.left[(subject, kind)] = time.monotonic()
                pending.running = None
            script_calls.collected_footprint()
            script_calls.record()
            CURRENT.reset(token)
            state_assembly.REQUEST_CUTOFF.reset(cutoff)
        if ended is None and kept_reads.fresh_code("operate") != code:
            return script_calls.End.CODE_CHANGED
        return ended


def serve() -> script_calls.End:
    """Serves requests until this interpreter must end, and gives why."""
    script_calls.start_service(str(checkout.ROOT))
    from relay_reads import session_id
    path = endpoint(checkout.ROOT, session_id())
    with path.with_suffix(".owner").open("a") as owner:
        try:
            fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return script_calls.End.LOCK_HELD
        # The duplicate stays open until process exit, including a cleanup failure.
        os.dup(owner.fileno())
        import kept_reads
        gc.disable()
        kept_reads.open_store(required=True)
        code = kept_reads.fresh_code("operate")
        import operate  # noqa: F401
        kept_reads.pin_code("operate")
        if (kept_reads.fresh_code("operate") != code
                or os.environ.get(CODE_ENV, code) != code):
            kept_reads.flush()
            script_calls.record()
            script_calls.record_end(str(checkout.ROOT), script_calls.End.CODE_CHANGED)
            os._exit(CODE_CHANGED)
        script_calls.record()
        with socket.socket(socket.AF_UNIX) as listener:
            path.unlink(missing_ok=True)
            listener.bind(str(path))
            listener.listen()
            listener.settimeout(IDLE_SECONDS)
            pending = Pending(listener)
            idle_until = time.monotonic() + IDLE_SECONDS
            ended = script_calls.End.IDLE
            try:
                while time.monotonic() < idle_until:
                    connection = pending.take()
                    if connection is None:
                        select.select([listener], [], [], 0.05)
                        continue
                    idle_until = time.monotonic() + IDLE_SECONDS
                    with connection:
                        try:
                            reason = serve_request(connection, listener, code, pending)
                            if reason is not None:
                                ended = reason
                                break
                        except (OSError, ValueError, KeyError, TypeError):
                            continue
                    idle_until = time.monotonic() + IDLE_SECONDS
            finally:
                pending.close()
                path.unlink(missing_ok=True)
                kept_reads.flush()
    return ended


if __name__ == "__main__":
    sys.modules["operate_service"] = sys.modules[__name__]
    reason = serve()
    script_calls.record()
    script_calls.record_end(str(checkout.ROOT), reason)
    os._exit(0)
