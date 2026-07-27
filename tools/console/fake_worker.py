#!/usr/bin/env python3
"""Simulates a claude -p worker's stream-json output (CONSOLE_FAKE=1)."""

import json
import sys
import time
import uuid

tid = sys.argv[1]
msg = sys.argv[2] if len(sys.argv) > 2 else ""
sid = str(uuid.uuid5(uuid.NAMESPACE_URL, "fake-worker/" + tid))


def emit(obj):
    print(json.dumps(obj), flush=True)


def tool(name, **inp):
    emit({"type": "assistant",
          "message": {"content": [{"type": "tool_use", "name": name, "input": inp}]}})


emit({"type": "system", "subtype": "init", "session_id": sid})
time.sleep(1)

if msg.strip().lower() == "cleanup":
    tool("Edit", file_path=f"programs/solvers/{tid}.dl")
    time.sleep(1)
    tool("Bash", command=f"uv run python scripts/run_dl.py {tid}")
    time.sleep(1)
    text = "(fake) Cleanup done. Simplify: none. Prune: two cuts. All pairs still pass."
else:
    tool("Bash", command=f"cat data/tasks/{tid}.json")
    time.sleep(1.5)
    tool("Read", file_path=f"../arc-synth-bun/programs/solvers/{tid}.ts")
    time.sleep(1)
    tool("Write", file_path=f"programs/solvers/{tid}.dl")
    time.sleep(1)
    tool("Bash", command=f"uv run python scripts/run_dl.py {tid}")
    time.sleep(1.5)
    text = (f"(fake) Solver for `{tid}` passes all pairs.\n\n"
            "1. Model: `divide` splits the grid; per-tile recolor by rank.\n"
            "2. Awkward: the rank join reads roundabout — see `header_color`.\n"
            "3. Lib: `rank_of` is solver-local and worked in context; "
            "candidate for staging.")

emit({"type": "assistant", "message": {"content": [{"type": "text", "text": text}]}})
emit({"type": "result", "subtype": "success", "result": text,
      "total_cost_usd": 0.12, "duration_ms": 6000, "session_id": sid})
