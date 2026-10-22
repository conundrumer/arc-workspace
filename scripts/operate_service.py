"""Session and checkout scoped transport for resident next, review and refresh reads.

The journal owns issued work. Connections own requests and responses; an
incomplete response is discarded and a retry computes from the journal.
Only the serving thread accesses held reads. Idle expiry does no state read.
A state read belongs to the resident: a request whose bound arrives first gets
a response that says the read runs, and the run goes on without it.
A refresh request gives way to a client request: the queue serves each `next`
or `review` request first, and a refresh read ends where one arrives. A call
that waits in the queue ends where a message to its caller arrives. Once the
resident serves a call, the resident alone decides the output. A run that has
journaled a give answers with its own output, and no bound or message replaces it.
"""

import contextlib
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

import read_interrupts
import script_calls

from engine import checkout
from operations.constants import LIMIT_SECONDS

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


def request_message(message: object) -> tuple[Kind, str, float, float]:
    """Validate the same request form in the queue and serving path."""
    if not isinstance(message, dict) or set(message) != {"kind", "subject", "started", "deadline"}:
        raise ValueError("invalid request")
    kind = Kind(message["kind"])
    if not isinstance(message["subject"], str) or not message["subject"]:
        raise ValueError("invalid request subject")
    for name in ("started", "deadline"):
        if type(message[name]) not in (int, float) or not math.isfinite(message[name]):
            raise ValueError("invalid request time")
    return kind, message["subject"], float(message["started"]), float(message["deadline"])


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

    def detach(self, stdout: str = "") -> None:
        """Answer the waiting client with a successful `stdout`; the run goes on without it."""
        if not self.waiting:
            return
        self.waiting = False
        try:
            self.connection.sendall(success(stdout))
        except OSError:
            pass

    def check(self, code: bool = False) -> None:
        beat(self.listener)
        if self.waiting and not self.committed and time.monotonic() >= self.deadline - FINISH_SECONDS:
            self.detach(read_running(self))
        from refresh_locks import try_shared
        from relay_reads import session_id
        lock = try_shared(session_id())
        if lock is None:
            raise Replaced
        lock.close()
        if self.pending is not None:
            self.pending.poll()
            if self.kind is Kind.REFRESH and self.pending.client_queued():
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
    """The file whose mtime is the time of the resident's last checkpoint."""
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
    and answer each at its bound while the run of `running` goes on."""
    listener: socket.socket
    connections: dict[socket.socket, tuple[float, dict | None]] = field(default_factory=dict)
    running: Request | None = None
    queued: float = 0.0
    """The seconds the request that `take` gave last waited in the queue."""

    def poll(self) -> None:
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
                if (self.running is not None
                        and float(message["deadline"]) - time.monotonic() <= FINISH_SECONDS):
                    connection.sendall(success(read_running(self.running)))
                    raise ValueError("queued request answered at its bound")
            except (OSError, ValueError, KeyError, TypeError):
                connection.close()
                self.connections.pop(connection, None)

    def client_queued(self) -> bool:
        """Whether a complete `next` or `review` request waits in the queue."""
        return any(message is not None and message["kind"] != Kind.REFRESH
                   for _, message in self.connections.values())

    def take(self) -> socket.socket | None:
        """The first complete `next` or `review` request, else the first complete refresh request."""
        self.poll()
        complete = [(connection, arrived, message) for connection, (arrived, message)
                    in self.connections.items() if message is not None]
        for connection, arrived, message in sorted(complete, key=lambda c: c[2]["kind"] == Kind.REFRESH):
            self.connections.pop(connection)
            self.queued = time.monotonic() - arrived
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
        previous = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGALRM})
        try:
            yield
        finally:
            signal.pthread_sigmask(signal.SIG_SETMASK, previous)


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


def ensure(main: Path, session: str, deadline: float) -> socket.socket:
    """Connect, starting at most one interpreter under the startup and owner locks."""
    path = endpoint(main, session)
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
                env={**os.environ, script_calls.SESSION_ENV: session, CODE_ENV: expected},
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


class Queued:
    """The transcript of the caller `operator`, read from the size it has at creation:
    `arrived` is true once a `queued_command` entry is appended after that point."""

    def __init__(self, operator: str) -> None:
        from transcripts import find
        self.path = find(operator)
        self.offset = self.path.stat().st_size

    def arrived(self) -> bool:
        with self.path.open("rb") as stream:
            stream.seek(self.offset)
            data = stream.read()
        end = data.rfind(b"\n") + 1
        self.offset += end
        return any(b'"queued_command"' in line and
                   json.loads(line).get("attachment", {}).get("type") == "queued_command"
                   for line in data[:end].splitlines() if line.strip())


def queued_of(operator: str) -> Queued | None:
    """The reader of the caller's transcript, or None where it cannot be read."""
    try:
        return Queued(operator)
    except Exception:
        return None


def message_output(operator: str, kind: Kind) -> str:
    """What the resident prints where a message to `operator` is accepted during a call of `kind`."""
    from operations.steps import Poll
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        if kind == Kind.REVIEW:
            from operations.printing import printed
            print(printed(Poll(), operator, Path()))
        else:
            from operate_loop import print_step
            print_step(Poll(), Path(), operator)
    return output.getvalue()


def exchange(connection: socket.socket, operator: str, started: float,
             deadline: float, kind: Kind) -> tuple[int, str, str] | ReviewPlan | None:
    """A complete response, or None when transport or request validation needs a retry.
    Where a message to `operator` is accepted while the request waits in the queue,
    the call ends with what the resident prints for that message, and the request is
    left. The resident sends `TAKEN` once it serves the request; after that, the call
    waits for the response."""
    with connection:
        connection.settimeout(max(deadline - time.monotonic(), 0.001))
        connection.sendall((json.dumps({"subject": operator, "started": started,
                                       "deadline": deadline, "kind": kind}) + "\n").encode())
        global REQUEST_SENT
        REQUEST_SENT = True
        inbox = queued_of(operator) if kind != Kind.REFRESH else None
        while not select.select([connection], [], [], 1.0)[0]:
            if time.monotonic() >= deadline:
                break
            if inbox is not None:
                try:
                    if inbox.arrived():
                        return 0, message_output(operator, kind), ""
                except Exception:
                    inbox = None
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
        if type(response["status"]) is not int or not all(isinstance(response[k], str) for k in ("stdout", "stderr")):
            raise ValueError("invalid response")
        return response["status"], response["stdout"], response["stderr"]


REQUEST_SENT = False
"""Whether this client has sent its request line to a resident."""


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
    operator run the command again; else the failure report."""
    if REQUEST_SENT and (not repeated or resident_beats()):
        from operations.printed_forms import RESIDENT_SILENT
        print(RESIDENT_SILENT.format(seconds=LIMIT_SECONDS), flush=True)
        return 0
    timeout_output(operator)
    return 1


def client(operator: str, kind: Kind = Kind.NEXT) -> int:
    """Return resident output and publish review plans within the foreground bound."""
    from operate_loop import arm_watchdog, single_instance
    from relay_reads import session_id
    from transcript_snapshots import Refused
    global REQUEST_SENT
    repeated = False
    try:
        if kind == Kind.REVIEW:
            from operate_review import qualification
            if qualification(operator) is None:
                return 0
        import kept_reads
        loaded_code = kept_reads.fresh_code("operate")
        single_instance(operator)
        REQUEST_SENT = False
        repeated = silent_before(operator, kind)
        arm_watchdog(operator, lambda me: expired_output(me, repeated))
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
        signal.alarm(0)


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


def request(main: Path, session: str, operator: str, started: float,
            deadline: float, kind: Kind) -> tuple[int, str, str] | ReviewPlan:
    """Retry transport failures from journal state within the original deadline."""
    from refresh_locks import wait_free
    while time.monotonic() < deadline:
        if not wait_free(session, deadline):
            raise Expired
        try:
            result = exchange(ensure(main, session, deadline), operator, started, deadline, kind)
            if result is not None:
                return result
        except (ConnectionError, FileNotFoundError):
            pass
        if kind != Kind.REVIEW:
            started = time.time()
        time.sleep(0.05)
    raise Expired


def refresh_resident(main: Path, session: str, operator: str) -> None:
    """Have the resident of `session`, started where none runs, read the state
    of `operator`. The resident answers once it accepts the request, and the
    read goes on in it."""
    result = request(main, session, operator, time.time(),
                           time.monotonic() + LIMIT_SECONDS, Kind.REFRESH)
    if isinstance(result, ReviewPlan) or result[0]:
        raise RuntimeError("resident refresh failed")


def arm(current: Request) -> None:
    """Answer the client of `current` at its bound, end its run at `CARRY_SECONDS`,
    and set the alarm for the earlier of those that has not come."""
    now = time.monotonic()
    end = current.begun + CARRY_SECONDS
    if now >= end:
        raise Unavailable(f"state read did not finish within {CARRY_SECONDS} s "
                          f"while reading {current.phase}")
    due = end
    if current.waiting and not current.committed:
        if now >= current.deadline - FINISH_SECONDS:
            current.detach(read_running(current))
        else:
            due = min(due, current.deadline - FINISH_SECONDS)
    signal.setitimer(signal.ITIMER_REAL, max(due - now, 0.001))


def serve_request(connection: socket.socket, listener: socket.socket, code: str,
                  pending: Pending | None = None) -> bool:
    """Serve one request; false retires this interpreter for a code change or refresh."""
    import kept_reads
    import operate
    import state_assembly
    from operations import codex_mode, trial_mode

    connection.settimeout(START_SECONDS)
    with connection.makefile("rb") as stream:
        line = stream.readline(65537)
    if not line:
        return True
    if not line.endswith(b"\n"):
        raise ValueError("incomplete request")
    message = json.loads(line)
    kind, subject, started, deadline = request_message(message)
    global client_began
    stdout, stderr = io.StringIO(), io.StringIO()
    current = Request(subject, started, deadline,
                      connection, listener, code, stdout, stderr, kind=kind, pending=pending)
    if kind != Kind.REFRESH:
        connection.sendall(TAKEN)
    with read_interrupts.request_scope(check):
        token = CURRENT.set(current)
        cutoff = state_assembly.REQUEST_STARTED.set(current.started)
        codex_mode.enabled.cache_clear()
        trial_mode.enabled.cache_clear()
        script_calls.start_request(str(checkout.ROOT), "operate.py", ["review" if kind == Kind.REVIEW else "next"],
                                   pending.queued if pending is not None else 0.0)
        from file_reads import stats_stand_but
        stats_stand_but(None)
        status: int | ReviewPlan = 1
        retry, keep = False, True
        if pending is not None:
            pending.running = current
        try:
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                signal.signal(signal.SIGALRM, lambda *_: arm(current))
                arm(current)
                current.check(code=True)
                if current.kind == Kind.REFRESH:
                    current.detach()
                    # A client read that began after this request began read the new code.
                    if current.started >= client_began:
                        state_assembly.read_state(current.operator)
                    status = 0
                else:
                    client_began = time.time()
                    with executor():
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
            status, retry, keep = 1, True, False
        except Detached:
            pass
        except (Unavailable, kept_reads.Unavailable) as exc:
            status, keep = 1, False
            stdout.seek(0)
            stdout.truncate(0)
            print(f"operate: {exc}", file=stderr)
        except Exception:
            stdout.seek(0)
            stdout.truncate(0)
            traceback.print_exc(file=stderr)
            status, keep = 1, False
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            if not kept_reads.flush():
                store = kept_reads.store()
                if store is None or not store.locked():
                    # A lock is transient: the records stay held for the next request's flush.
                    stdout.seek(0)
                    stdout.truncate(0)
                    status, retry, keep = 1, False, False
                    print(f"operate: kept-read store cannot preserve completed reads: "
                          f"{store.path if store is not None else ''}: "
                          f"{store.write_error if store is not None else ''}", file=stderr)
        response = {"status": 0 if isinstance(status, ReviewPlan) else status,
                    "stdout": "" if retry else stdout.getvalue(),
                    "stderr": "" if retry else stderr.getvalue(),
                    "retry": retry}
        if isinstance(status, ReviewPlan):
            response["plan"] = {"tag": "review-plan", "launch": asdict(status.launch),
                                "scratch": str(status.scratch), "code": status.code}
        connection.settimeout(1)
        try:
            if not current.waiting:
                pass
            elif not retry and response["status"] == 0:
                try:
                    with side_effect():
                        connection.sendall((json.dumps(response) + "\n").encode())
                except Replaced:
                    keep = False
                    connection.sendall((json.dumps({"status": 1, "stdout": "", "stderr": "",
                                                    "retry": True}) + "\n").encode())
                except Detached:
                    pass
            else:
                connection.sendall((json.dumps(response) + "\n").encode())
        except OSError:
            pass
        finally:
            if pending is not None:
                pending.running = None
            script_calls.record()
            CURRENT.reset(token)
            state_assembly.REQUEST_STARTED.reset(cutoff)
        return keep and kept_reads.fresh_code("operate") == code


def serve() -> None:
    script_calls.start_service(str(checkout.ROOT))
    from relay_reads import session_id
    path = endpoint(checkout.ROOT, session_id())
    with path.with_suffix(".owner").open("a") as owner:
        try:
            fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        import kept_reads
        from handbook.paths import console_importable
        # Match operate's import resolution before taking the initial stamp.
        # Otherwise importing operate adds console dependencies to the closure
        # and every cold interpreter retires as though its code had changed.
        console_importable()
        gc.disable()
        kept_reads.open_store(required=True)
        code = kept_reads.fresh_code("operate")
        import operate  # noqa: F401
        kept_reads.pin_code("operate")
        if (kept_reads.fresh_code("operate") != code
                or os.environ.get(CODE_ENV, code) != code):
            kept_reads.flush()
            script_calls.record()
            os._exit(CODE_CHANGED)
        script_calls.record()
        with socket.socket(socket.AF_UNIX) as listener:
            path.unlink(missing_ok=True)
            listener.bind(str(path))
            listener.listen()
            listener.settimeout(IDLE_SECONDS)
            pending = Pending(listener)
            idle_until = time.monotonic() + IDLE_SECONDS
            try:
                while time.monotonic() < idle_until:
                    connection = pending.take()
                    if connection is None:
                        select.select([listener], [], [], 0.05)
                        continue
                    idle_until = time.monotonic() + IDLE_SECONDS
                    with connection:
                        try:
                            if not serve_request(connection, listener, code, pending):
                                break
                        except (OSError, ValueError, KeyError, TypeError):
                            continue
                    idle_until = time.monotonic() + IDLE_SECONDS
            finally:
                pending.close()
                path.unlink(missing_ok=True)
                kept_reads.flush()


if __name__ == "__main__":
    sys.modules["operate_service"] = sys.modules[__name__]
    serve()
    script_calls.record()
    os._exit(0)
