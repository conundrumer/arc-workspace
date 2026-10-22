"""A line pace that admits work caps the running agents by its slack."""

import math
from pathlib import Path


def usage(used: float, elapsed: float, now: float = 9000.0):
    from operations.pacing import Usage, Window
    return Usage(now, {"five_hour": Window(used, elapsed, 18000.0)})


def test_a_line_pace_that_admits_work_caps_the_running_agents_by_its_slack() -> None:
    from operations.pacing import DEFAULT, Until, WindowName, asap, by, preset
    from operations.constants import SUBAGENT_LIMIT
    even = preset(["even", "--factor", "1", "--window", "five_hour"])
    assert even(usage(90, 90)) == Until(9000.0, 1)
    assert even(usage(80, 90)) == Until(9000.0, 20)
    assert even(usage(85, 90)) == Until(9000.0, 10)
    assert even(usage(60, 90)) == Until(9000.0, SUBAGENT_LIMIT)
    assert by(usage(85, 0.0), 10000.0, WindowName.FIVE_HOUR) == Until(9000.0, 10)
    assert DEFAULT(usage(85, 90)) == Until(9000.0)
    assert asap(usage(85, 90)) == Until(-math.inf)


def test_presets_joined_by_a_semicolon_admit_work_only_where_each_admits_it(tmp_path: Path) -> None:
    from operations.pacing import Until, Usage, Window, admits, line_pace
    from operations.state import NotComputed
    joined = line_pace("even --window five_hour; by 1970-01-01T05:00:00+00:00 --window seven_day", tmp_path)
    assert callable(joined)

    def usage(five: float, seven: float) -> Usage:
        return Usage(9000.0, {"five_hour": Window(five, 50.0, 18000.0),
                              "seven_day": Window(seven, 0.0, 7 * 86400.0)})

    assert joined(usage(45.0, 0.0)) == Until(9000.0, 10)
    assert joined(usage(40.0, 45.0)) == Until(9000.0, 10)
    for past in (usage(60.0, 0.0), usage(40.0, 60.0)):
        assert not admits(joined(past), 9000.0)
        assert admits(joined(past), 10800.0)
    assert isinstance(joined(Usage(9000.0, {"five_hour": Window(40.0, 50.0, 18000.0)})), NotComputed)
    weekly = line_pace("by 1970-01-01T05:00:00+00:00 --window seven_day", tmp_path)
    assert callable(weekly)
    assert not admits(weekly(usage(60.0, 0.0)), 9000.0)
    assert weekly(usage(45.0, 0.0)) == Until(9000.0, 10)
    hourly = line_pace("even --factor 2 --window five_hour", tmp_path)
    assert callable(hourly)
    assert hourly(usage(60.0, 0.0)) == Until(9000.0, 20)
    for line in ("even;;asap", "even; ", "even; x.py"):
        assert line_pace(line, tmp_path) is None


def test_a_script_pace_that_admits_work_holds_the_five_hour_pace() -> None:
    from pathlib import Path
    from operations.constants import SUBAGENT_LIMIT
    from operations.pacing import FIVE_HOUR, Scripted, Until, with_five_hour
    path = Path("pace.py")
    past, within = usage(90, 80), usage(50, 80)
    held = with_five_hour(Scripted(path, True), past)
    assert held == FIVE_HOUR(past)
    assert isinstance(held, Until) and held.time > past.now
    assert with_five_hour(Scripted(path, True), within) == Until(within.now, SUBAGENT_LIMIT)
    assert with_five_hour(Scripted(path, False), past) == Scripted(path, False)
    assert with_five_hour(Scripted(path, False), within) == Scripted(path, False)
