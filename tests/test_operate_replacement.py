"""Replacement during startup reaps the first-read child before owner exit."""

import fcntl
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

import pytest

from tests.conftest import script
from tests.test_operate_service import SCRIPTS, service


STARTUP = '''
import os
import sys
from pathlib import Path
import operate_service as service
import operate
import kept_reads
import script_calls
root = Path.cwd()
service.checkout.ROOT = root
service.checkout.caches = lambda: root / "cache"
service.endpoint = lambda *_: Path("owner.sock")
operate.__file__ = str(root / "identity.py")
script_calls.RECORDS = str(root / "records")
blocked, release = os.pipe()
def child():
    os.write(1, ("child " + str(os.getpid()) + "\\n").encode())
    os.read(blocked, 1)
def parent():
    kept_reads.store().keep("operate:fixture", "key", "completed")
    os.write(1, b"parent\\n")
    os.read(0, 1)
os.register_at_fork(after_in_child=child, after_in_parent=parent)
reason = service.serve()
try:
    os.waitpid(-1, os.WNOHANG)
except ChildProcessError:
    print("reaped", flush=True)
else:
    raise AssertionError("first-read child remains")
print(reason, flush=True)
sys.stdin.read(1)
os._exit(0)
'''


@pytest.mark.parametrize("cleanup_failure", [False, True])
def test_replacement_during_startup_with_queued_clients(tmp_path, monkeypatch, cleanup_failure):
    refresh = script("refresh_locks")
    monkeypatch.setattr(refresh.checkout, "caches", lambda: tmp_path / "cache")
    monkeypatch.chdir(tmp_path)
    identity = tmp_path / "identity.py"
    identity.write_text("value = 1\n")
    process = subprocess.Popen(
        [sys.executable, "-u", "-c", STARTUP], cwd=tmp_path,
        env={"PATH": os.defpath, "HOME": str(tmp_path), "CLAUDE_CONFIG_DIR": str(tmp_path),
             "CLAUDE_CODE_SESSION_ID": "replacement-test", "PYTHONPATH":
             os.pathsep.join((str(SCRIPTS), str(SCRIPTS.parent / "src")))},
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    peers = []
    try:
        deadline = time.monotonic() + 15
        while True:
            first = socket.socket(socket.AF_UNIX)
            try:
                first.connect("owner.sock")
                break
            except (FileNotFoundError, ConnectionRefusedError):
                first.close()
                if process.poll() is not None:
                    assert process.stderr is not None
                    pytest.fail(process.stderr.read().decode())
                assert time.monotonic() < deadline
                time.sleep(0.01)
        peers.append(first)

        def request(peer, kind, subject):
            peer.settimeout(15)
            peer.sendall((json.dumps({"kind": kind, "subject": subject,
                                     "started": time.time(), "deadline": time.monotonic() + 30})
                          + "\n").encode())

        request(first, "next", "first")
        stream = first.makefile("rb")
        assert stream.readline() == service.TAKEN
        assert process.stdout is not None and process.stdin is not None
        ready = [process.stdout.readline().decode().strip() for _ in range(2)]
        child = int(next(line.split()[1] for line in ready if line.startswith("child ")))
        assert "parent" in ready
        for kind in ("refresh", "next"):
            peer = socket.socket(socket.AF_UNIX)
            peer.connect("owner.sock")
            peers.append(peer)
            request(peer, kind, "queued")
        with refresh.hold("replacement-test"):
            identity.write_text("value = 2\n")
            identity.write_text("value = 3\n")
            if cleanup_failure:
                import sqlite3
                with sqlite3.connect(tmp_path / "cache" / "kept-reads.sqlite") as db:
                    db.execute("DROP TABLE records")
            process.stdin.write(b"c")
            process.stdin.flush()
            reply = json.loads(stream.readline())
            assert reply["status"] == 1
            assert reply["retry"] is not cleanup_failure
            if cleanup_failure:
                assert "cannot preserve completed reads" in reply["stderr"]
            assert process.stdout.readline() == b"reaped\n"
            assert process.stdout.readline().strip() == (b"store failure" if cleanup_failure else b"replaced")
            with pytest.raises(ProcessLookupError):
                os.kill(child, 0)
            with (tmp_path / "owner.owner").open("a") as owner:
                with pytest.raises(BlockingIOError):
                    fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
                process.stdin.write(b"e")
                process.stdin.flush()
                assert process.wait(timeout=10) == 0
                fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
        stream.close()
        assert not (tmp_path / "owner.sock").exists()
        assert not list(tmp_path.rglob("step-journal.jsonl"))
    finally:
        for peer in peers:
            peer.close()
        if process.poll() is None:
            process.kill()
        process.wait(timeout=10)
