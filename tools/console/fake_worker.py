#!/usr/bin/env python3
"""Simulates a persistent claude stream-json worker (CONSOLE_FAKE=1)."""

import json
import os
import select
import sys
import time
import uuid
from collections import deque

tid = sys.argv[1]
phase = sys.argv[2] if len(sys.argv) > 2 else "refine"
sid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"fake-worker/{tid}/{phase}"))
pending = deque()
turn = 0


reqno = 0
cached = 0


def emit(obj):
    print(json.dumps(obj), flush=True)


def usage_for():
    """One request's usage; the stream repeats it on the request's block events."""
    global reqno, cached
    reqno += 1
    delta = 27000 if cached == 0 else 250
    usage = {"input_tokens": 10, "output_tokens": 100,
             "cache_read_input_tokens": cached,
             "cache_creation_input_tokens": delta,
             "cache_creation": {"ephemeral_1h_input_tokens": delta}}
    cached += delta
    return usage


def tool(name, **inp):
    usage = usage_for()
    emit({"type": "assistant",
          "message": {"id": f"msg-{reqno}", "usage": usage,
                      "content": [{"type": "tool_use", "name": name, "input": inp}]}})


def result(text, reason="completed"):
    if reason == "completed":
        usage = usage_for()
        emit({"type": "assistant", "message": {"id": f"msg-{reqno}", "usage": usage,
              "content": [{"type": "text", "text": text}]}})
        emit({"type": "result", "subtype": "success", "terminal_reason": reason,
              "result": text, "is_error": False, "total_cost_usd": round(turn * .12, 2),
              "duration_ms": 6000, "session_id": sid,
              # the CLI's result event carries only the final request
              "usage": {"iterations": [usage]},
              "modelUsage": {"claude-fable-5": {"inputTokens": turn * 10,
                  "outputTokens": turn * 100,
                  "cacheReadInputTokens": usage["cache_read_input_tokens"],
                  "cacheCreationInputTokens": usage["cache_creation_input_tokens"],
                  "costUSD": turn * .12,
                  "contextWindow": 200000, "canonicalModel": "claude-fable-5"}}})
    else:
        emit({"type": "result", "subtype": "error_during_execution",
              "terminal_reason": reason, "result": "", "is_error": True,
              "usage": {"input_tokens": 0, "output_tokens": 0},
              "total_cost_usd": 0, "duration_ms": 0, "session_id": sid})


def control(line):
    try:
        ev = json.loads(line)
    except ValueError:
        return False
    if ev.get("type") != "control_request":
        return False
    request_id = ev.get("request_id")
    emit({"type": "control_response", "response": {"subtype": "success",
          "request_id": request_id, "response": {"still_queued": []}}})
    return ev.get("request", {}).get("subtype") == "interrupt"


def pause(seconds):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        ready, _, _ = select.select([sys.stdin], [], [], min(.05, deadline - time.monotonic()))
        if ready:
            line = sys.stdin.readline()
            if not line:
                return "eof"
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if event.get("type") == "control_request" and control(line):
                return "interrupt"
            if event.get("type") == "user":
                pending.append(event)
    return None


def run_turn(message):
    global turn
    turn += 1
    emit({"type": "system", "subtype": "init", "session_id": sid})
    mode = message.strip().lower()
    if mode == "crash":
        os._exit(17)
    if mode == "stop-reading-stdin":
        while True:
            time.sleep(60)
    if mode == "/compact":
        emit({"type": "system", "subtype": "compact_boundary", "session_id": sid,
              "compact_metadata": {"trigger": "manual", "pre_tokens": 28260,
                  "post_tokens": 1914, "cumulative_dropped_tokens": 26346,
                  "duration_ms": 1200}})
        emit({"type": "result", "subtype": "success", "terminal_reason": "completed",
              "result": "", "is_error": False, "total_cost_usd": 0.12,
              "duration_ms": 1200, "session_id": sid, "usage": {"iterations": []},
              "modelUsage": {"claude-fable-5": {"contextWindow": 200000,
                  "canonicalModel": "claude-fable-5", "costUSD": .12}}})
        return None
    if mode == "runaway":
        # The live stream never carries stop_reason; a runaway shows up as
        # thinking_tokens progress with no tool_use or text between.
        emit({"type": "assistant", "message": {"id": f"msg-runaway-{turn}",
              "usage": usage_for(),
              "content": [{"type": "thinking", "thinking": ""}]}})
        thought = 0
        while True:
            thought += 25000
            emit({"type": "system", "subtype": "thinking_tokens", "session_id": sid,
                  "estimated_tokens": thought, "estimated_tokens_delta": 25000})
            stopped = pause(.2)
            if stopped == "interrupt":
                result("", "aborted_streaming")
                return None
            if stopped == "eof":
                return "eof"
    steps = []
    if mode == "cleanup":
        steps = [("Edit", {"file_path": f"programs/solvers/{tid}.dl"}),
                 ("Bash", {"command": f"uv run python scripts/run_dl.py {tid}"})]
        text = "(fake) Cleanup done. Simplify: none. Prune: two cuts. All pairs still pass."
    elif phase == "create":
        steps = [("Write", {"file_path": f"programs/solvers/{tid}.dl"}),
                 ("Bash", {"command": f"uv run python scripts/run_dl.py {tid}"}),
                 ("Bash", {"command": f"uv run python scripts/run_dl.py audit {tid}"})]
        text = (f"(fake) Handoff report for `{tid}`.\n\n"
                "1. Model claim: `divide` splits the grid; per-tile recolor by rank.\n"
                "2. Discarded: global recolor — breaks train 2 (tile order flips).\n"
                "3. Audit: clean. Judgment call: rank ties broken by position.")
    else:
        steps = [("Read", {"file_path": f"programs/solvers/{tid}.dl"}),
                 ("Edit", {"file_path": f"programs/solvers/{tid}.dl"}),
                 ("Bash", {"command": f"uv run python scripts/run_dl.py {tid}"})]
        text = (f"(fake) Refined `{tid}`; all pairs still pass.\n\n"
                "1. Kept the model; renamed `header_color` for the concept.\n"
                "2. **No fit pass needed.**\n"
                "3. Lib: `rank_of` is solver-local and worked in context; candidate for staging.")
    for name, inp in steps:
        stopped = pause(.35)
        if stopped:
            if stopped == "interrupt":
                result("", "aborted_streaming")
            return stopped
        tool(name, **inp)
    stopped = pause(.35)
    if stopped == "interrupt":
        result("", "aborted_streaming")
        return stopped
    if stopped != "eof":
        result(text)
    return stopped


while True:
    if pending:
        event = pending.popleft()
        raw = json.dumps(event)
    else:
        raw = sys.stdin.readline()
        if not raw:
            break
        try:
            event = json.loads(raw)
        except ValueError:
            continue
    if event.get("type") == "control_request":
        control(raw)
        continue
    if event.get("type") != "user":
        continue
    content = event.get("message", {}).get("content", "")
    if isinstance(content, list):
        content = "".join(x.get("text", "") for x in content if isinstance(x, dict))
    if run_turn(str(content)) == "eof":
        break
