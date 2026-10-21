"""Session and checkout scoped transport for resident `operate.py next` reads.

The journal owns issued work. Connections own requests and responses; an
incomplete response is discarded and a retry computes from the journal.
Only the serving thread accesses held reads. Idle expiry does no state read.
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
from collections.abc import Callable, Iterator
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

import script_calls

from engine import checkout
from operations.constants import LIMIT_SECONDS

IDLE_SECONDS = 1800
START_SECONDS = 30
FINISH_SECONDS = 5
"""Time left for the kept-read flush and the response after a state read stops."""
CODE_ENV = "ARC_OPERATE_CODE"


# Request cancellation must escape the state cache's failed-read handlers.
class Replaced(BaseException):
    """The interpreter must be replaced before the request can continue."""


class Disconnected(BaseException):
    """The request's client has gone or a replacement request waits."""


class Expired(BaseException):
    """The request reached its foreground deadline."""


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
    phase: str = "state"

    def check(self, code: bool = False) -> None:
        if time.monotonic() >= self.deadline:
            raise Expired
        readable, _, _ = select.select([self.connection, self.listener], [], [], 0)
        if self.listener in readable or self.connection in readable:
            raise Disconnected
        if code:
            import kept_reads
            if kept_reads.fresh_code("operate") != self.code:
                raise Replaced


CURRENT: ContextVar[Request | None] = ContextVar("operate_request", default=None)


def read_phase(phase: str) -> None:
    """Name the current read in a failure diagnostic."""
    if (request := CURRENT.get()) is not None:
        request.phase = phase


@contextlib.contextmanager
def reading() -> Iterator[None]:
    """Leave time to preserve completed reads and report an unfinished read.

    A read cannot be assumed to finish under arbitrary I/O or machine
    load. Stop it before the foreground watchdog can discard its cause
    and its completed work. A read begun too late is refused immediately.
    """
    current = CURRENT.get()
    if current is None:
        yield
        return

    def exhausted(*_: object) -> None:
        raise Unavailable(f"state read could not finish before the foreground deadline "
                          f"while reading {current.phase}; {FINISH_SECONDS} s reserved "
                          "to preserve completed reads and return this response")

    remaining = current.deadline - FINISH_SECONDS - time.monotonic()
    if remaining <= 0:
        exhausted()
    handler = signal.signal(signal.SIGALRM, exhausted)
    signal.setitimer(signal.ITIMER_REAL, remaining)
    try:
        yield
    finally:
        signal.signal(signal.SIGALRM, handler)
        signal.setitimer(signal.ITIMER_REAL, max(current.deadline - time.monotonic(), 0.001))


def check() -> None:
    """Validate the active request before a side effect or published result."""
    if (request := CURRENT.get()) is not None:
        request.check()


@contextlib.contextmanager
def side_effect() -> Iterator[None]:
    """Exclude a merge while validated request code issues work or publishes a step.

    The deadline signal is deferred until a started Bash run is journaled.
    Standalone commands keep their existing exclusion and watchdog.
    """
    current = CURRENT.get()
    if current is None:
        yield
        return
    from refresh_locks import lock_path
    from relay_reads import session_id
    path = lock_path(session_id())
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as lock:
        while True:
            try:
                fcntl.flock(lock, fcntl.LOCK_SH | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                pause(0.05)
        current.check()
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
        select.select([request.connection, request.listener], [], [], max(min(end - time.monotonic(), 0.2), 0))
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
        with path.with_suffix(".owner").open("a") as owner:
            try:
                fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                pass
            else:
                path.unlink(missing_ok=True)
                import kept_reads
                expected = kept_reads.fresh_code("operate")
                with path.with_suffix(".log").open("w") as errors:
                    process = subprocess.Popen(
                        [sys.executable, "-B", "-X", f"pycache_prefix={path.with_suffix('.pyc')}",
                         str(main / "scripts/operate_service.py"), "startup"], cwd=main,
                        env={**os.environ, script_calls.SESSION_ENV: session, CODE_ENV: expected},
                        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                        stderr=errors, start_new_session=True)
        until = min(deadline, time.monotonic() + START_SECONDS)
        while time.monotonic() < until:
            if process is not None and process.poll() is not None:
                detail = path.with_suffix(".log").read_text()[-4096:].strip()
                raise Unavailable(f"resident startup exited ({process.returncode}): "
                                  f"{detail or 'no diagnostic from the resident'}")
            try:
                return connect(path, deadline - time.monotonic())
            except OSError:
                time.sleep(0.05)
        raise Unavailable(f"resident did not open its socket within {START_SECONDS} s")


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
    """A complete response, or None when a replacement interpreter is required."""
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
        print(f"operate: {exc}", file=sys.stderr)
        return 1
    except Expired:
        timeout_output(operator)
        return 1
    finally:
        signal.alarm(0)
    status, stdout, stderr = result
    sys.stdout.write(stdout)
    sys.stderr.write(stderr)
    return status


def request(main: Path, session: str, operator: str, started: float,
            deadline: float, refresh: bool) -> tuple[int, str, str]:
    """Retry transport failures from journal state within the original deadline."""
    while time.monotonic() < deadline:
        try:
            result = exchange(ensure(main, session, deadline), operator, started, deadline, refresh)
            if result is not None:
                return result
        except (ConnectionError, FileNotFoundError):
            pass
        started = time.time()
        time.sleep(0.05)
    raise Expired


def refresh_resident(main: Path, session: str, operator: str,
                     standalone: Callable[[], None] | None = None) -> bool:
    """Refresh an existing resident through its replacement, if one owns the session."""
    path = endpoint(main, session)
    with path.with_suffix(".start").open("a") as startup:
        fcntl.flock(startup, fcntl.LOCK_EX)
        with path.with_suffix(".owner").open("a") as owner:
            try:
                fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                pass
            else:
                if standalone is not None:
                    standalone()
                    return True
                return False
    status, _, _ = request(main, session, operator, time.time(),
                           time.monotonic() + LIMIT_SECONDS, True)
    if status:
        raise RuntimeError("resident refresh failed")
    return True


def serve_request(connection: socket.socket, listener: socket.socket, code: str) -> bool:
    """Serve one request; false retires this interpreter after a code change."""
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
                      connection, listener, code, stdout, stderr)
    token = CURRENT.set(current)
    cutoff = state_assembly.REQUEST_STARTED.set(current.started)
    codex_mode.enabled.cache_clear()
    trial_mode.enabled.cache_clear()
    script_calls.start_request(str(checkout.ROOT), "operate.py", ["next"])
    from file_reads import stats_stand_but
    stats_stand_but(None)
    status, retry, keep = 1, False, True
    try:
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(Expired()))
            signal.setitimer(signal.ITIMER_REAL, max(current.deadline - time.monotonic(), 0.001))
            current.check(code=True)
            if message["refresh"]:
                state_assembly.read_state(current.operator)
                status = 0
            else:
                with executor():
                    status = operate.main(["next", current.operator])
            current.check()
    except Replaced:
        retry, keep = True, False
    except Disconnected:
        stdout.seek(0)
        stdout.truncate(0)
        with contextlib.redirect_stdout(stdout):
            timeout_output(current.operator)
    except Expired:
        keep = False
        stdout.seek(0)
        stdout.truncate(0)
        with contextlib.redirect_stdout(stdout):
            timeout_output(current.operator)
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
            status, retry, keep = 1, False, False
            stdout.seek(0)
            stdout.truncate(0)
            store = kept_reads.store()
            print(f"operate: kept-read store cannot preserve completed reads: "
                  f"{store.path if store is not None else ''}: "
                  f"{store.write_error if store is not None else ''}", file=stderr)
    response = {"status": status, "stdout": stdout.getvalue(), "stderr": stderr.getvalue(),
                "retry": retry}
    connection.settimeout(1)
    try:
        if not retry and status == 0 and not message["refresh"]:
            try:
                with side_effect():
                    connection.sendall((json.dumps(response) + "\n").encode())
            except (Disconnected, Expired):
                pass
        else:
            connection.sendall((json.dumps(response) + "\n").encode())
    except OSError:
        pass
    finally:
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
            raise Unavailable("code changed during resident startup; no state read was started")
        script_calls.record()
        with socket.socket(socket.AF_UNIX) as listener:
            path.unlink(missing_ok=True)
            listener.bind(str(path))
            listener.listen()
            listener.settimeout(IDLE_SECONDS)
            try:
                while True:
                    try:
                        connection, _ = listener.accept()
                    except TimeoutError:
                        break
                    with connection:
                        try:
                            if not serve_request(connection, listener, code):
                                break
                        except (OSError, ValueError, KeyError, TypeError):
                            continue
            finally:
                path.unlink(missing_ok=True)
                kept_reads.flush()


if __name__ == "__main__":
    sys.modules["operate_service"] = sys.modules[__name__]
    serve()
    script_calls.record()
    os._exit(0)
