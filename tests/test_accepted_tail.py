"""The inbox check reads transcripts from near its boundary and keeps only results that count."""

import json
from datetime import datetime, timezone
from pathlib import Path

from handbook.paths import scripts_importable
from tests.conftest import script

scripts_importable()
messages = script("accepted_messages")

BASE = 1_700_000_000.0


def stamp(at: float) -> str:
    return datetime.fromtimestamp(at, timezone.utc).isoformat().replace("+00:00", "Z")


def pair(n: int, at: float, result: dict) -> list[dict]:
    ident = f"toolu_{n}"
    call = {"type": "assistant", "timestamp": stamp(at), "message": {"content": [
        {"type": "tool_use", "id": ident, "name": "SendMessage", "input": {"to": "x"}}]}}
    back = {"type": "user", "timestamp": stamp(at + 1), "toolUseResult": result,
            "message": {"content": [{"type": "tool_result", "tool_use_id": ident}]}}
    return [call, back]


QUEUED = {"success": True, "message": "Message queued for delivery"}
REFUSED = {"success": False, "message": "no"}


def transcript(path: Path, count: int) -> None:
    rows: list[dict] = []
    for n in range(count):
        rows += pair(n, BASE + 100 * n, QUEUED if n % 2 == 0 else REFUSED)
        rows.append({"type": "summary", "pad": "x" * 4000})
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))


def delivered(tail) -> list[str]:
    return [call["id"] for call, *_ in tail.deliveries]


def test_bisected_read_gives_the_deliveries_after_its_bound(tmp_path: Path) -> None:
    path = tmp_path / "t.jsonl"
    transcript(path, 400)
    whole = messages.Tail()
    whole.read(path)
    since = BASE + 100 * 300
    near = messages.Tail()
    near.read(path, since)
    wanted = [i for i in delivered(whole)
              if int(i.removeprefix("toolu_")) * 100 + BASE >= since - messages.PAIRING]
    got = delivered(near)
    assert wanted and got[-len(wanted):] == wanted
    assert got == delivered(whole)[-len(got):] and len(got) < len(delivered(whole))
    assert all(int(i.removeprefix("toolu_")) % 2 == 0 for i in delivered(whole))


def test_earlier_boundary_than_floor_reads_again(tmp_path: Path) -> None:
    path = tmp_path / "t.jsonl"
    transcript(path, 400)
    tail = messages.Tail()
    tail.read(path, BASE + 100 * 300)
    tail.read(path, BASE + 100 * 50)
    whole = messages.Tail()
    whole.read(path, BASE + 100 * 50)
    assert delivered(tail) == delivered(whole)
    assert "toolu_60" in delivered(tail)


def test_result_that_counts_nothing_is_not_kept(tmp_path: Path) -> None:
    path = tmp_path / "t.jsonl"
    transcript(path, 4)
    tail = messages.Tail()
    tail.read(path)
    assert delivered(tail) == ["toolu_0", "toolu_2"]
