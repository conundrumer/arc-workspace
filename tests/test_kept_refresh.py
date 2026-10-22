"""The refresh locks of the sessions' kept reads: a merge takes them
before its fast-forward and releases them once it has landed, and a state
read waits for them; the refresh then asks each session's resident to read."""

import fcntl
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

import pytest

from tests.conftest import script

kept_refresh = script("kept_refresh")
refresh_locks = script("refresh_locks")

ENV = {"PATH": os.environ["PATH"], "HOME": os.environ["HOME"], "GIT_AUTHOR_NAME": "t",
       "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}


@pytest.fixture
def caches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(refresh_locks.checkout, "caches", lambda: tmp_path / "caches")
    return tmp_path / "caches"


def is_held(session: str) -> bool:
    with open(refresh_locks.lock_path(session)) as f:
        try:
            fcntl.flock(f, fcntl.LOCK_SH | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        return False


def test_refresh_asks_each_session_with_an_operator_and_goes_on_after_a_failure(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """A session with no operator is not asked, and a session whose request
    fails does not stop the sessions after it."""
    asked: list[tuple[str, str]] = []
    monkeypatch.setattr(kept_refresh, "operator_runs",
                        lambda s, me: [] if s == "idle" else [(f"op-{s}", Path(s))])

    def ask(main: Path, session: str, operator: str) -> None:
        asked.append((session, operator))
        if session == "a":
            raise RuntimeError("fixture failure")

    monkeypatch.setattr(kept_refresh.operate_service, "refresh_resident", ask)
    assert kept_refresh.refresh(Path("."), ["m", "a", "idle", "b"]) is False
    assert asked == [("m", "op-m"), ("a", "op-a"), ("b", "op-b")]


def repo(tmp_path: Path, name: str) -> tuple[Path, str]:
    """A repo whose `master` has one commit, and a commit after it that
    adds the file `name`."""
    main = tmp_path / "main"
    main.mkdir(parents=True)
    for argv in (("init", "-q", "-b", "master"), ("commit", "-q", "--allow-empty", "-m", "a")):
        subprocess.run(("git", *argv), cwd=main, env=ENV, check=True)
    (main / name).write_text("x")
    for argv in (("add", name), ("commit", "-q", "-m", "b")):
        subprocess.run(("git", *argv), cwd=main, env=ENV, check=True)
    top = subprocess.run(("git", "rev-parse", "HEAD"), cwd=main, env=ENV, check=True,
                         capture_output=True, text=True).stdout.strip()
    subprocess.run(("git", "reset", "-q", "--hard", "HEAD~"), cwd=main, env=ENV, check=True)
    return main, top


def test_merge_locks_released_where_nothing_lands(caches: Path, tmp_path: Path) -> None:
    """The locks are taken for a fast-forward that changes a `.py` file,
    for none that does not, and released where no fast-forward landed."""
    main, top = repo(tmp_path, "m.py")
    locks = refresh_locks.MergeLocks(main, "m")
    locks.take(top)
    assert is_held("m")
    assert locks.start() is None
    assert not is_held("m")
    other, plain = repo(tmp_path / "o", "m.txt")
    locks = refresh_locks.MergeLocks(other, "n")
    locks.take(plain)
    assert locks.files == {}


def test_merge_locks_released_at_landing_and_the_refresh_gets_the_sessions(
        caches: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """No lock is held once the fast-forward has landed, and the refresh
    process is started with the sessions it locked."""
    main, top = repo(tmp_path, "m.py")
    given = tmp_path / "given"
    stub = tmp_path / "stub.py"
    stub.write_text(f"import sys\nopen({str(given)!r}, 'w').write(' '.join(sys.argv[1:]))\n")
    monkeypatch.setattr(refresh_locks, "REFRESH", (str(stub),))
    locks = refresh_locks.MergeLocks(main, "m")
    locks.take(top)
    assert is_held("m")
    locks.mark_landed()
    assert not is_held("m")
    proc = locks.start()
    assert proc is not None
    proc.wait()
    assert given.read_text() == "m"


def test_read_waits_for_refresh(caches: Path) -> None:
    """`wait_free` returns only once the refresh lock is released."""
    order: list[str] = []
    f = refresh_locks.hold("s")
    waiter = threading.Thread(target=lambda: (refresh_locks.wait_free("s"),
                                              order.append("returned")))
    waiter.start()
    time.sleep(0.3)
    order.append("released")
    f.close()
    waiter.join()
    assert order == ["released", "returned"]
