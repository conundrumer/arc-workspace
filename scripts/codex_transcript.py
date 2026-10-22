"""Read the accepted Codex turns of a launcher, including incomplete work.

Entries appear as text, with JSON for unknown event forms.
"""

import argparse
import json
import shlex
import sys
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

from handbook.paths import scripts_importable

scripts_importable()

import codex_rollout
from controlled_markdown import mctx
from operations.codex_spend import CodexSource, CodexSpend
from spends import codex_spend
from transcripts import find


class Coverage(StrEnum):
    NONE = "no Codex calls"
    ATTRIBUTED = "attributable turns"
    GAP = "coverage gaps"


@dataclass
class Transcript:
    """Source attribution and the readable activity of each accepted turn."""
    spend: CodexSpend
    turns: list[tuple[CodexSource, Path, codex_rollout.Turn]] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)

    @property
    def coverage(self) -> Coverage:
        if self.gaps:
            return Coverage.GAP
        return Coverage.ATTRIBUTED if self.spend.sources else Coverage.NONE


def read(path: Path, home: Path | None = None) -> Transcript:
    """Read fresh source evidence after launcher profiling, outside its cache."""
    home = home or Path.home()
    try:
        spend = codex_spend({path: "unknown"}, home=home)
    except (OSError, ValueError, KeyError, TypeError, IndexError) as exc:
        spend = CodexSpend((CodexSource(str(path), "unknown", None, None, None,
                                       f"attribution unreadable: {exc}"),))
    result = Transcript(spend)
    threads: dict[str, tuple[Path, list[codex_rollout.Turn]] | str] = {}
    for source in result.spend.sources:
        if source.reason:
            result.gaps.append(f"{source.source}: {source.reason}")
        if source.thread is None or source.turn is None:
            if source.reason is None:
                result.gaps.append(f"{source.source}: accepted turn identity unavailable")
            continue
        if source.thread not in threads:
            try:
                rollout = codex_rollout.rollout_path(source.thread, home)
                threads[source.thread] = rollout, codex_rollout.read_turns(rollout)
            except (OSError, ValueError, KeyError, TypeError) as exc:
                threads[source.thread] = str(exc)
        evidence = threads[source.thread]
        if isinstance(evidence, str):
            result.gaps.append(f"{source.source}: rollout unreadable: {evidence}")
            continue
        rollout, turns = evidence
        found = [t for t in turns if t.turn == source.turn]
        if len(found) != 1:
            result.gaps.append(f"{source.source}: accepted turn missing or ambiguous: {source.turn}")
            continue
        turn = found[0]
        result.turns.append((source, rollout, turn))
        if turn.ended is None:
            result.gaps.append(f"{source.source}: accepted turn has no recorded end")
    result.turns.sort(key=lambda item: (item[2].started, item[0].thread or '', item[2].turn))
    return result


def activity(turn: codex_rollout.Turn) -> list[dict[str, Any]]:
    """Prefer response projections where events repeat their visible content."""
    responses = [r["payload"] for r in turn.activity if r.get("type") == "response_item"]
    texts = {c.get("text") for p in responses if p.get("type") == "message"
             for c in p.get("content", []) if isinstance(c.get("text"), str)}
    texts.update("\n".join(c["text"] for c in p.get("content", []) if "text" in c)
                 for p in responses if p.get("type") == "message")
    reasoning = {c.get("text") for p in responses if p.get("type") == "reasoning"
                 for c in [*(p.get("summary") or []), *(p.get("content") or [])]
                 if isinstance(c.get("text"), str)}
    identities = {p['id'] for p in responses if 'id' in p}
    calls = {p['call_id'] for p in responses if 'call_id' in p and
             p.get('type') in ('function_call', 'custom_tool_call')}
    results = {p['call_id'] for p in responses if 'call_id' in p and
               p.get('type') in ('function_call_output', 'custom_tool_call_output')}
    out = []
    for row in turn.activity:
        p = row.get("payload", {})
        if row.get("type") == "event_msg":
            kind = p.get("type")
            if kind in ("agent_message", "user_message") and p.get("message") in texts:
                continue
            if kind == "agent_reasoning" and p.get("text") in reasoning:
                continue
            if (isinstance(kind, str) and
                    ((kind.endswith('_begin') and p.get('call_id') in calls) or
                     (kind.endswith('_end') and p.get('call_id') in results))):
                continue
            if kind in ("item_started", "item_completed"):
                item = p.get("item", {})
                if item.get('id') in identities:
                    continue
        out.append(row)
    return out


def readable(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict) and value:
        return '\n'.join(f'{key}: {readable(item)}' for key, item in value.items())
    if isinstance(value, list) and value:
        return '\n'.join(readable(item) for item in value)
    return json.dumps(value, ensure_ascii=False)


def result_value(value: Any) -> Any:
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except ValueError:
            return value
        return result_value(decoded) if isinstance(decoded, (dict, list)) else value
    if isinstance(value, list):
        return [result_value(item) for item in value]
    if isinstance(value, dict):
        return {key: result_value(item) if key in
                {'output', 'result', 'content', 'text', 'aggregated_output'} else item
                for key, item in value.items()}
    return value


def display(row: dict[str, Any]) -> str:
    payload = row.get('payload')
    if not isinstance(payload, dict):
        return json.dumps(row, ensure_ascii=False)
    known = {
        'response_item': {'message', 'reasoning', 'function_call', 'custom_tool_call',
                          'function_call_output', 'custom_tool_call_output'},
        'event_msg': {'agent_message', 'user_message', 'agent_reasoning', 'task_started',
                      'task_complete', 'turn_aborted', 'token_count', 'item_started',
                      'item_completed', 'exec_command_begin', 'exec_command_end'},
    }
    row_type = row.get('type')
    if not isinstance(row_type, str) or payload.get('type') not in known.get(row_type, set()):
        return json.dumps(row, ensure_ascii=False)
    projected = dict(payload)
    if payload.get('type') in {'function_call_output', 'custom_tool_call_output',
                               'exec_command_end'}:
        projected = result_value(projected)
    if payload.get('type') == 'function_call' and isinstance(payload.get('arguments'), str):
        try:
            projected['arguments'] = json.loads(payload['arguments'])
        except ValueError:
            pass
    metadata = {key: value for key, value in row.items() if key != 'payload'}
    return readable(metadata) + '\n' + readable(projected)


def command(launcher: str, offset: int, limit: int, full: bool) -> str:
    return shlex.join(['uv', 'run', 'python', 'scripts/codex_transcript.py', launcher,
                       '--offset', str(offset), '--limit', str(limit),
                       *(['--full'] if full else [])])


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("launcher", help="launcher agent id")
    ap.add_argument("--offset", type=int, default=0,
                    help="zero-based deduplicated activity row to start at (default: %(default)s)")
    ap.add_argument("--limit", type=int, default=200,
                    help="maximum activity rows (default: %(default)s)")
    ap.add_argument("--full", action="store_true",
                    help="show full contents of selected rows (long entries are shortened by default)")
    args = ap.parse_args(argv)
    if args.offset < 0 or args.limit < 1:
        ap.error("offset must be nonnegative and limit must be positive")
    result = read(find(args.launcher))
    print(f"Codex: {result.coverage}")
    rows = []
    for source, path, turn in result.turns:
        print(f"role {source.role}; thread {source.thread}; turn {source.turn}; source {path}; "
              f"start {turn.started}; end {turn.ended}; state {turn.end_state or 'unfinished'}; "
              f"usage {json.dumps(asdict(source.usage)) if source.usage else 'unknown'}")
        rows.extend((source, row) for row in activity(turn))
    for gap in result.gaps:
        print(f"gap: {gap}")
    end = min(len(rows), args.offset + args.limit)
    for index in range(args.offset, end):
        source, row = rows[index]
        content = display(row)
        print(f"{index} {source.thread}/{source.turn}")
        if not args.full and len(content) > 4000:
            print(content[:4000])
            print(mctx("[shortened; full entry: {command}]").format(
                command=command(args.launcher, index, 1, True)))
        else:
            print(content)
    if end < len(rows):
        print(f"continue: {command(args.launcher, end, args.limit, args.full)}")
    else:
        print("end of attributable activity")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
