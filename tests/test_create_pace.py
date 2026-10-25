"""`create_pace.py` times the steps of a Create pass from the calls it records."""

import subprocess
import sys
from pathlib import Path

START = 1_000_000.0
SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "create_pace.py"


def at(minutes: float) -> float:
    return START + minutes * 60


def test_a_step_within_its_budget_prints_the_times_and_the_next_budget(tmp_path: Path) -> None:
    from create_pace import Step, pace  # pyright: ignore[reportMissingImports]
    pace(tmp_path, Step.READ, at(0))
    out = pace(tmp_path, Step.PRECEDENT, at(1))
    assert out.count("1.0 min") == 2
    assert f"{Step.PRECEDENT.cap.minutes:g} min" in out
    assert Step.PRECEDENT.cap.action in out
    assert "past" not in out


def test_a_step_past_its_budget_is_reported_with_no_action_for_it(tmp_path: Path) -> None:
    from create_pace import Step, pace  # pyright: ignore[reportMissingImports]
    pace(tmp_path, Step.READ, at(0))
    out = pace(tmp_path, Step.PRECEDENT, at(2))
    assert "past its budget" in out
    assert Step.READ.cap.action not in out
    assert Step.PRECEDENT.cap.action in out


def test_a_run_past_its_target_says_to_take_the_action_of_the_starting_step(tmp_path: Path) -> None:
    from create_pace import Step, pace  # pyright: ignore[reportMissingImports]
    pace(tmp_path, Step.READ, at(0))
    pace(tmp_path, Step.DEVELOP, at(13))
    out = pace(tmp_path, Step.DETERMINE, at(16))
    assert "past its target" in out
    assert "past its budget" not in out
    assert Step.DETERMINE.cap.action in out
    assert Step.DEVELOP.cap.action not in out


def test_the_first_call_past_the_limit_says_to_restore_the_last_pass_and_later_calls_do_not(
        tmp_path: Path) -> None:
    from create_pace import LAST_PASS, LAST_PASS_WITNESSES, Step, pace  # pyright: ignore[reportMissingImports]
    pace(tmp_path, Step.READ, at(0))
    pace(tmp_path, Step.DEVELOP, at(1))
    (tmp_path / LAST_PASS).write_text("")
    first = pace(tmp_path, Step.WITNESS, at(26))
    assert str(tmp_path / LAST_PASS) in first
    assert str(tmp_path / LAST_PASS_WITNESSES) in first
    assert "Report step" in first
    assert Step.WITNESS.cap.action not in first
    report = pace(tmp_path, Step.REPORT, at(27))
    assert str(tmp_path / LAST_PASS) not in report
    assert Step.REPORT.cap.action in report
    again = pace(tmp_path, Step.REPORT, at(28))
    assert str(tmp_path / LAST_PASS) not in again


def test_a_pass_with_no_saved_solver_says_to_keep_the_current_one(tmp_path: Path) -> None:
    from create_pace import LAST_PASS, Step, pace  # pyright: ignore[reportMissingImports]
    pace(tmp_path, Step.READ, at(0))
    out = pace(tmp_path, Step.WITNESS, at(26))
    assert LAST_PASS in out and "keep the current solver" in out


def test_a_read_call_starts_a_new_clock(tmp_path: Path) -> None:
    from create_pace import LAST_PASS, Step, pace  # pyright: ignore[reportMissingImports]
    pace(tmp_path, Step.READ, at(0))
    pace(tmp_path, Step.REPORT, at(30))
    out = pace(tmp_path, Step.READ, at(100))
    assert "limit of" not in out
    assert out.splitlines()[0].startswith("Run time used: 0.0 min")
    again = pace(tmp_path, Step.WRITE, at(101))
    assert "1.0 min" in again
    assert LAST_PASS not in again
    assert str(tmp_path / LAST_PASS) in pace(tmp_path, Step.WITNESS, at(130))


def test_a_repeated_call_keeps_the_start_of_the_step(tmp_path: Path) -> None:
    from create_pace import Step, pace  # pyright: ignore[reportMissingImports]
    pace(tmp_path, Step.READ, at(0))
    pace(tmp_path, Step.DEVELOP, at(1))
    pace(tmp_path, Step.DEVELOP, at(3))
    out = pace(tmp_path, Step.DEVELOP, at(4))
    assert "4.0 min" in out and "3.0 min" in out
    assert len((tmp_path / "pace.jsonl").read_text().splitlines()) == 2
    assert "Develop took" in pace(tmp_path, Step.WITNESS, at(5))


def test_a_repeated_call_prints_the_action_only_when_the_step_is_past_its_budget(tmp_path: Path) -> None:
    from create_pace import Step, pace  # pyright: ignore[reportMissingImports]
    pace(tmp_path, Step.READ, at(0))
    pace(tmp_path, Step.DEVELOP, at(1))
    within = pace(tmp_path, Step.DEVELOP, at(4))
    past = pace(tmp_path, Step.DEVELOP, at(6))
    assert Step.DEVELOP.cap.action not in within
    assert Step.DEVELOP.cap.action in past


def test_a_repeated_call_past_the_limit_prints_the_limit_text(tmp_path: Path) -> None:
    from create_pace import LAST_PASS, Step, pace  # pyright: ignore[reportMissingImports]
    pace(tmp_path, Step.READ, at(0))
    pace(tmp_path, Step.DEVELOP, at(1))
    out = pace(tmp_path, Step.DEVELOP, at(26))
    assert str(tmp_path / LAST_PASS) in out
    assert Step.DEVELOP.cap.action not in out
    assert str(tmp_path / LAST_PASS) not in pace(tmp_path, Step.DEVELOP, at(27))


def test_a_status_of_a_timeout_or_a_kill_is_named_and_another_adds_nothing(tmp_path: Path) -> None:
    from create_pace import Step, pace  # pyright: ignore[reportMissingImports]
    pace(tmp_path, Step.READ, at(0))
    pace(tmp_path, Step.DEVELOP, at(1))
    plain = pace(tmp_path, Step.DEVELOP, at(2))
    assert pace(tmp_path, Step.DEVELOP, at(2), 0) == plain
    timeout = pace(tmp_path, Step.DEVELOP, at(2), 124)
    killed = pace(tmp_path, Step.DEVELOP, at(2), 137)
    assert "124" in timeout and "137" in killed
    assert "Rules for one long command" in timeout and "Rules for one long command" in killed
    assert "124" not in killed and "137" not in timeout


def test_an_unknown_step_is_refused_with_the_list_of_steps(tmp_path: Path) -> None:
    done = subprocess.run([sys.executable, str(SCRIPT), "abcdef12", "plan"], cwd=tmp_path, env={},
                          capture_output=True, text=True)
    assert done.returncode == 2
    for slug in ("read", "precedent-and-design", "write", "develop", "determine", "witness",
                 "simplify-and-prune", "report"):
        assert f"`{slug}`" in done.stderr
    assert not (tmp_path / "work").exists()
