"""Past the usage pace, a step that starts an agent's run is held and its
procedure gives its next step in its place; within the pace, it stands."""

import math
from dataclasses import replace
from pathlib import Path

from tests.test_ticket_stall import state


def test_past_the_pace_a_launch_is_held_and_the_next_step_stands(tmp_path: Path) -> None:
    from operations import order
    from operations.handled import held_aside
    from operations.pacing import Until
    from operations.roles import Role
    from operations.steps import Bash, Launch
    within = state(tmp_path, {"open/9-1_change_x_ticket-analyst.md": ""})
    past = replace(within, computed=replace(within.computed, pace=Until(within.now + 60)))
    launch = Launch(Role.TICKET_REVIEWER, "9-1", "brief", occasion="1")
    move = Bash("true", "move", occasion="1")

    def procedure(s):
        return move if held_aside(s, launch) else launch

    assert order.placed(within, procedure)[0] == launch
    assert order.placed(past, procedure)[0] == move
    assert order.placed(past, lambda _s: launch)[0] is None
    assert order.pace_held_step(past) is None


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


def test_at_the_cap_a_launch_is_held_and_the_batch_stops(tmp_path: Path) -> None:
    from operations import order
    from operations.handled import held_aside
    from operations.monitor import MonitorState
    from operations.pacing import Until
    from operations.roles import Role
    from operations.steps import Bash, Launch
    base = state(tmp_path, {"open/9-1_change_x_ticket-analyst.md": ""})
    launch = Launch(Role.TICKET_REVIEWER, "9-1", "brief", occasion="1")
    move = Bash("true", "move", occasion="1")

    def procedure(s):
        return move if held_aside(s, launch) else launch

    one = replace(base, computed=replace(base.computed, pace=Until(base.now, 1)))
    assert order.placed(one, procedure)[0] == launch
    assert order.batch(one, MonitorState((), frozenset(), ()), launch) == (launch,)
    running = order.made(one, launch)
    assert order.placed(running, procedure)[0] == move
    uncapped = replace(running, computed=replace(running.computed, pace=Until(base.now)))
    for _ in range(25):
        uncapped = order.made(uncapped, launch)
    assert order.placed(uncapped, procedure)[0] == launch
