"""Run the agent's checklist on the shared Codex daemon, with exec fallback.

    uv run python scripts/codex_agent.py <agent> <scratch> <brief> <model> <effort> [--cwd <dir>] [--resume]

Give the starting instruction or a later result or message on stdin, closed
within five seconds. An open input fails before the launch. The
first call supplies the rendered agent document and rendered repo and user
CLAUDE.md files as developer instructions, with the configured Codex style.
The brief and starting instruction are user input. A fresh call refuses existing
thread or turn history without changing it.
Each work call requires the calling Claude session identity and passes it to
worker shells through request-local configuration. Control calls need no identity.
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
import io
import json
import os
import select
import subprocess
import sys
import time
import tomllib
from collections.abc import Callable
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import asdict
from functools import partial
from pathlib import Path
from typing import Any

import codex_daemon
import codex_rollout
import ticket_numbers

from controlled_markdown import mctx
from engine import checkout
from handbook.agent_documents import agent_dir, agent_doc
from handbook.context import codex_config_value, codex_permissions, entry_text
from handbook.listings import listings
from operations.roles import ANALYST_NAMES, CODEX_ROLES, GENERAL, Role
from operations.state import CodexUsage

FRESH_REFUSAL = "fresh launch refused: existing Codex history; no thread or turn accepted"
CONTROLS = ("show", "steer", "interrupt")

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

NATIVE_PREAMBLE = mctx(
    "Do the work your role's documents and brief give. Where your role has a "
    "checklist, run `uv run python scripts/step.py <role>` yourself, starting "
    "with its first item, and walk it through its end. Do each item and run "
    "the step command it gives to go on, including choosing whether to enter "
    "conditional parts. Where blocked, use your checklist's `--stop` call "
    "and report what remains unfinished and why. Use the operations agent "
    "id in your assignment for commands that take your agent id.")

NATIVE_RULES = mctx({
    "launch": (
        "For each agent launch your documents give, use its filed assignment "
        "to call `spawn_agent` with `fork_turns=\"none\"` and the assigned "
        "role instructions, brief, model and reasoning effort. Keep the "
        "operations agent id and native agent id as separate identities."),
    "messages": (
        "Deliver each message your documents give within this ticket's "
        "native tree. Use `send_message` for a running recipient and "
        "`followup_task` for a finished child. If a recipient finishes "
        "before delivery, explicitly follow up that child. Use the native "
        "id for native tools. File substantive assignment changes before "
        "delivery so the changed assignment requires a new validated result."),
    "external-decision": (
        "Where work needs an external decision, write the unfinished "
        "findings to your assigned report, use your checklist's `--stop` "
        "call where applicable, and finish with a needs-operator outcome. "
        "The root collects that outcome and joins its descendants before "
        "returning it to the owning operator."),
    "waiting": (
        "Use `list_agents` to observe descendants and `wait_agent` to wait "
        "for their updates. Join every descendant before ending the root "
        "turn. A runtime completed status does not validate a report. "
        "Accept each result through the shared report validator before "
        "using it to release a dependency. Explicitly follow up a finished "
        "child whose result is invalid; if no valid result can be obtained, "
        "join live descendants and return an unfinished outcome."),
    "review": (
        "Run `uv run python scripts/operate.py review <agent id>` with your "
        "operations agent id, and make each filed native check launch it "
        "prints. Run it again after each launch. Keep each required review "
        "and its round cap. Use the validated checker reports for findings "
        "and corrections within this tree."),
    "root-resume": (
        "Keep editor reports separate from root dispatch results. On a new "
        "root assignment, start a fresh checker for work addressed to an "
        "old child, using its filed findings and predecessor reference. "
        "External input comes from the owning operator after the root turn "
        "and its descendants end."),
    "final-reply": (
        "Write your final reply to the assigned report file, then return "
        "that file's path alone. Complete the assignment only with a report "
        "that passes the shared validator for that assignment revision and "
        "its inputs. A needs-operator report leaves the change unapproved."),
})


def role_instructions(root: Path, home: Path, agent: str,
                      agent_type: str | None = None) -> str:
    user = home / ".claude" / "CLAUDE.md"
    kind = agent_type or Role(agent).agent_type
    values = partial(listings, codex=True)
    document = ([] if kind == GENERAL else
                [entry_text(agent_doc(kind, agent_dir(root)), values=values)])
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
        entry_text((root / "CLAUDE.md").resolve(), values=values),
        *([user.read_text()] if user.exists() else [])])


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
                transport: Callable[[], Any], worker_config: dict[str, str],
                instructions: str | None = None,
                home: Path | None = None) -> str | None:
    """Try the daemon with the caller's worker configuration; only a new thread
    may fall back before turn submission."""
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
            loaded = codex_daemon.start(client, thread, cwd, model, effort, writable,
                                        worker_config, instructions)
        except (OSError, ValueError) as exc:
            # With no daemon connected, no daemon holds the thread, so exec can resume it.
            if original_thread is not None and client is not None:
                raise TurnFailed(str(exc), message) from exc
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
            if original_thread is not None:
                raise TurnFailed(str(exc), message) from exc
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
    parser.add_argument("action", choices=CONTROLS)
    parser.add_argument("scratch", type=Path)
    parser.add_argument("message", nargs="?")
    args = parser.parse_args(argv)
    if args.action == "steer" and not args.message:
        parser.error("steer requires a message")
    import codex_ticket

    if args.action == "steer":
        codex_ticket.legacy_guard(args.scratch)
    elif args.action == "interrupt" and codex_ticket.interrupt(args.scratch, transport):
        return 0
    elif args.action == "show" and (binding := codex_ticket.Binding.read(args.scratch)) is not None:
        print(binding.correction())
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
    id even on failure so a later call can continue the same session.
    Require the calling Claude session before work and configure both transports
    to give worker shells that identity on every call."""
    scratch = scratch.resolve()
    import codex_ticket

    codex_ticket.legacy_guard(scratch)
    thread = saved_thread(scratch, resume)
    scratch.mkdir(parents=True, exist_ok=True)
    session = scratch / "codex-session"
    preparing = time.time()
    try:
        worker_config = {
            "shell_environment_policy.set." + ticket_numbers.SESSION_VAR: ticket_numbers.session_id(),
        }
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
    except Exception as exc:
        from uuid import uuid4

        failure = {"id": uuid4().hex, "started": preparing, "ended": time.time(),
                   "error": str(exc)}
        # Separate from turn history: a fresh retry must still be possible.
        with (scratch / "codex-launch-failures.jsonl").open("a") as record:
            record.write(json.dumps(failure) + "\n")
        raise ValueError(f"launch failed before Codex started [{failure['id']}]: {exc}") from exc
    daemon_message = daemon_turn(scratch, thread, prompt, item, cwd, model, effort,
                                 writable, transport, worker_config, instructions, home)
    if daemon_message is not None:
        return daemon_message
    argv = ["codex", "exec", "-m", model, "-c", f'model_reasoning_effort="{effort}"',
            "-c", "project_doc_max_bytes=0",
            *(a for k, v in {**codex_permissions([*writable, cwd / ".codex"]),
                           **worker_config}.items()
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


def input_text() -> str:
    """Read input through EOF within five seconds, before starting a turn."""
    if isinstance(sys.stdin, io.StringIO):
        return sys.stdin.read()
    if sys.stdin.isatty():
        raise ValueError("stdin is a terminal; supply input with a closed pipe or file")
    deadline = time.monotonic() + 5
    chunks: list[bytes] = []
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0 or not select.select([sys.stdin], [], [], remaining)[0]:
            raise ValueError("stdin did not close within five seconds; use a closed pipe or file")
        chunk = os.read(sys.stdin.fileno(), 65536)
        if not chunk:
            return b"".join(chunks).decode(sys.stdin.encoding or "utf-8")
        chunks.append(chunk)


def work_parser() -> argparse.ArgumentParser:
    """The parser for `main`'s work calls."""
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
    return parser


def work_args(argv: list[str]) -> argparse.Namespace | None:
    """The arguments `main` runs a turn with, or None where `argv` is a control
    call or `main` exits before its turn (help, or arguments its parser refuses)."""
    if argv and argv[0] in CONTROLS:
        return None
    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
        try:
            return work_parser().parse_args(argv)
        except SystemExit:
            return None


def main(argv: list[str]) -> int:
    if argv and argv[0] in CONTROLS:
        try:
            return control(argv)
        except (OSError, ValueError) as exc:
            print(f"codex_agent: {exc}", file=sys.stderr)
            return 1
    args = work_parser().parse_args(argv)
    try:
        item = input_text()
        saved_thread(args.scratch, args.resume)
    except (OSError, ValueError) as exc:
        print(f"codex_agent: {exc}", file=sys.stderr)
        return 1
    done = args.scratch / DONE
    done.unlink(missing_ok=True)
    try:
        message = run(args.agent, args.scratch, args.brief, args.model, args.effort,
                      item, checkout.ROOT, Path.home(),
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
