"""The cache readout the rail shows and the finalize lens sorts on."""

import json
import shutil
import subprocess

import pytest

from .conftest import ROOT

ITEM_JS = ROOT / "tools" / "console" / "ui" / "item.js"
# The module reaches the page for two things the readout never uses: the
# duration format it imports, and the gesture that unlocks the chime.
STUB = ('import { fmtDur } from "/ui/prose.js";',
        "const fmtDur = s => String(s);\nglobalThis.addEventListener = () => {};")
CHECK = """
const now = Date.now();
const session = la => ({id:"a", phase:"finalize", state:"needs-review",
                        sessions:{finalize:"fs"}, lastActive:{finalize:la}});
console.log(JSON.stringify({
  blank: cacheInfo(session(null)),
  expired: cacheInfo(session(now - (TTL_MIN + 5) * 60000)),
  warm: cacheInfo(session(now - 60000)),
  unopened: cacheInfo({id:"a", phase:"finalize", state:"needs-review",
                       sessions:{}, lastActive:{}}),
}));
"""


def readouts() -> dict:
    src = ITEM_JS.read_text().replace(*STUB)
    out = subprocess.run(["node", "--input-type=module", "-e", src + CHECK],
                         capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


@pytest.mark.skipif(shutil.which("node") is None, reason="node runs the ui module")
def test_a_session_with_no_stamp_reads_as_cold():
    r = readouts()
    assert r["blank"] == r["expired"]
    assert r["blank"]["cls"] == "cold"
    assert r["warm"]["cls"] == "ok"
    # a stage that has opened no session has no cache to lose, and leads
    assert r["unopened"] == {"cls": "none", "txt": "—", "sort": -1}
