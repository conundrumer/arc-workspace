"""`tools/console/retro.py`: the retro window and its mark, read and moved
without a console process."""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RETRO_PY = ROOT / "tools" / "console" / "retro.py"


def run(state_dir, *args):
    proc = subprocess.run([sys.executable, str(RETRO_PY), *args],
                          capture_output=True, text=True,
                          env={**os.environ, "CONSOLE_STATE_DIR": str(state_dir)})
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def report(state_dir, item_id, text):
    p = state_dir / "reports" / item_id / "create.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    return p


def test_the_window_carries_the_callouts_filed_since_the_mark(tmp_path):
    state = tmp_path / "state"
    report(state, "b", "done\n\n## Callouts\n\n- [P2] a doc gap\n")
    window = run(state, "window")
    assert window["retro_mark"] == 0
    assert [(i["id"], i["callouts"]) for i in window["items"]] == \
        [("b", ["[P2] a doc gap"])]


def test_the_mark_the_cli_writes_closes_the_window(tmp_path):
    state = tmp_path / "state"
    report(state, "b", "done\n\n## Callouts\n\n- [P2] a doc gap\n")
    marked = run(state, "mark")
    assert marked["ok"] is True
    assert json.loads((state / "retro.json").read_text()) == {"ts": marked["ts"]}
    assert run(state, "window") == {"retro_mark": marked["ts"], "items": []}
