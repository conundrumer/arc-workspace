"""The key of a step stays the same across occasions, and the journal's entry key tells them apart."""

from operations.roles import Role
from operations.steps import Bash, Launch, entry_key, input_time, key


def launch(occasion: str, version: float | None = None) -> Launch:
    return Launch(Role.DOC_EDITOR, "9-1", "brief", occasion=occasion, version=version)


def test_the_key_leaves_out_the_occasion_and_the_version() -> None:
    assert key(launch("1.0")) == key(launch("2.0", 5.0))


def test_the_entry_key_tells_occasions_versions_and_attempts_apart() -> None:
    from dataclasses import replace
    base = launch("1.0")
    keys = {entry_key(base), entry_key(launch("2.0")), entry_key(launch("1.0", 5.0)),
            entry_key(replace(base, attempt=1))}
    assert len(keys) == 4


def test_a_bash_step_keeps_its_key_across_occasions() -> None:
    first = Bash("cmd", "9-1 open", occasion="1.0")
    later = Bash("cmd", "9-1 open", occasion="2.0")
    assert key(first) == key(later) and entry_key(first) != entry_key(later)


def test_the_input_time_is_the_version_else_an_occasion_that_is_a_time() -> None:
    assert input_time(launch("1.5", 9.0)) == 9.0
    assert input_time(launch("1.5")) == 1.5
    assert input_time(launch("abc def")) is None


def test_a_take_and_a_release_each_move_the_occasion_of_the_next_one(tmp_path) -> None:
    from dataclasses import replace
    from operations.state import LogLine
    from operations.taking import status_since
    from ticketing.vocabulary import Status
    from tests.test_unreported_agents import ticket as filed
    t = filed(tmp_path, "assigned", "9-1_change_x_ticket-analyst.md",
              "---\nkind: change\neditors: code-editor\n---\n# x: y\n\n## Log\n"
              "2026-10-17T02:14:06Z draft [ticket-analyst]: filed\n")

    def line(time: float, status: Status) -> LogLine:
        return LogLine(time, status, "operator", None, "n", False, None, False, None, None, None)

    moves = [(10.0, Status.ASSIGNED), (20.0, Status.RELEASED), (30.0, Status.ASSIGNED),
             (40.0, Status.RELEASED)]
    steps: list[Bash] = []
    for i, (_, status) in enumerate(moves):
        seen = replace(t, status=status, log=tuple(line(*m) for m in moves[:i + 1]))
        steps.append(Bash("cmd", "take", occasion=str(status_since(seen))))
    assert [s.occasion for s in steps] == ["10.0", "20.0", "30.0", "40.0"]
    assert len({entry_key(s) for s in steps}) == 4
