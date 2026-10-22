"""Snapshot reuse must preserve the operator's next step after transcript edits."""

import json
import pickle
import subprocess
import sys
from pathlib import Path


READINESS = r'''
import pickle
import sys
from dataclasses import replace
from pathlib import Path
from handbook.paths import scripts_importable
scripts_importable()
import kept_reads
from transcript_snapshots import read_snapshot
from operator_transcript import read_operator
from operations.monitor import MonitorState
from operations.plan import ready_step
from tests.test_own_work import state

mode, transcript, store = sys.argv[1:]
path = Path(transcript)
kept_reads.open_store(Path(store))
if mode == "prime":
    read_snapshot(path).holding(frozenset({"Op ", "Agent", "SendMessage"}))
    kept_reads.flush()
else:
    read = read_operator("op", path, path.parent, [], {})
    base = state(path.parent, messages=read.messages)
    fixed = replace(base, transcripts=replace(base.transcripts, calls=read.calls),
                    listing=frozenset())
    step = ready_step(fixed, MonitorState((), frozenset(), (), ()))
    print(pickle.dumps(step).hex())
'''


def test_snapshot_readiness_after_append_and_rewrite(tmp_path: Path) -> None:
    path = tmp_path / "operator.jsonl"
    path.with_suffix(".meta.json").write_text(json.dumps({"agentType": "operator"}))
    store = tmp_path / "snapshots.sqlite"

    def entry(text: str) -> str:
        return json.dumps({"type": "user", "timestamp": "2026-10-21T00:00:00Z",
                           "origin": {"kind": "coordinator"},
                           "message": {"content": text}}) + "\n"

    def run(mode: str, database: Path) -> object:
        result = subprocess.run([sys.executable, "-c", READINESS, mode, str(path), str(database)],
                                env={}, capture_output=True, text=True, check=True, timeout=30)
        return pickle.loads(bytes.fromhex(result.stdout.strip())) if mode == "read" else None

    def compare(name: str) -> object:
        actual = run("read", store)
        assert actual == run("read", tmp_path / f"empty-{name}.sqlite")
        return actual

    path.write_text(entry("Op scope: own."))
    run("prime", store)
    unchanged = compare("unchanged")
    with path.open("a") as fh:
        fh.write(entry("Op unknown."))
    appended = compare("append")
    from operations.steps import Send
    assert isinstance(appended, Send)
    assert appended != unchanged
    run("prime", store)
    path.write_text(entry("Op scope: own.") + entry("Op scope: own."))
    assert compare("rewrite") == unchanged
