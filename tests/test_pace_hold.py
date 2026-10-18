"""Past the usage pace, a step that starts an agent's run is held and its
procedure gives its next step in its place; within the pace, it stands."""

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
