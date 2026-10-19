"""The `repeated` reading of the monitor gives a run of calls with the same
command and the same result, and gives none for a run of polls whose
output asks for the command again: a wrong reading sends an agent an alert
that asks the opposite of its command's output, or sends none."""

from handbook.paths import scripts_importable
from operations.printed_forms import POLL_AGAIN
from tests.conftest import script

COMMAND = "uv run python scripts/operate.py review a8b69083a4e72f3a6"


def runs(result: str) -> list[float]:
    scripts_importable()
    calls = [(f"c{i}", COMMAND, float(i)) for i in range(3)]
    return script("run_reads").repeated_runs(calls, {c: result for c, _, _ in calls}, 3)


def test_poll_results_give_no_run():
    assert runs(f"held 3m\n{POLL_AGAIN}\n") == []


def test_same_other_result_gives_a_run():
    assert runs("ok\n") == [2.0]
