"""The refresh locks of the sessions' kept reads: a merge takes them
before its fast-forward and hands them to the refresh, which releases each
once that session's child ends, and a state read waits for them, so that
a read does not compute the reads the merge made stale."""

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
refresh_locks = sys.modules["refresh_locks"]

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


def test_refresh_releases_each_lock_after_its_child(
        caches: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Every session's lock is held from the first child on, and each until
    its own child ends; the merging session's end is written before the
    others run; a session with no operator has no child."""
    events: list[Any] = []
    monkeypatch.setattr(kept_refresh, "operator_runs",
                        lambda s, me: [] if s == "idle" else [(f"op-{s}", Path(s))])

    def run(argv: tuple[str, ...], env: dict[str, str], **_: Any) -> None:
        session = env["CLAUDE_CODE_SESSION_ID"]
        events.append((session, argv[-1], [s for s in ("m", "a", "b") if is_held(s)]))

    monkeypatch.setattr(kept_refresh.subprocess, "run", run)
    monkeypatch.setattr(kept_refresh, "said_refreshed", lambda: events.append("said"))
    held = {s: refresh_locks.hold(s) for s in ("m", "a", "idle", "b")}
    kept_refresh.refresh(caches, "m", held)
    assert events == [("m", "op-m", ["m", "a", "b"]), "said", ("a", "op-a", ["a", "b"]),
                      ("b", "op-b", ["b"])]
    assert not any(is_held(s) for s in ("m", "a", "b", "idle"))


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


def test_merge_locks_handed_to_the_refresh(caches: Path, tmp_path: Path,
                                           monkeypatch: pytest.MonkeyPatch) -> None:
    """The refresh process holds the locks once the merge's copies are
    closed, until it ends."""
    main, top = repo(tmp_path, "m.py")
    go = tmp_path / "go"
    stub = tmp_path / "stub.py"
    stub.write_text(f"import os, time\nwhile not os.path.exists({str(go)!r}):\n"
                    "    time.sleep(0.05)\n")
    monkeypatch.setattr(refresh_locks, "REFRESH", (str(stub),))
    locks = refresh_locks.MergeLocks(main, "m")
    locks.take(top)
    locks.mark_landed()
    proc = locks.start()
    assert proc is not None
    assert locks.files == {}
    assert is_held("m")
    go.write_text("")
    proc.wait()
    assert not is_held("m")


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
