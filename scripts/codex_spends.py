"""Measure Codex turns from launcher calls and saved execution evidence."""

from dataclasses import asdict, replace
import json
from pathlib import Path

import codex_reads
import codex_rollout
import read_interrupts
from file_reads import state_stat
from operations.state import CodexSource, CodexSpend
from run_reads import run_entries
from transcripts import chain


def fingerprint(path: Path) -> tuple[str, int | None, int | None]:
    """A source revision in this state, including a missing source.

    Hundreds of old spends watch the same transcript directories. Share
    their stats with the other state reads instead of statting each again.
    """
    text = str(path)
    stat = state_stat(text)
    return (text, None, None) if stat is None else (text, stat.mtime_ns, stat.size)


def legacy_turn_records(records: list[dict], home: Path,
                        inputs: set[Path]) -> list[dict]:
    """Recover legacy call boundaries only when accepted record order is exact.
    A partial or unmatched accepted history cannot establish that correspondence.
    """
    recovered: list[dict] = []
    for thread in sorted({r["thread"] for r in records if isinstance(r.get("thread"), str)}):
        read_interrupts.checkpoint()
        accepted = []
        for record in records:
            read_interrupts.checkpoint()
            if record.get("thread") != thread or "turn" in record:
                continue
            try:
                events = [json.loads(line) for line in record["output"].splitlines()]
            except (KeyError, ValueError):
                continue
            if any(e.get("type") in ("turn.completed", "turn.failed") for e in events):
                accepted.append(record)
        if not accepted:
            continue
        try:
            inputs.add(codex_rollout.rollout_path(thread, home))
            turns = codex_rollout.turns(thread, home)
        except (OSError, ValueError, KeyError):
            continue
        if len(accepted) != len(turns):
            continue
        for record, turn in zip(accepted, turns):
            read_interrupts.checkpoint()
            recovered.append({**record, "turn": turn.turn,
                "usage": None if turn.usage is None else asdict(turn.usage),
                "running": turn.ended is None, "started": turn.started,
                "ended": turn.ended})
    return recovered


def watch_rollouts(home: Path, inputs: set[Path]) -> None:
    """Watch directory revisions when a rollout can arrive later."""
    sessions = home / ".codex" / "sessions"
    inputs.add(sessions)
    if sessions.exists():
        inputs.update(p for p in sessions.rglob("*") if p.is_dir())


def recovery_turns(scratch: Path, records: list[dict], home: Path,
                   inputs: set[Path]) -> tuple[str, list[codex_rollout.Turn]]:
    """Read the saved thread only when all recorded thread identities agree."""
    thread = (scratch / "codex-session").read_text().strip()
    if any(r.get("thread") != thread for r in records):
        raise ValueError("session and record thread identities conflict")
    path = codex_rollout.rollout_path(thread, home)
    inputs.add(path)
    return thread, codex_rollout.read_turns(path)


def codex_spend(owner: dict[Path, str], before: float | None = None,
                home: Path | None = None) -> CodexSpend:
    """Count accepted turns once across the change's launcher calls.
    Missing or ambiguous boundaries remain explicit source components.
    """
    home = home or Path.home()
    sources: list[CodexSource] = []
    inputs: set[Path] = {p for path in owner for p in chain(path)}
    launches: dict[Path, list[codex_reads.Call]] = {}
    for path in owner:
        read_interrupts.checkpoint()
        try:
            gaps: list[str] = []
            for call in codex_reads.calls(list(run_entries(path)), gaps):
                read_interrupts.checkpoint()
                if before is None or call.started is None or call.started <= before:
                    launches.setdefault(call.scratch, []).append(replace(call, transcript=path))
            sources.extend(CodexSource(str(path), owner[path], None, None, None, gap)
                           for gap in gaps)
        except (OSError, ValueError, KeyError, IndexError) as exc:
            sources.append(CodexSource(str(path), owner[path], None, None, None,
                                       "launcher evidence unreadable: " + str(exc)))
    seen: dict[tuple[str, str], CodexSource] = {}
    for scratch, calls in launches.items():
        read_interrupts.checkpoint()
        calls.sort(key=lambda c: c.started if c.started is not None else float("inf"))
        record_path = scratch / "codex-events.jsonl"
        inputs.update((record_path, scratch / "codex-session"))
        record_error = None
        try:
            records = codex_rollout.rows(record_path)
        except FileNotFoundError:
            records = []
        except (OSError, ValueError) as exc:
            records = []
            record_error = "events file unreadable: " + str(exc)
        fallback: tuple[str, list[codex_rollout.Turn]] | str | None = None
        recovered = legacy_turn_records(records, home, inputs)
        for index, call in enumerate(calls):
            read_interrupts.checkpoint()
            source = f"{call.transcript}:{call.call_id}"
            next_call = calls[index + 1].started if index + 1 < len(calls) else None
            limits = [t for t in (next_call, before) if t is not None]
            next_start = min(limits) if limits else None
            legacy_limits = [t for t in (next_start, call.until) if t is not None]
            legacy_end = min(legacy_limits) if legacy_limits else None
            timed = [r for batch, limit in ((records, next_start), (recovered, legacy_end))
                     for r in batch if isinstance(r.get("started"), (int, float))
                     and call.started is not None and r["started"] >= call.started
                     and (limit is None or r["started"] < limit)]
            from_rollout = False
            if len(timed) == 1:
                record = timed[0]
            elif len(records) == len(calls) and not any("started" in r for r in records):
                record = records[index]
            else:
                failure = record_error
                if failure is None and (len(timed) > 1 or
                        (records and not any("started" in r for r in records))):
                    failure = "existing turn records are ambiguous"
                if failure is None and (call.started is None or legacy_end is None):
                    failure = "recovery interval boundary unavailable"
                if failure is None:
                    if fallback is None:
                        try:
                            fallback = recovery_turns(scratch, records, home, inputs)
                        except (OSError, ValueError, KeyError, TypeError) as exc:
                            fallback = "rollout recovery unavailable: " + str(exc)
                            watch_rollouts(home, inputs)
                    if isinstance(fallback, str):
                        failure = fallback
                    else:
                        thread, turns = fallback
                        assert call.started is not None and legacy_end is not None
                        evidence = codex_rollout.select_turn(
                            turns, call.started, legacy_end,
                            include_end=legacy_end != next_call)
                        if evidence is None:
                            failure = "recovery interval has no unique accepted turn"
                        else:
                            from_rollout = True
                            record = {"thread": thread, "turn": evidence.turn,
                                "usage": None if evidence.usage is None else asdict(evidence.usage),
                                "running": evidence.ended is None,
                                "usage_reason": codex_rollout.usage_reason(evidence.usage, evidence.turn)}
                if failure is not None:
                    sources.append(CodexSource(source, call.work_name, None, None, None,
                        f"turn record missing or ambiguous in {record_path}; {failure}",
                        call.ended is None))
                    continue
            if record.get("refused") is True:
                continue
            thread, turn = record.get("thread"), record.get("turn")
            usage = codex_rollout.tokens(record.get("usage"))
            running = record.get("running", False)
            reason = record.get("usage_reason", "turn usage unavailable")
            if not from_rollout and thread is not None and (usage is None or turn is None or running):
                try:
                    rollout = codex_rollout.rollout_path(thread, home)
                    inputs.add(rollout)
                    start = record.get("started", call.started)
                    end = record.get("ended", legacy_end)
                    evidence = (codex_rollout.call_turn(thread, home, start, end, turn)
                                if start is not None and end is not None else None)
                    if evidence is not None:
                        turn, usage = evidence.turn, evidence.usage
                        running = evidence.ended is None
                except (OSError, ValueError, KeyError) as exc:
                    reason = "rollout evidence unavailable: " + str(exc)
                    watch_rollouts(home, inputs)
            if turn is None:
                usage = None
                reason = "accepted turn identity unavailable"
            elif usage is not None:
                reason = codex_rollout.usage_reason(usage, turn)
            item = CodexSource(source, call.work_name,
                               thread, turn, usage, reason, running)
            if thread is None or turn is None:
                sources.append(item)
            else:
                key = thread, turn
                previous = seen.get(key)
                if previous is None:
                    seen[key] = item
                elif previous.role != item.role or previous.usage != item.usage:
                    seen[key] = replace(previous, usage=None, reason="conflicting turn evidence")
    sources.extend(seen.values())
    native_sources = native_turn_sources(launches, owner, before, home, inputs)
    accepted = {(item.thread, item.turn): item for item in native_sources
                if item.thread is not None and item.turn is not None}
    sources = [item for item in sources if (item.thread, item.turn) not in accepted]
    sources.extend(accepted.values())
    sources.extend(item for item in native_sources if item.thread is None or item.turn is None)
    return CodexSpend(tuple(sources), tuple(fingerprint(p) for p in sorted(inputs)))



def native_turn_sources(launches: dict[Path, list[codex_reads.Call]], owner: dict[Path, str],
                        before: float | None, home: Path, inputs: set[Path]) -> list[CodexSource]:
    """Measure enrolled roots and descendants from the shared assignment projection."""
    from codex_ticket import Binding
    from run_reads import session_of
    from tree_reads import scratch as session_scratch

    stores = {binding.store for directory in launches
              if (binding := Binding.read(directory)) is not None}
    native_sources = []
    sessions = {session_scratch(session_of(path).name) for path in owner}
    for directory in sorted(sessions):
        inputs.add(directory / "codex-stores")
        for item in codex_reads.native_assignments(directory, include_history=True):
            if (item.store not in stores or item.state.get("refused")
                    or (before is not None and item.state["reserved"] > before)):
                continue
            inputs.update((item.store / "state.json", item.manifest, item.assignment.brief))
            usage = None
            reason = "native submission has no accepted rollout evidence"
            running = True
            try:
                turn = codex_reads.native_turn(item, home)
                inputs.add(codex_rollout.rollout_path(item.state["native"], home))
                usage = turn.usage
                reason = codex_rollout.usage_reason(usage, turn.turn)
                running = turn.ended is None
            except (OSError, ValueError, KeyError) as exc:
                reason = "native rollout evidence unavailable: " + str(exc)
            native_sources.append(CodexSource(str(item.manifest), item.assignment.role.value,
                item.state["native"], item.state["turn"], usage, reason, running))
    return native_sources
