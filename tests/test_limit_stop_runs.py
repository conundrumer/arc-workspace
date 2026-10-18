"""An agent the usage limit stopped counts as stopped (`TranscriptsRead.limited`)
only until its own transcript gains an entry after the stop: an agent another
agent resumed is resumed by the operator a second time where it does not, and
its report goes to the operator, with no failure."""

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from handbook.paths import scripts_importable
from tests.conftest import script

scripts_importable()
script("operator_transcript")
operator_transcript = sys.modules["operator_transcript"]
state_reads = sys.modules["state_reads"]

STOP = 1_760_000_000.0


def entry(t: float) -> str:
    stamp = datetime.fromtimestamp(t, UTC)
    return json.dumps({"type": "user", "message": {"content": "x"},
                       "timestamp": stamp.isoformat().replace("+00:00", "Z")}) + "\n"


def test_an_agent_resumed_after_its_stop_has_run_since_and_one_not_resumed_has_not(
        tmp_path: Path) -> None:
    path = tmp_path / "run.jsonl"
    path.write_text(entry(STOP - 0.05))
    state_reads.new_state()
    assert not operator_transcript.ran_since(path, STOP)
    with path.open("a") as fh:
        fh.write(entry(STOP + 60))
    state_reads.new_state()
    assert operator_transcript.ran_since(path, STOP)
