"""Case bounds must refuse a span that would record a false loss."""

import json
from pathlib import Path

import pytest

from handbook.paths import scripts_importable
from ticketing.subscription import CLAUDE_LIST_TO_SUBSCRIPTION
from tests.conftest import script


@pytest.mark.parametrize(("start", "end", "refused"), [
    ("2026-10-18T21:59:59Z", "2026-10-18T22:00:01Z", True),
    ("2026-10-18T22:00:00Z", "2026-10-18T22:00:11Z", True),
    ("2026-10-18T22:00:00Z", "2026-10-18T22:00:10Z", False),
])
def test_case_span(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                   start: str, end: str, refused: bool) -> None:
    scripts_importable()
    watch = script("ticket_watch")
    path = tmp_path / "run.jsonl"
    path.write_text("\n".join(json.dumps(entry) for entry in [
        {"type": "user", "timestamp": "2026-10-18T22:00:00Z"},
        {"type": "assistant", "timestamp": "2026-10-18T22:00:01Z",
         "message": {"id": "request", "model": "claude-haiku-4-5-20251001",
                     "usage": {"input_tokens": 1000, "output_tokens": 100}}},
    ]) + "\n")
    monkeypatch.setattr(watch.time, "time", lambda: watch.stamp_time("2026-10-18T22:00:10Z"))
    undecided: list[str] = []
    if refused:
        with pytest.raises(watch.Refused):
            watch.case_loss(str(path), start, end, undecided)
    else:
        case = watch.case_loss(str(path), start, end, undecided)
        assert case.dollars == pytest.approx(0.0015 * CLAUDE_LIST_TO_SUBSCRIPTION)
        assert case.seconds == 10
    assert not undecided
