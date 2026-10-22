"""Session and checkout scoped transport for resident `operate.py next` reads.

The journal owns issued work. Connections own requests and responses; an
incomplete response is discarded and a retry computes from the journal.
Only the serving thread accesses held reads. Idle expiry does no state read.
A state read belongs to the resident: a request whose bound arrives first gets
a response that says the read runs, and the run goes on without it.
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
from dataclasses import dataclass, field
from pathlib import Path
from typing import TextIO

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
    refresh: bool = False
    phase: str = "state"
    pending: "Pending | None" = None
    begun: float = field(default_factory=time.monotonic)
    waiting: bool = True
    """Whether the client still waits for a response."""

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
        if self.waiting and time.monotonic() >= self.deadline - FINISH_SECONDS:
            self.detach(read_running(self))
        from refresh_locks import try_shared
        from relay_reads import session_id
        lock = try_shared(session_id())
        if lock is None:
            raise Replaced
        lock.close()
        if self.pending is not None:
            self.pending.poll()
        if self.waiting:
            readable, _, _ = select.select([self.connection], [], [], 0)
            if self.connection in readable:
                self.waiting = False
        if code:
            import kept_reads
            if kept_reads.fresh_code("operate") != self.code:
                raise Replaced


def success(stdout: str) -> bytes:
    """The response line of a call that succeeded with the output `stdout`."""
    return (json.dumps({"status": 0, "stdout": stdout, "stderr": "", "retry": False}) + "\n").encode()


def read_running(request: Request) -> str:
    """What a call prints where the state read of `request` outlasts the call."""
    from operations.printed_forms import POLL_AGAIN, READ_RUNNING
    return READ_RUNNING.format(phase=request.phase,
                               seconds=round(time.monotonic() - request.begun)) + "\n" + POLL_AGAIN + "\n"


@dataclass
class Pending:
    """Accept queued requests during cooperative reads, without executing them,
    and answer each at its bound while the run of `running` goes on."""
    listener: socket.socket
    connections: dict[socket.socket, tuple[float, dict | None]] = field(default_factory=dict)
    running: Request | None = None

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
                    if not isinstance(message, dict) or not isinstance(message["operator"], str):
                        raise ValueError("invalid queued request")
                    self.connections[connection] = arrived, message
                if (self.running is not None
                        and float(message["deadline"]) - time.monotonic() <= FINISH_SECONDS):
                    connection.sendall(success(read_running(self.running)))
                    raise ValueError("queued request answered at its bound")
            except (OSError, ValueError, KeyError, TypeError):
                connection.close()
                self.connections.pop(connection, None)

    def take(self) -> socket.socket | None:
        self.poll()
        for connection, (_, message) in self.connections.items():
            if message is not None:
                self.connections.pop(connection)
                return connection
        return None

    def close(self) -> None:
        for connection in self.connections:
            connection.close()
        self.connections.clear()


CURRENT: ContextVar[Request | None] = ContextVar("operate_request", default=None)


def read_phase(phase: str) -> None:
    """Name the current read in a failure diagnostic."""
    if (request := CURRENT.get()) is not None:
        request.phase = phase


def check() -> None:
    """Validate the active request before a side effect or published result."""
    if (request := CURRENT.get()) is not None:
        request.check()


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


def exchange(connection: socket.socket, operator: str, started: float,
             deadline: float, refresh: bool) -> tuple[int, str, str] | None:
    """A complete response, or None when transport or request validation needs a retry."""
    with connection:
        connection.settimeout(max(deadline - time.monotonic(), 0.001))
        connection.sendall((json.dumps({"operator": operator, "started": started,
                                       "deadline": deadline, "refresh": refresh}) + "\n").encode())
        with connection.makefile("rb") as stream:
            line = stream.readline()
        if not line.endswith(b"\n"):
            return None
        response = json.loads(line)
        if response["retry"]:
            return None
        return response["status"], response["stdout"], response["stderr"]


def timeout_output(operator: str) -> None:
    from operate_loop import timeout_output as output
    output(operator)


def client(operator: str) -> int:
    """Return resident output as the foreground next call's own result."""
    from operate_loop import arm_watchdog, single_instance
    from relay_reads import session_id
    single_instance(operator)
    arm_watchdog(operator)
    started, deadline = time.time(), time.monotonic() + LIMIT_SECONDS
    try:
        result = request(checkout.ROOT,
                         session_id(), operator, started, deadline, False)
    except (Unavailable, OSError, ValueError) as exc:
        return failed_next(operator, 1, "", f"operate: {exc}\n")
    except Expired:
        timeout_output(operator)
        return 1
    finally:
        signal.alarm(0)
    status, stdout, stderr = result
    if status != 0:
        return failed_next(operator, status, stdout, stderr)
    sys.stdout.write(stdout)
    sys.stderr.write(stderr)
    return status


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
        previous = last_next_call(entries_back(find(operator)), operator, Action.NEXT)
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
            deadline: float, refresh: bool) -> tuple[int, str, str]:
    """Retry transport failures from journal state within the original deadline."""
    from refresh_locks import wait_free
    while time.monotonic() < deadline:
        if not wait_free(session, deadline):
            raise Expired
        try:
            result = exchange(ensure(main, session, deadline), operator, started, deadline, refresh)
            if result is not None:
                return result
        except (ConnectionError, FileNotFoundError):
            pass
        started = time.time()
        time.sleep(0.05)
    raise Expired


def refresh_resident(main: Path, session: str, operator: str) -> None:
    """Have the resident of `session`, started where none runs, read the state
    of `operator`. The resident answers once it accepts the request, and the
    read goes on in it."""
    status, _, _ = request(main, session, operator, time.time(),
                           time.monotonic() + LIMIT_SECONDS, True)
    if status:
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
    if current.waiting:
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
    if not isinstance(message, dict) or not isinstance(message["operator"], str):
        raise ValueError("invalid request")
    stdout, stderr = io.StringIO(), io.StringIO()
    current = Request(message["operator"], float(message["started"]), float(message["deadline"]),
                      connection, listener, code, stdout, stderr, refresh=message["refresh"], pending=pending)
    with read_interrupts.request_scope(check):
        token = CURRENT.set(current)
        cutoff = state_assembly.REQUEST_STARTED.set(current.started)
        codex_mode.enabled.cache_clear()
        trial_mode.enabled.cache_clear()
        script_calls.start_request(str(checkout.ROOT), "operate.py", ["next"])
        from file_reads import stats_stand_but
        stats_stand_but(None)
        status, retry, keep = 1, False, True
        if pending is not None:
            pending.running = current
        try:
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                signal.signal(signal.SIGALRM, lambda *_: arm(current))
                arm(current)
                current.check(code=True)
                if current.refresh:
                    current.detach()
                    state_assembly.read_state(current.operator)
                    status = 0
                else:
                    with executor():
                        status = operate.main(["next", current.operator])
                current.check()
        except Replaced:
            retry, keep = True, False
        except Detached:
            pass
        except (Unavailable, kept_reads.Unavailable) as exc:
            keep = False
            stdout.seek(0)
            stdout.truncate(0)
            print(f"operate: {exc}", file=stderr)
        except Exception:
            stdout.seek(0)
            stdout.truncate(0)
            traceback.print_exc(file=stderr)
            keep = False
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            if not kept_reads.flush():
                store = kept_reads.store()
                stdout.seek(0)
                stdout.truncate(0)
                if store is not None and store.locked():
                    # A lock is transient: the records stay held for the retry's flush.
                    status, retry = 1, True
                else:
                    status, retry, keep = 1, False, False
                    print(f"operate: kept-read store cannot preserve completed reads: "
                          f"{store.path if store is not None else ''}: "
                          f"{store.write_error if store is not None else ''}", file=stderr)
        response = {"status": status, "stdout": "" if retry else stdout.getvalue(),
                    "stderr": "" if retry else stderr.getvalue(),
                    "retry": retry}
        connection.settimeout(1)
        try:
            if not current.waiting:
                pass
            elif not retry and status == 0:
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
