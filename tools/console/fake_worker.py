#!/usr/bin/env python3
"""Simulates a claude -p worker's stream-json output (CONSOLE_FAKE=1)."""

import json
import sys
import time
import uuid

tid = sys.argv[1]
msg = sys.argv[2] if len(sys.argv) > 2 else ""
phase = sys.argv[3] if len(sys.argv) > 3 else "refine"
sid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"fake-worker/{tid}/{phase}"))


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
elif phase == "create":
    tool("Write", file_path=f"programs/solvers/{tid}.dl")
    time.sleep(1.5)
    tool("Bash", command=f"uv run python scripts/run_dl.py {tid}")
    time.sleep(1)
    tool("Bash", command=f"uv run python scripts/run_dl.py audit {tid}")
    time.sleep(1)
    text = (f"(fake) Handoff report for `{tid}`.\n\n"
            "1. Model claim: `divide` splits the grid; per-tile recolor by rank.\n"
            "2. Discarded: global recolor — breaks train 2 (tile order flips).\n"
            "3. Audit: clean. Judgment call: rank ties broken by position.")
else:
    tool("Read", file_path=f"programs/solvers/{tid}.dl")
    time.sleep(1)
    tool("Edit", file_path=f"programs/solvers/{tid}.dl")
    time.sleep(1)
    tool("Bash", command=f"uv run python scripts/run_dl.py {tid}")
    time.sleep(1.5)
    text = (f"(fake) Refined `{tid}`; all pairs still pass.\n\n"
            "1. Kept the model; renamed `header_color` for the concept.\n"
            "2. **No fit pass needed.**\n"
            "3. Lib: `rank_of` is solver-local and worked in context; "
            "candidate for staging.")

emit({"type": "assistant", "message": {"content": [{"type": "text", "text": text}]}})
emit({"type": "result", "subtype": "success", "result": text,
      "total_cost_usd": 0.12, "duration_ms": 6000, "session_id": sid})
