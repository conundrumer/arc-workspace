"""An operator whose calls of `next` find nothing ready for
`WAIT_SECONDS_IDLE` waits with its turn ended while an agent of its own is
pending, and otherwise gives its final reply for a wait. Its launcher then
waits in the background and launches a fresh operator, and launches one at
once after an operator's end with no final reply, unless two quick ends
come in a row."""

from dataclasses import replace
from pathlib import Path

from tests.test_operator_take_up import EARLY, LATE, LAUNCHER, operator_state

OTHER = "a0000000000000005"
NOW = 1000.0


def next_call(time: float, result: str | None, operator: str = EARLY):
    from operations.command_words import next_command
    from operations.state import Call, Tool
    return Call(operator, time, Tool.BASH, {"command": next_command(operator)}, result, False)


def pending(operator: str, agent_id: str = "a0000000000000007"):
    from operations.roles import Role
    from operations.state import Agent, Running, Waits
    return Agent(agent_id, operator, Role.CODE_EDITOR, "1-1", "brief", 0.0, 0.0, Running(Waits.AT_WORK),
                 (), True)


def idle_state(tmp_path: Path, first_poll: float, mine: bool):
    """The state of `EARLY` at `NOW`, whose calls of `next` from
    `first_poll` on printed that nothing is ready, while an agent of
    `EARLY`, where `mine`, or else of another operator, is pending."""
    from operations.printed_forms import POLL_AGAIN
    calls = (next_call(first_poll - 300.0, "call Agent"), next_call(first_poll, POLL_AGAIN),
             next_call(first_poll + 150.0, POLL_AGAIN), next_call(NOW, None))
    from operations.pacing import Until
    s = operator_state(tmp_path, EARLY, (EARLY,), calls)
    return replace(s, now=NOW, computed=replace(s.computed, pace=Until(0.0)),
                   transcripts=replace(s.transcripts, agents=(pending(EARLY if mine else OTHER),)))


def step_of(s, waiting: bool = False):
    from operations.monitor import MonitorState
    from operations.plan import next_step
    return next_step(s, MonitorState((), frozenset(), (), ()), waiting)


def test_an_operator_with_nothing_ready_for_the_idle_time_and_no_agent_pending_gives_its_final_reply_for_a_wait(
        tmp_path: Path) -> None:
    from operations.final_reply import final_text, for_wait, hands_over
    from operations.steps import Send
    step = step_of(idle_state(tmp_path, NOW - 300.0, mine=False))
    assert isinstance(step, Send)
    text = final_text(step.message) or ""
    assert for_wait(text) and hands_over(text)


def test_an_operator_with_nothing_ready_for_less_than_the_idle_time_runs_the_command_again(
        tmp_path: Path) -> None:
    from operations.steps import Poll
    assert isinstance(step_of(idle_state(tmp_path, NOW - 299.0, mine=False)), Poll)


def test_an_operator_whose_agent_is_pending_waits_with_its_turn_ended(tmp_path: Path) -> None:
    from operations.steps import Wait
    s = idle_state(tmp_path, NOW - 300.0, mine=True)
    assert step_of(s) == Wait(EARLY, call=True)
    assert step_of(s, waiting=True) == Wait(EARLY, call=False)


def test_an_operator_whose_own_wait_runs_ends_its_turn_with_no_final_reply(
        tmp_path: Path) -> None:
    from operations.steps import Wait
    s = idle_state(tmp_path, NOW - 300.0, mine=False)
    assert step_of(s, waiting=True) == Wait(EARLY, call=False)


def test_the_result_of_a_wait_continues_the_calls_that_found_nothing_ready(
        tmp_path: Path) -> None:
    from operations.plan import idle_since
    from operations.printing import printed
    from operations.printed_forms import POLL_AGAIN
    from operations.steps import Wait
    calls = [next_call(100.0, POLL_AGAIN), next_call(400.0, printed(Wait(EARLY), EARLY, tmp_path)),
             next_call(900.0, None)]
    assert idle_since(calls, EARLY) == 100.0
    assert idle_since([next_call(50.0, "call Agent"), *calls[1:]], EARLY) == 400.0


def test_the_printed_wait_is_a_background_call_of_wait_then_the_end_of_the_turn(
        tmp_path: Path) -> None:
    from operations.printing import printed, printed_bash, printed_end_turn, wait_command
    from operations.steps import Wait
    text = printed(Wait(EARLY), EARLY, tmp_path)
    assert printed_bash(text) == wait_command(EARLY)
    assert printed_end_turn(text)
    alone = printed(Wait(EARLY, call=False), EARLY, tmp_path)
    assert printed_bash(alone) is None and printed_end_turn(alone)


def run(agent_id: str, launched: float, final: str | None, ended: float, pending: bool = False):
    from operations.relay import Run
    return Run(agent_id, launched, pending, final, ended)


def relay(runs, calls=(), lines=(), waiting: bool = False):
    from operations.relay import Relay
    from operations.state import Message
    brief = Message(LAUNCHER, 0.0, None, "brief")
    return Relay(LAUNCHER, (brief, *lines), tuple(runs), tuple(calls), False, waiting)


def wait_call(time: float):
    from operations.printing import wait_command
    from operations.state import Call, Tool
    return Call(LAUNCHER, time, Tool.BASH, {"command": wait_command(LAUNCHER)}, "running", False)


def for_wait_reply() -> str:
    from operations.final_reply import FOR_WAIT
    return FOR_WAIT + "\n- line"


def test_after_a_final_reply_for_a_wait_the_launcher_waits_with_its_turn_ended() -> None:
    from operations.relay import next_step
    from operations.steps import Wait
    ended = [run(EARLY, 10.0, for_wait_reply(), 400.0)]
    assert next_step(relay(ended)) == Wait(LAUNCHER, call=True)
    assert next_step(relay(ended, [wait_call(410.0)], waiting=True)) == Wait(LAUNCHER, call=False)


def test_the_launcher_launches_a_fresh_operator_once_its_wait_completed() -> None:
    from operations.relay import next_step
    from operations.roles import Role
    from operations.steps import Launch
    step = next_step(relay([run(EARLY, 10.0, for_wait_reply(), 400.0)], [wait_call(410.0)]))
    assert isinstance(step, Launch) and step.role is Role.OPERATOR


def test_a_line_of_the_coordinator_launches_a_fresh_operator_during_the_wait() -> None:
    from operations.relay import next_step
    from operations.state import Message
    from operations.steps import Launch
    step = next_step(relay([run(EARLY, 10.0, for_wait_reply(), 400.0)], [wait_call(410.0)],
                           [Message(LAUNCHER, 500.0, None, "Op run: x.py")], waiting=True))
    assert isinstance(step, Launch) and step.brief == "Op run: x.py"


def test_an_end_with_no_final_reply_launches_a_fresh_operator_and_tells_the_coordinator_nothing() -> None:
    from operations.relay import next_step
    from operations.steps import Launch
    step = next_step(relay([run(EARLY, 10.0, None, 100.0)]))
    assert isinstance(step, Launch)
    step = next_step(relay([run(EARLY, 10.0, None, 1000.0), run(LATE, 1100.0, None, 1200.0)]))
    assert isinstance(step, Launch)


def test_two_quick_ends_in_a_row_with_no_final_reply_reach_the_coordinator() -> None:
    from operations.constants import COORDINATOR
    from operations.relay import NO_REPLY, next_step
    from operations.state import Call, Tool
    from operations.steps import Reply, Send
    runs = [run(EARLY, 10.0, None, 100.0), run(LATE, 110.0, None, 200.0)]
    step = next_step(relay(runs))
    assert isinstance(step, Send) and step.to == COORDINATOR
    assert step.message == NO_REPLY.format(operator=LATE)
    sent = Call(LAUNCHER, 210.0, Tool.SEND_MESSAGE,
                {"to": COORDINATOR, "message": step.message}, "sent", False)
    assert next_step(relay(runs, [sent])) == Reply(COORDINATOR)


def test_the_fresh_operator_releases_the_change_of_an_operator_that_ended_with_no_final_reply(
        tmp_path: Path) -> None:
    """The ended operator `EARLY` made no final send. While its work is
    open it holds its change live; once the notification of its end
    closes its work, it leaves `open_holders` (`profile_runs.py --help
    running`), the fresh operator `LATE` releases its change, and, from
    the state after that release, takes it."""
    from operations import change_take, taking
    from operations.steps import Bash
    from tests.test_ticket_stall import FILED, state
    taken = f"{FILED} assigned [operator {EARLY}]: taking: budget 1 subscription dollars, 100 s\n"
    s = state(tmp_path, {"assigned/9-1_change_x_ticket-analyst.md": taken})
    s = replace(s, me=LATE, operators=(EARLY, LATE), parents={EARLY: LAUNCHER, LATE: LAUNCHER},
                session_holders=frozenset({EARLY, LATE}),
                transcripts=replace(s.transcripts, calls=(next_call(100.0, "call Agent"),)))
    running = replace(s, open_holders=frozenset({EARLY, LATE}))
    assert taking.release(running) is None
    step = taking.release(replace(s, open_holders=frozenset({LATE})))
    assert isinstance(step, Bash) and "9-1" in step.command
    released = (taken + f"{FILED} released [operator {LATE}]: "
                + taking.RELEASED.format(holder=EARLY) + "\n")
    after = state(tmp_path / "after", {"released/9-1_change_x_ticket-analyst.md": released},
                  budgets=("9-1",))
    after = replace(after, me=LATE, operators=(EARLY, LATE),
                    parents={EARLY: LAUNCHER, LATE: LAUNCHER},
                    open_holders=frozenset({LATE}), session_holders=frozenset({EARLY, LATE}))
    took = change_take.take(after)
    assert isinstance(took, Bash) and "9-1" in took.command and LATE in took.command
