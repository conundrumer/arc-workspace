"""`scripts/run_heavy.py` starts no command while the daemon holds its budget
or the kernel reports memory pressure, starts the calls of a queue in the order
they came, keeps a short job's reserve out of the long jobs' reach, frees a
share when its command ends, starts a nested call at once, and refuses with
status 125 where it cannot reach the daemon. The daemon runs the main tree's
script, takes up a changed copy of its own source while it runs, and is no
member of a job.

The machine is a directory of readings that `sysctl`, `vm_stat` and `ps` stubs
on `PATH` print, so a test sets the budget (2 CPUs and 4 GiB) and the pressure
level it needs, and the daemon each call starts runs on a temporary directory
that the test ends."""

import json
import os
import shutil
import signal
import subprocess
import time
from pathlib import Path

import pytest

from engine import checkout
from handbook.paths import scripts_importable

scripts_importable()

import heavy_client  # pyright: ignore[reportMissingImports]
import heavy_protocol  # pyright: ignore[reportMissingImports]

RUN_HEAVY = str(checkout.scripts() / "run_heavy.py")
SYSCTL = '#!/bin/sh\n[ "$1" = -n ] && shift\nfor key in "$@"; do cat "$FAKE_MACHINE/$key" || exit 1; done\n'
VM_STAT = '#!/bin/sh\ncat "$FAKE_MACHINE/vm_stat"\n'
PS = '#!/bin/sh\n[ -e "$FAKE_MACHINE/ps-fail" ] && exit 1\ncase "$1" in -Eww) cat "$FAKE_MACHINE/ps-env";; *) cat "$FAKE_MACHINE/ps";; esac\n'
SWAPINS = "Mach Virtual Memory Statistics: (page size of 16384 bytes)\nPageins: 5.\nSwapins: 0.\n"
PRESSURE = "kern.memorystatus_vm_pressure_level"
HOLD = "echo up; exec sleep 300"


class Machine:
    """The directory of a daemon and the readings of a machine, for one test."""

    def __init__(self, root: Path) -> None:
        self.daemon = root / "daemon"
        self.readings = root / "readings"
        self.readings.mkdir()
        bin = root / "bin"
        bin.mkdir()
        for name, text in (("sysctl", SYSCTL), ("vm_stat", VM_STAT), ("ps", PS)):
            (bin / name).write_text(text)
            (bin / name).chmod(0o755)
        self.set("hw.logicalcpu", 4)
        self.set("hw.memsize", 8 << 30)
        self.set(PRESSURE, 1)
        (self.readings / "vm_stat").write_text(SWAPINS)
        (self.readings / "ps").write_text("")
        (self.readings / "ps-env").write_text("")
        (root / "config").mkdir()
        (root / "socks").mkdir()
        self.env = {"PATH": f"{bin}:/usr/bin:/bin:/usr/sbin", "ARC_HEAVY_DIR": str(self.daemon),
                    "FAKE_MACHINE": str(self.readings), "CLAUDE_CONFIG_DIR": str(root / "config"),
                    "ARC_HEAVY_SOCKS": str(root / "socks"), "HOME": str(root)}
        self.calls: list[subprocess.Popen[str]] = []
        self.run_heavy = RUN_HEAVY

    def set(self, key: str, value: int) -> None:
        (self.readings / key).write_text(f"{value}\n")

    def start(self, *args: str, env: dict[str, str] | None = None) -> subprocess.Popen[str]:
        call = subprocess.Popen([self.run_heavy, *args], text=True, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, env={**self.env, **(env or {})})
        self.calls.append(call)
        return call

    def holder(self, *args: str) -> subprocess.Popen[str]:
        """A call whose command holds its share until the call is killed, once it runs."""
        call = self.start(*args, "sh", "-c", HOLD)
        assert call.stdout is not None
        assert call.stdout.readline() == "up\n"
        return call

    def queue(self) -> str:
        return subprocess.run([self.run_heavy, "queue"], text=True, capture_output=True, env=self.env).stdout

    def end(self) -> None:
        for call in self.calls:
            if call.poll() is None:
                call.kill()
            call.wait()
            for stream in (call.stdout, call.stderr):
                if stream is not None:
                    stream.close()
        try:
            record = json.loads((self.daemon / "registry.json").read_text())
        except (FileNotFoundError, ValueError):
            return
        try:
            os.kill(record["daemon"], signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            os.unlink(heavy_protocol.socket_path(str(self.daemon)))
        except FileNotFoundError:
            pass


@pytest.fixture
def machine(tmp_path):
    machine = Machine(tmp_path)
    yield machine
    machine.end()


def first_stderr_line(call: subprocess.Popen[str]) -> str:
    assert call.stderr is not None
    return call.stderr.readline()


def until(condition, seconds: int = 5) -> bool:
    """Whether `condition` holds within `seconds`, polled."""
    for _ in range(seconds * 10):
        if condition():
            return True
        time.sleep(0.1)
    return condition()


def release(call: subprocess.Popen[str]) -> None:
    call.kill()
    call.wait()


def test_a_call_starts_no_command_while_the_budget_is_held(machine, tmp_path):
    holder = machine.holder("--cpus", "4")
    marker = tmp_path / "ran"
    call = machine.start("touch", str(marker))
    assert "waiting for" in first_stderr_line(call)
    assert not marker.exists()
    release(holder)
    assert call.wait() == 0
    assert marker.exists()


def test_a_request_over_the_budget_is_cut_to_it_and_waits_for_all_of_it(machine, tmp_path):
    holder = machine.holder()
    marker = tmp_path / "ran"
    call = machine.start("--cpus", "99", "touch", str(marker))
    assert "cut to the budget: 4 CPUs" in first_stderr_line(call)
    assert "waiting for" in first_stderr_line(call)
    assert not marker.exists()
    release(holder)
    assert call.wait() == 0
    assert marker.exists()


def test_a_call_starts_no_command_under_memory_pressure(machine, tmp_path):
    machine.set(PRESSURE, 2)
    marker = tmp_path / "ran"
    call = machine.start("touch", str(marker))
    assert "memory pressure" in first_stderr_line(call)
    assert not marker.exists()
    machine.set(PRESSURE, 1)
    assert call.wait() == 0
    assert marker.exists()


def test_calls_start_in_the_order_they_came(machine, tmp_path):
    holder = machine.holder("--cpus", "3", "--gib", "1")
    log = tmp_path / "log"
    first = machine.start("--cpus", "4", "--gib", "1", "sh", "-c", f"echo first >> {log}")
    first_stderr_line(first)
    second = machine.start("--cpus", "1", "--gib", "1", "sh", "-c", f"echo second >> {log}")
    first_stderr_line(second)  # it waits for the call before it, though one CPU is free
    release(holder)
    assert first.wait() == 0 and second.wait() == 0
    assert log.read_text() == "first\nsecond\n"


def test_a_short_job_starts_beside_a_long_job_that_holds_all_that_long_jobs_may(machine, tmp_path):
    long_job = machine.holder("--need", "now", "--minutes", "10", "--cpus", "2", "--gib", "2")
    waiting = machine.start("--need", "now", "--minutes", "10", "--gib", "1", "touch", str(tmp_path / "long"))
    first_stderr_line(waiting)
    short = machine.start("--cpus", "2", "--gib", "2", "touch", str(tmp_path / "short"))
    assert short.wait() == 0
    assert (tmp_path / "short").exists() and not (tmp_path / "long").exists()
    release(long_job)
    assert waiting.wait() == 0


def test_the_queue_names_each_job_that_holds_a_share_and_each_call_that_waits(machine):
    holder = machine.holder("--cpus", "4", "--need", "now", "--minutes", "30")
    waiting = machine.start("--cpus", "2", "--gib", "4", "--need", "idle", "true")
    first_stderr_line(waiting)
    text = machine.queue()
    assert str(holder.pid) in text and str(waiting.pid) in text and "idle" in text


def test_a_call_killed_while_it_waits_leaves_the_queue(machine):
    holder = machine.holder("--cpus", "4")
    waiting = machine.start("--cpus", "4", "true")
    first_stderr_line(waiting)
    release(waiting)
    assert until(lambda: str(waiting.pid) not in machine.queue())
    assert str(holder.pid) in machine.queue()


def test_the_command_is_the_calls_own_process_and_its_share_ends_with_it(machine, tmp_path):
    call = machine.start("--cpus", "4", "sh", "-c", "echo $$; exec sleep 300")
    assert call.stdout is not None
    assert int(call.stdout.readline()) == call.pid
    waiting = machine.start("touch", str(tmp_path / "ran"))
    first_stderr_line(waiting)
    release(call)  # SIGKILL
    assert waiting.wait() == 0


def test_a_wait_that_runs_out_gives_the_expected_start(machine):
    machine.holder("--cpus", "4")
    call = machine.start("--wait", "1", "true")
    _, errors = call.communicate()
    assert call.returncode == 125
    assert "expected start" in errors


def test_a_changed_need_reorders_a_waiting_call_and_a_pid_that_does_not_wait_is_refused(machine):
    machine.holder("--cpus", "4")
    first = machine.start("--cpus", "4", "--need", "idle", "true")
    first_stderr_line(first)
    second = machine.start("--cpus", "4", "--need", "soon", "true")
    first_stderr_line(second)

    def order() -> list[int]:
        text = machine.queue().split("waiting:", 1)[1]
        return sorted((first.pid, second.pid), key=lambda pid: text.index(f"  {pid} "))

    assert order() == [second.pid, first.pid]
    changed = subprocess.run([RUN_HEAVY, "need", str(first.pid), "now"], text=True, capture_output=True,
                             env=machine.env)
    assert changed.returncode == 0
    assert order() == [first.pid, second.pid]
    for args in (["need", "99999", "now"], ["need", str(first.pid), "never"], ["need", "x"]):
        refused = subprocess.run([RUN_HEAVY, *args], text=True, capture_output=True, env=machine.env)
        assert refused.returncode == 125 and refused.stderr.startswith("run_heavy.py: ")


def test_a_restarted_daemon_still_holds_the_share_of_a_command_that_runs(machine, tmp_path):
    machine.holder("--cpus", "4")
    record = json.loads((machine.daemon / "registry.json").read_text())
    os.kill(record["daemon"], signal.SIGKILL)
    call = machine.start("touch", str(tmp_path / "ran"))
    assert "waiting for" in first_stderr_line(call)
    assert until(lambda: json.loads((machine.daemon / "registry.json").read_text())["daemon"] != record["daemon"])
    assert not (tmp_path / "ran").exists()


def test_a_nested_call_starts_at_once_within_its_parents_share(machine):
    machine.set(PRESSURE, 4)
    call = machine.start("--cpus", "5", "sh", "-c", "echo $ARC_HEAVY_CPUS $CARGO_BUILD_JOBS $ARCLOG_THREADS",
                         env={"ARC_HEAVY_CPUS": "2", "ARCLOG_THREADS": "1"})
    out, _ = call.communicate()
    assert call.returncode == 0
    assert out == "2 2 1\n"
    assert not machine.daemon.exists()


def test_a_gated_command_gets_its_share_as_its_pool_sizes(machine):
    call = machine.start("--cpus", "2", "sh", "-c", "echo $ARC_HEAVY_CPUS $RAYON_NUM_THREADS")
    out, _ = call.communicate()
    assert out == "2 2\n"


def test_a_failure_before_the_start_exits_125_126_or_127(machine, tmp_path):
    assert machine.start().wait() == 125
    assert machine.start("--cpus", "none", "true").wait() == 125
    assert machine.start("--need", "never", "true").wait() == 125
    assert machine.start("--minutes", "0", "true").wait() == 125
    assert machine.start("--wait", "soon", "true").wait() == 125
    assert machine.start("no-such-command").wait() == 127
    plain = tmp_path / "plain"
    plain.write_text("")
    assert machine.start(str(plain)).wait() == 126


@pytest.mark.parametrize("reading", ["hw.logicalcpu", PRESSURE, "vm_stat"])
def test_a_reading_that_cannot_be_read_exits_125(machine, reading):
    (machine.readings / reading).write_text("garbage\n")
    call = machine.start("true")
    _, errors = call.communicate()
    assert call.returncode == 125
    assert errors.startswith("run_heavy.py: ")


def test_a_reading_that_fails_on_the_request_path_refuses_with_its_cause_and_the_daemon_stays(machine):
    assert machine.start("true").wait() == 0
    (machine.readings / "ps-fail").write_text("")
    call = machine.start("true")
    _, errors = call.communicate()
    assert call.returncode == 125
    assert errors.startswith("run_heavy.py: cannot read")
    assert "closing the connection" not in errors
    assert "budget:" in machine.queue()


def test_a_call_that_cannot_reach_or_start_the_daemon_exits_125_with_the_cause(machine, tmp_path):
    file = tmp_path / "file"
    file.write_text("")
    call = machine.start("true", env={"ARC_HEAVY_DIR": str(file / "daemon")})
    _, errors = call.communicate()
    assert call.returncode == 125
    assert "daemon directory" in errors


def test_the_daemon_script_is_the_main_trees_unless_the_daemon_directory_is_set(monkeypatch):
    monkeypatch.delenv(heavy_protocol.DIR_ENV, raising=False)
    main = checkout.main_worktree(checkout.ROOT) / "scripts" / "resource_daemon.py"
    assert Path(heavy_client.daemon_script()).resolve() == main.resolve()
    monkeypatch.setenv(heavy_protocol.DIR_ENV, "/unused")
    assert Path(heavy_client.daemon_script()).resolve() == (checkout.scripts() / "resource_daemon.py").resolve()


def test_a_daemon_that_takes_up_a_changed_source_keeps_its_job_and_its_waiting_call(machine, tmp_path):
    scripts = tmp_path / "scripts-copy"
    shutil.copytree(checkout.scripts(), scripts, ignore=shutil.ignore_patterns("__pycache__"))
    machine.run_heavy = str(scripts / "run_heavy.py")
    holder = machine.holder("--cpus", "4")
    daemon = json.loads((machine.daemon / "registry.json").read_text())["daemon"]
    marker = tmp_path / "ran"
    call = machine.start("touch", str(marker))
    assert "waiting for" in first_stderr_line(call)
    machine.set(PRESSURE, 2)  # a sample each second
    with (scripts / "heavy_core.py").open("a") as source:
        source.write("\n# changed\n")
    assert until(lambda: "restart" in (machine.daemon / "daemon.log").read_text(), 20)
    assert until(lambda: f"  {call.pid} " in machine.queue().split("waiting:", 1)[-1], 20)
    assert f"  {holder.pid} " in machine.queue().split("waiting:", 1)[0]
    assert json.loads((machine.daemon / "registry.json").read_text())["daemon"] == daemon
    assert call.poll() is None and not marker.exists()
    machine.set(PRESSURE, 1)
    release(holder)
    assert call.wait() == 0
    assert marker.exists()


def test_a_daemon_that_stops_is_no_zombie_of_the_call_that_started_it(machine):
    holder = machine.holder()
    daemon = json.loads((machine.daemon / "registry.json").read_text())["daemon"]
    os.kill(daemon, signal.SIGTERM)

    def gone() -> bool:
        try:
            os.kill(daemon, 0)
        except ProcessLookupError:
            return True
        return False

    assert until(gone, 20)
    release(holder)


def test_the_daemon_is_no_member_of_the_job_of_the_call_that_started_it(machine):
    holder = machine.holder()
    daemon = json.loads((machine.daemon / "registry.json").read_text())["daemon"]
    child = subprocess.Popen(["sleep", "300"])
    try:
        row = "{} {} 0.0 00:10 Mon Jan  1 00:00:00 2024 {}\n"
        (machine.readings / "ps").write_text(row.format(holder.pid, 1, "sleep 300")
                                             + row.format(daemon, holder.pid, "python resource_daemon.py")
                                             + row.format(child.pid, holder.pid, "sleep 300"))

        def members() -> list[int]:
            record = json.loads((machine.daemon / "registry.json").read_text())
            return [int(pid) for pid in record["jobs"][0]["members"]]

        assert until(lambda: child.pid in members(), 20)
        assert daemon not in members()
    finally:
        child.kill()
        child.wait()
