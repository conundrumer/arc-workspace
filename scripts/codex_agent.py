"""Run the agent's checklist on the shared Codex daemon, with exec fallback.

    uv run python scripts/codex_agent.py <agent> <scratch> <brief> <model> <effort> [--cwd <dir>] [--resume]

Give the starting instruction or a later result or message on stdin. The
first call supplies the rendered agent document and repo and user CLAUDE.md
files as developer instructions, with the configured Codex style. The brief
and starting instruction are user input. A fresh call refuses existing
thread or turn history without changing it.
`--resume` requires the thread in <scratch>/codex-session and continues it
with its initial instructions and only the new input.
`--cwd` sets the directory Codex works in, defaulting to the current directory.
The last message is printed; a failed or interrupted turn exits 1. The daemon
is never started or stopped. An unavailable or refusing daemon falls back to exec
before a turn starts; a lost connection after submission is reported, not replayed.

    uv run python scripts/codex_agent.py show <scratch>
    uv run python scripts/codex_agent.py steer <scratch> <message>
    uv run python scripts/codex_agent.py interrupt <scratch>

Show reads the live rollout; steer and interrupt reach the running daemon turn.
"""

import argparse
import json
import os
import subprocess
import sys
import time
import tomllib
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path
from typing import Any

import codex_daemon
import codex_rollout

from controlled_markdown import mctx
from engine import checkout
from handbook.context import codex_config_value, codex_permissions
from operations.roles import ANALYST_NAMES, CODEX_ROLES, GENERAL, Role
from operations.state import CodexUsage

FRESH_REFUSAL = "fresh launch refused: existing Codex history; no thread or turn accepted"

DONE = "codex-done"
"""The file under the scratch directory that the command makes once it ends,
which the Codex launcher's foreground wait checks for."""

PREAMBLE = mctx(
    "Do the work your role's documents and brief give. Where your role has a "
    "checklist, run `uv run python scripts/step.py <role>` yourself, starting "
    "with its first item, and walk it through its end in this run. Do each "
    "item and run the step command it gives to go on, including choosing "
    "whether to enter conditional parts. You have no Agent or SendMessage "
    "tool; make no Agent call and no SendMessage. Where your documents give "
    "one, end your turn with the full call to make, including all arguments "
    "and the full text to send. The Claude launcher makes the call and "
    "passes its result or a message back by resuming this session; then "
    "continue your walk. Also ask the launcher to run `operate.py review` "
    "in its own foreground Bash call where your documents give it. The "
    "Codex mode procedure is for that launcher; do not run `codex_agent.py` "
    "yourself. Where blocked, use your checklist's `--stop` call and report "
    "what remains unfinished and why. Write the report and final reply "
    "your documents give; the launcher delivers your final reply.")


def without_front(text: str) -> str:
    """Remove the rendered document's leading YAML front matter."""
    lines = text.splitlines(keepends=True)
    if lines and lines[0].strip() == "---":
        for i, line in enumerate(lines[1:], 1):
            if line.strip() == "---":
                return "".join(lines[i + 1:]).lstrip("\n")
        raise ValueError("agent document has unclosed front matter")
    return text


def role_instructions(root: Path, home: Path, agent: str,
                      agent_type: str | None = None) -> str:
    user = home / ".claude" / "CLAUDE.md"
    kind = agent_type or Role(agent).agent_type
    document = ([] if kind == GENERAL else
                [without_front((root / ".claude" / "agents" / f"{kind}.md").read_text())])
    styles = []
    for config in (Path(os.environ.get("CODEX_HOME", home / ".codex")) / "config.toml",
                   checkout.main_worktree(root) / ".codex" / "config.toml"):
        if config.exists():
            style = tomllib.loads(config.read_text()).get("developer_instructions")
            if style is not None:
                if not isinstance(style, str):
                    raise ValueError(f"{config}: developer_instructions must be a string")
                styles.append(style)
    return "\n\n".join([
        *styles, PREAMBLE, *document,
        (root / "CLAUDE.md").read_text(), *([user.read_text()] if user.exists() else [])])


def execute(argv: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True, text=True)


def error_text(event: dict[str, Any]) -> str:
    """The message of a CLI error event, including a nested turn error."""
    error = event.get("error", event)
    return str(error.get("message", error)) if isinstance(error, dict) else str(error)


class TurnFailed(ValueError):
    """A failed turn whose last answer still belongs on stdout."""

    def __init__(self, detail: str, message: str):
        super().__init__(detail)
        self.message = message


def usage_record(thread: str | None, events: list[dict[str, Any]], started: float,
                 ended: float, home: Path,
                 baseline: CodexUsage | None = None) -> dict[str, Any]:
    """Keep accepted identity and usage even when a turn fails."""
    accepted = next((e.get("turn_id") for e in events if e.get("turn_id")), None)
    usage = None
    running = thread is not None and not any(
        e.get("type") in ("turn.completed", "turn.failed") for e in events)
    if thread is not None:
        try:
            turn = codex_rollout.call_turn(thread, home, started, ended, accepted)
        except (OSError, ValueError, KeyError):
            turn = None
        if turn is not None:
            accepted, usage, running = turn.turn, turn.usage, turn.ended is None
    cumulative = [codex_rollout.tokens(e.get("cumulative")) for e in events
                  if e.get("type") == "usage.updated" and e.get("cumulative") is not None]
    if usage is None and baseline is not None and cumulative and cumulative[-1] is not None:
        usage = codex_rollout.difference(cumulative[-1], baseline)
    # Exec reports per-turn usage. Daemon cumulative readings need boundaries.
    direct = [e.get("usage") for e in events
              if e.get("type") in ("turn.completed", "turn.failed") and e.get("usage") is not None]
    if direct:
        usage = codex_rollout.tokens(direct[-1])
    reason = codex_rollout.usage_reason(usage, accepted)
    return {"turn": accepted, "usage": asdict(usage) if usage is not None else None,
            "usage_reason": reason, "running": running, "started": started, "ended": ended,
            "refused": thread is None and bool(events) and
                       all(e.get("type") == "error" for e in events)}


def daemon_turn(scratch: Path, thread: str | None, prompt: str, item: str,
                cwd: Path, model: str, effort: str, writable: list[Path],
                transport: Callable[[], Any], instructions: str | None = None,
                home: Path | None = None) -> str | None:
    """Try the daemon; only a refusal before turn submission permits fallback."""
    call_started = time.time()
    baseline = CodexUsage(0, 0, 0, 0, 0) if thread is None else None
    if thread is not None:
        try:
            previous = codex_rollout.turns(thread, home or Path.home())
            if previous and previous[-1].ended is not None:
                baseline = previous[-1].after
        except (OSError, ValueError, KeyError):
            pass
    original_thread = thread
    client = None
    events: list[dict[str, Any]] = []
    submitted = False
    message = ""
    ok = False

    def emit(event: dict[str, Any]):
        nonlocal message
        events.append(event)
        if event.get("item", {}).get("type") == "agent_message":
            message = event["item"]["text"]
            (scratch / "codex-last.md").write_text(message)

    try:
        try:
            client = transport()
            loaded = codex_daemon.start(client, thread, cwd, model, effort, writable, instructions)
        except (OSError, ValueError) as exc:
            print(f"codex_agent: shared daemon unavailable or refused: {exc}; "
                  "falling back to codex exec", file=sys.stderr)
            return None
        thread = str(loaded["thread"]["id"])
        (scratch / "codex-session").write_text(thread + "\n")
        events.append({"type": "thread.started", "thread_id": thread})
        # A disconnect here may follow acceptance. Never replay that work in exec.
        submitted = True
        try:
            started = client.call("turn/start", {"threadId": thread, "effort": effort,
                                  "input": [{"type": "text", "text": prompt}]})
        except codex_daemon.Refused as exc:
            submitted = False
            if original_thread is None:
                (scratch / "codex-session").unlink()
            print(f"codex_agent: shared daemon refused: {exc}; falling back to codex exec",
                  file=sys.stderr)
            return None
        events.append({"type": "turn.started", "turn_id": started["turn"]["id"]})
        message, ok = codex_daemon.collect(client, thread, started["turn"]["id"], emit)
        (scratch / "codex-last.md").write_text(message)
        ok = ok and bool(message.strip())
        if not ok:
            raise TurnFailed(f"Codex turn {events[-1].get('status')} "
                             f"{events[-1].get('error') or ''}".strip(), message)
        return message
    except (OSError, ValueError) as exc:
        if isinstance(exc, TurnFailed):
            raise
        raise TurnFailed(f"daemon turn failed (not replayed): {exc}", message) from exc
    finally:
        try:
            if submitted:
                evidence = usage_record(thread, events, call_started, time.time(),
                                        home or Path.home(), baseline)
                with (scratch / "codex-events.jsonl").open("a") as record:
                    record.write(json.dumps({"thread": thread, "input": item,
                        "output": "\n".join(map(json.dumps, events)), "ok": ok,
                        **evidence}) + "\n")
        finally:
            if client is not None:
                client.close()


def control(argv: list[str], transport: Callable[[], Any] = codex_daemon.Proxy) -> int:
    """Show live evidence or deliver a steer/interrupt without resuming a thread."""
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("show", "steer", "interrupt"))
    parser.add_argument("scratch", type=Path)
    parser.add_argument("message", nargs="?")
    args = parser.parse_args(argv)
    if args.action == "steer" and not args.message:
        parser.error("steer requires a message")
    if not (args.scratch / "codex-session").exists():
        print(f"{args.scratch}: no saved Codex thread; no turn running")
        return 0
    state = codex_rollout.read(args.scratch, Path.home())
    if args.action == "show":
        print(state.show())
    elif state.turn is None:
        print(f"thread {state.thread}: no turn running")
    else:
        client = transport()
        try:
            params: dict[str, Any] = {"threadId": state.thread}
            if args.action == "steer":
                params.update(expectedTurnId=state.turn,
                              input=[{"type": "text", "text": args.message}])
            else:
                params["turnId"] = state.turn
            try:
                client.call("turn/" + args.action, params)
            except codex_daemon.Refused:
                current = client.call("thread/read", {"threadId": state.thread, "includeTurns": True})
                if not any(t["status"] == "inProgress" for t in current["thread"]["turns"]):
                    print(f"thread {state.thread}: no turn running")
                    return 0
                raise
            print(f"{args.action} sent to turn {state.turn}")
        finally:
            client.close()
    return 0


def saved_thread(scratch: Path, resume: bool) -> str | None:
    """Validate the launch before changing any saved evidence."""
    session = scratch / "codex-session"
    if not resume:
        if session.exists() or (scratch / "codex-events.jsonl").exists():
            raise ValueError(FRESH_REFUSAL)
        return None
    thread = session.read_text().strip()
    if not thread:
        raise ValueError(f"{session}: empty session id")
    return thread


def run(agent: str, scratch: Path, brief: Path, model: str, effort: str, item: str,
        root: Path, home: Path, main: Path, cwd: Path,
        runner: Callable[[list[str]], subprocess.CompletedProcess[str]] = execute,
        agent_type: str | None = None,
        transport: Callable[[], Any] = codex_daemon.Proxy,
        resume: bool = False) -> str:
    """Return the last message, or raise with the CLI's error. Save a thread
    id even on failure so a later call can continue the same session."""
    scratch = scratch.resolve()
    thread = saved_thread(scratch, resume)
    scratch.mkdir(parents=True, exist_ok=True)
    session = scratch / "codex-session"
    instructions = None if thread is not None else role_instructions(root, home, agent, agent_type)
    prompt = item if thread is not None else "\n\n".join([brief.read_text(), item])
    last = scratch / "codex-last.md"
    last.unlink(missing_ok=True)
    git_dir = Path(checkout.git_out(cwd, "rev-parse", "--absolute-git-dir").strip())
    # The repository's commands write the main tree's tickets, git data and
    # caches, and uv's and cargo's caches, from any worktree. Codex keeps the
    # git dir of a worktree it runs in read-only unless that dir is a root.
    writable = [main / "tickets", main / ".git",
                *([git_dir] if git_dir != main / ".git" else []), main / ".cache",
                home / ".cache" / "uv", home / ".cargo", scratch]
    daemon_message = daemon_turn(scratch, thread, prompt, item, cwd, model, effort,
                                 writable, transport, instructions, home)
    if daemon_message is not None:
        return daemon_message
    argv = ["codex", "exec", "-m", model, "-c", f'model_reasoning_effort="{effort}"',
            "-c", "project_doc_max_bytes=0",
            *(a for k, v in codex_permissions([*writable, cwd / ".codex"]).items()
              for a in ("-c", f"{k}={codex_config_value(v)}")),
            "-c", 'approval_policy="never"',
            "--skip-git-repo-check", "-C", str(cwd), "-o", str(last), "--json"]
    if instructions is not None:
        argv.extend(["-c", "developer_instructions=" + json.dumps(instructions)])
    call_started = time.time()
    done = runner([*argv, *(["resume", thread] if thread is not None else []), prompt])
    errors: list[str] = []
    events: list[dict[str, Any]] = []
    for line in done.stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        events.append(event)
        if thread is None and isinstance(found := event.get("thread_id"), str) and found:
            thread = found
            session.write_text(thread + "\n")
        if event.get("type") in ("error", "turn.failed", "usage_limit"):
            errors.append(error_text(event))
        elif event.get("type") == "item.completed" and isinstance(event.get("item"), dict):
            if event["item"].get("type") == "error":
                errors.append(error_text(event["item"]))
    message = last.read_text() if last.exists() else ""
    ok = not (done.returncode or errors or not message.strip() or thread is None)
    with (scratch / "codex-events.jsonl").open("a") as record:
        record.write(json.dumps({"thread": thread, "input": item, "output": done.stdout, "ok": ok,
            **usage_record(thread, events, call_started, time.time(), home)}) + "\n")
    if not ok:
        details = "\n".join([*errors, done.stderr.strip()]).strip()
        raise ValueError(details or
                         f"codex exec exited {done.returncode} with no last message or thread id")
    return message


def main(argv: list[str]) -> int:
    if argv and argv[0] in ("show", "steer", "interrupt"):
        try:
            return control(argv)
        except (OSError, ValueError) as exc:
            print(f"codex_agent: {exc}", file=sys.stderr)
            return 1
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("agent", choices=sorted(r.value for r in CODEX_ROLES))
    parser.add_argument("scratch", type=Path)
    parser.add_argument("brief", type=Path)
    parser.add_argument("model")
    parser.add_argument("effort", choices=("low", "medium", "high", "xhigh"))
    parser.add_argument("--cwd", type=Path, default=Path.cwd())
    parser.add_argument("--agent-type", choices=sorted({r.agent_type for r in CODEX_ROLES}
                                                     | ANALYST_NAMES))
    parser.add_argument("--resume", action="store_true",
                        help="continue the saved thread; required for later turns")
    args = parser.parse_args(argv)
    try:
        saved_thread(args.scratch, args.resume)
    except (OSError, ValueError) as exc:
        print(f"codex_agent: {exc}", file=sys.stderr)
        return 1
    done = args.scratch / DONE
    done.unlink(missing_ok=True)
    try:
        message = run(args.agent, args.scratch, args.brief, args.model, args.effort,
                      sys.stdin.read(), checkout.ROOT, Path.home(),
                      checkout.main_worktree(checkout.ROOT), args.cwd.resolve(),
                      agent_type=args.agent_type, resume=args.resume)
    except (OSError, ValueError) as exc:
        if isinstance(exc, TurnFailed) and exc.message:
            print(exc.message, flush=True)
        print(f"codex_agent: {exc}", file=sys.stderr)
        return 1
    else:
        print(message, end="" if message.endswith("\n") else "\n", flush=True)
        return 0
    finally:
        if args.scratch.is_dir():
            done.touch()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
