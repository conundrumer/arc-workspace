"""The alarms of a process (`alarms`) come at their time whatever other alarm
a block sets or clears while they are due; a late alarm is silent."""

import os
import time

import pytest

from tests.conftest import script

alarms = script("alarms")
run_scripts = script("run_scripts")


def spin_until(condition, seconds: float = 10.0) -> None:
    """Run bytecode, where a handler can run, until `condition` holds."""
    end = time.monotonic() + seconds
    while not condition():
        assert time.monotonic() < end


def test_a_bounded_block_ends_at_its_bound_though_another_alarm_comes_and_is_set_again_inside_it():
    ticks: list[int] = []
    other = alarms.Alarm(lambda: (ticks.append(1), other.set(time.monotonic() + 0.05)))
    with pytest.raises(run_scripts.ScriptTimeout, match="ran past 1 seconds"):
        with run_scripts.bounded(1, "the call"):
            other.set(time.monotonic() + 0.05)
            spin_until(lambda: False)
    other.clear()
    assert len(ticks) > 1


def test_a_callback_runs_to_its_end_before_an_alarm_it_set_comes():
    order: list[str] = []
    second = alarms.Alarm(lambda: order.append("second"))

    def first_callback() -> None:
        order.append("first start")
        second.set(time.monotonic())
        end = time.monotonic() + 0.1
        while time.monotonic() < end:
            pass
        order.append("first end")

    first = alarms.Alarm(first_callback)
    first.set(time.monotonic() + 0.01)
    spin_until(lambda: "second" in order)
    assert order == ["first start", "first end", "second"]


def test_a_cleared_alarm_does_not_come():
    came: list[int] = []
    alarm = alarms.Alarm(lambda: came.append(1))
    alarm.set(time.monotonic() + 0.05)
    alarm.clear()
    time.sleep(0.2)
    assert came == []


def test_a_forked_child_runs_no_alarm_of_its_parent(tmp_path):
    marks = tmp_path / "marks"
    parent = alarms.Alarm(lambda: marks.open("a").write(f"parent alarm in {os.getpid()}\n"))
    parent.set(time.monotonic() + 0.4)
    pid = os.fork()
    if pid == 0:
        status = 1
        try:
            own = alarms.Alarm(lambda: marks.open("a").write("child alarm\n"))
            own.set(time.monotonic() + 0.05)
            time.sleep(1)
            status = 0
        finally:
            os._exit(status)
    parent.clear()
    assert os.waitpid(pid, 0)[1] == 0
    assert marks.read_text() == "child alarm\n"
