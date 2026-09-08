#!/usr/bin/env python3
"""Rate-limit windows, and the tokens spent inside them.

Utilization is only ever available as a live snapshot — nothing serves its
history — so the only way to learn how usage maps onto a window is to record
the two together as they move. `record` writes one sample per call, pairing
every window's utilization with the tokens spent inside it.

Tokens are summed across every transcript in the console's Claude home, not
console workers alone, because the windows count the whole account. Transcript
reading is incremental: each file is read from where the last pass stopped.

server.py samples on its usage poll; calibrate.py reads the same transcripts
for a one-shot measurement.
"""

import json
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path

from solver_console import config

RETAIN = 8 * 86400  # a little past the longest window
TIERS = ("in", "out", "read", "w5m", "w1h")


def epoch(iso: str) -> float:
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()


def parse(line: str) -> tuple[float, str, str, dict] | None:
    """One transcript line as (when, model, id, usage), or None if it isn't one."""
    if '"assistant"' not in line:
        return None
    try:
        ev = json.loads(line)
    except ValueError:
        return None
    if ev.get("type") != "assistant":
        return None
    msg = ev.get("message") or {}
    mid, usage, model = msg.get("id"), msg.get("usage"), msg.get("model")
    if not (mid and usage and model):
        return None
    try:
        return epoch(ev["timestamp"]), model, mid, usage
    except (KeyError, ValueError):
        return None


def tally(usage: dict) -> dict[str, int]:
    """Token counts by billing tier. Cache writes split by TTL where reported."""
    created = usage.get("cache_creation") or {}
    write_1h = created.get("ephemeral_1h_input_tokens", 0)
    write_5m = created.get("ephemeral_5m_input_tokens", 0)
    if not (write_1h or write_5m):
        write_5m = usage.get("cache_creation_input_tokens", 0)
    return {
        "in": usage.get("input_tokens", 0),
        "out": usage.get("output_tokens", 0),
        "read": usage.get("cache_read_input_tokens", 0),
        "w5m": write_5m,
        "w1h": write_1h,
    }


# The usage endpoint rate-limits a token that asks too often, and keeps
# refusing while the asking goes on. A refusal earns a pause that doubles up
# to BACKOFF_MAX seconds; a reading clears it.
BACKOFF_MAX = 600
NEXT_TRY = 0.0
BACKOFF = 0.0


def fetch(force: bool = False) -> None:
    """Refresh the usage cache of the console's home. The script reads the
    account that home is logged into. A fetch that fails leaves the last
    reading in place."""
    global NEXT_TRY, BACKOFF
    if not config.USAGE_FETCH.exists() or time.time() < NEXT_TRY:
        return
    try:
        out = subprocess.run(["bash", str(config.USAGE_FETCH)] + (["--force"] if force else []),
                             env={**os.environ, "CLAUDE_CONFIG_DIR": str(config.CLAUDE_HOME)},
                             capture_output=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return
    if out.returncode == 0:
        BACKOFF = 0.0
        return
    BACKOFF = min(max(BACKOFF * 2, 2 * config.USAGE_POLL), BACKOFF_MAX)
    NEXT_TRY = time.time() + BACKOFF


def scan():
    """Every assistant message across all transcripts, deduplicated by id."""
    seen = set()
    for f in config.PROJECTS.rglob("*.jsonl"):
        try:
            lines = f.read_text(errors="replace").splitlines()
        except OSError:
            continue
        for line in lines:
            row = parse(line)
            if row and row[2] not in seen:
                seen.add(row[2])
                yield row


def windows(force: bool = False) -> dict[str, tuple[float, float, int, str | None]]:
    """Each window as (start, end, percent used, model scope), keyed by label.

    Labels match the ones the console header shows, so a constant measured
    here lands under the key server.py reads it by. `force` refetches rather
    than accepting the cache's own staleness window.
    """
    fetch(force)
    try:
        raw = json.loads(config.USAGE_API.read_text())
    except (OSError, ValueError):
        return {}
    out = {}
    for lim in (raw.get("data") or {}).get("limits") or []:
        pct, kind = lim.get("percent"), lim.get("kind")
        scope = (((lim.get("scope") or {}).get("model")) or {}).get("display_name")
        if pct is None or not lim.get("resets_at"):
            continue
        if kind == "session":
            label, span = "5h", 5 * 3600
        elif kind == "weekly_all":
            label, span = "wk", 7 * 86400
        elif scope:
            label = "fbl" if scope.lower().startswith("fable") else scope[:3].lower()
            span = 7 * 86400
        else:
            continue
        try:
            end = epoch(lim["resets_at"])
        except ValueError:
            continue
        out[label] = (end - span, end, pct, scope)
    return out


def in_scope(model: str, scope: str | None) -> bool:
    """Whether a model's usage counts against a scoped window."""
    return not scope or model.startswith("claude-" + scope.lower())


class Sampler:
    """Keeps a rolling index of recent transcript rows and writes samples."""

    def __init__(self) -> None:
        self.offsets: dict[Path, int] = {}
        self.rows: list[tuple[float, str, str, dict]] = []
        self.ids: set[str] = set()
        self.last: dict | None = None

    def refresh(self) -> None:
        """Read whatever the transcripts have gained since the last pass."""
        for f in config.PROJECTS.rglob("*.jsonl"):
            try:
                size = f.stat().st_size
            except OSError:
                continue
            start = self.offsets.get(f, 0)
            if size <= start:
                self.offsets[f] = size  # unchanged, or rewritten shorter
                continue
            try:
                with f.open("rb") as fh:
                    fh.seek(start)
                    chunk = fh.read()
            except OSError:
                continue
            # Leave a trailing partial line for the next pass to pick up whole.
            cut = chunk.rfind(b"\n")
            if cut < 0:
                continue
            self.offsets[f] = start + cut + 1
            for line in chunk[:cut].decode("utf-8", "replace").splitlines():
                row = parse(line)
                if row and row[2] not in self.ids:
                    self.ids.add(row[2])
                    self.rows.append(row)
        cutoff = time.time() - RETAIN
        if any(when < cutoff for when, *_ in self.rows):
            self.rows = [r for r in self.rows if r[0] >= cutoff]
            self.ids = {mid for _, _, mid, _ in self.rows}

    def sample(self) -> dict | None:
        """Current utilization of every window, with the tokens spent in it."""
        wins = windows()
        if not wins:
            return None
        self.refresh()
        out = {}
        for label, (start, end, pct, scope) in wins.items():
            models: dict[str, dict[str, int]] = {}
            for when, model, _, usage in self.rows:
                if not (start <= when < end) or not in_scope(model, scope):
                    continue
                totals = models.setdefault(model, dict.fromkeys(TIERS, 0))
                for tier, n in tally(usage).items():
                    totals[tier] += n
            out[label] = {"pct": pct, "start": int(start), "end": int(end),
                          "scope": scope, "models": models}
        return out

    def record(self, path: Path) -> dict | None:
        """Append a sample, unless nothing has moved since the last one."""
        s = self.sample()
        if s is None or s == self.last:
            return None
        self.last = s
        try:
            with path.open("a") as fh:
                fh.write(json.dumps({"t": int(time.time()), "windows": s}) + "\n")
        except OSError:
            return None
        return s
