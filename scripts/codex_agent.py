"""Run the agent's checklist on the shared Codex daemon, with exec fallback.

    uv run python scripts/codex_agent.py <agent> <scratch> <brief> <model> <effort> [--agent-id <id>] [--cwd <dir>] [--resume]

Give optional starting material or a later result or message on stdin, closed
within five seconds. An open input fails before the launch. The
first call supplies the rendered agent document and rendered repo and user
CLAUDE.md files as developer instructions, with the configured Codex style.
A fresh call requires `--agent-id`, the launcher's agent id, and puts its id line
before the brief and starting instruction in user input. A fresh call refuses
existing thread or turn history without changing it.
A scratch directory permits one work call at a time. Contention accepts no turn;
wait for its owner, then retry. A resume refuses an active rollout turn; use
show or interrupt and wait for that turn to end before retrying. Controls remain
available while work owns the lock.
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
import fcntl
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
import codex_ticket
import ticket_numbers
from subagent_start_hook import context

from controlled_markdown import mctx
from engine import checkout
from handbook.agent_documents import agent_dir, agent_doc
from handbook.checklist import checklist_agents, step_call
from handbook.context import codex_config_value, codex_permissions, entry_text
from handbook.listings import listings
from operations.roles import ANALYST_NAMES, CODEX_ROLES, GENERAL, ReasoningEffort, Role
from operations.codex_spend import CodexUsage

FRESH_REFUSAL = "fresh launch refused: existing Codex history; no thread or turn accepted"
CONTROLS = ("show", "steer", "interrupt")

BUSY_REFUSAL = "work call refused: scratch is busy; no thread or turn accepted; wait for its owner, then retry"

DONE = "codex-done"
"""The file under the scratch directory that the command makes once it ends,
which the Codex launcher's foreground wait checks for."""

STEP_OPENING = mctx(
    "Run `{call}` now. What it prints is your instruction: do it fully, "
    "then run the call it gives, as a Bash call by itself. Only that call "
    "prints the next item. Your documents are reference for how to do each "
    "item; your brief is its material.")

WORK_OPENING = mctx("Do the work your documents and brief give.")

STEP_STOP = mctx("Where blocked, run `{call} --stop <item>`, and report what remains unfinished and why.")
WORK_STOP = mctx("Where blocked, report what remains unfinished and why.")

PREAMBLE = mctx("{opening} {stop}")


def opening(kind: str) -> str:
    return (STEP_OPENING.format(call=step_call(kind))
            if kind in checklist_agents() else WORK_OPENING)


def role_instructions(root: Path, home: Path, agent: str,
                      agent_type: str | None = None) -> str:
    user = home / ".claude" / "CLAUDE.md"
    kind = agent_type or Role(agent).agent_type
    values = partial(listings, codex=True)
    document = ([] if kind == GENERAL else
                [entry_text(agent_doc(kind, agent_dir(root)), values=values)])
    import controlled_markdown as nm

    native_root = checkout.main_worktree(root)
    native_file = native_root / "prompts/agents/notes/native-agents.md"
    registry = nm.Registry(native_root)
    native_document = registry.load(native_file)
    native_section = registry.ids[native_document.source]["native-tools"]
    native = nm.render(nm.section_document(native_document, native_section), registry)
    native = native.replace("](#", "](" + str(native_file) + "#")
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
        *styles, PREAMBLE.format(
            opening=opening(kind),
            stop=(STEP_STOP.format(call=step_call(kind))
                  if kind in checklist_agents() else WORK_STOP)), native, *document,
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
                home: Path | None = None,
                admission: tuple[codex_ticket.Store, codex_ticket.Assignment, str] | None = None) -> str | None:
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
        if admission is not None:
            store, assignment, token = admission
            store.accepted(assignment.agent, token, thread, str(started["turn"]["id"]))
        message, ok = codex_daemon.collect(client, thread, started["turn"]["id"], emit)
        (scratch / "codex-last.md").write_text(message)
        ok = ok and bool(message.strip())
        if not ok:
            raise TurnFailed(f"Codex turn {events[-1].get('status')} "
                             f"{events[-1].get('error') or ''}".strip(), message)
        return message
    except (OSError, ValueError) as exc:
        if not submitted:
            raise launch_failure(scratch, call_started, exc) from exc
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


def work(agent: str, scratch: Path, brief: Path, model: str, effort: str, item: str,
        root: Path, home: Path, main: Path, cwd: Path,
        runner: Callable[[list[str]], subprocess.CompletedProcess[str]] = execute,
        agent_type: str | None = None,
        transport: Callable[[], Any] = codex_daemon.Proxy,
        thread: str | None = None,
        admission: tuple[codex_ticket.Store, codex_ticket.Assignment, str] | None = None,
        agent_id: str | None = None) -> str:
    """Return the last message, or raise with the CLI's error. Save a thread
    id even on failure so a later call can continue the same session.
    Require the calling Claude session before work and configure both transports
    to give worker shells that identity on every call."""
    session = scratch / "codex-session"
    preparing = time.time()
    try:
        worker_config = {
            "shell_environment_policy.set." + ticket_numbers.SESSION_VAR: ticket_numbers.session_id(),
        }
        instructions = None if thread is not None else role_instructions(root, home, agent, agent_type)
        if thread is None:
            if agent_id is None:
                raise ValueError(mctx("The fresh call is missing its agent id (--agent-id)."))
            item = "\n\n".join(filter(None, [opening(agent_type or Role(agent).agent_type), item]))
            prompt = "\n\n".join([context(agent_id), brief.read_text(), item])
        else:
            prompt = item
        if admission is not None:
            store, assignment, _ = admission
            if thread is not None:
                prompt = brief.read_text()
            prompt += "\n\n" + codex_ticket.NATIVE_IDENTITY.format(
                agent=assignment.agent, scratch=scratch,
                manifest=store.manifest(assignment.agent, assignment.revision))
        last = scratch / "codex-last.md"
        last.unlink(missing_ok=True)
        git_dir = Path(checkout.git_out(cwd, "rev-parse", "--absolute-git-dir").strip())
        # The repository's commands write the main tree's tickets, git data and
        # caches, and uv's and cargo's caches, from any worktree. Codex keeps the
        # git dir of a worktree it runs in read-only unless that dir is a root.
        writable = [main / "tickets", main / ".git",
                    *([git_dir] if git_dir != main / ".git" else []), main / ".cache",
                    home / ".cache" / "uv", home / ".cargo", scratch]
        if admission is not None:
            writable.extend([admission[0].path, admission[1].report.parent])
    except Exception as exc:
        raise launch_failure(scratch, preparing, exc) from exc
    daemon_message = daemon_turn(scratch, thread, prompt, item, cwd, model, effort,
                                 writable, transport, worker_config, instructions, home, admission)
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
    try:
        command = [*argv, *(["resume", thread] if thread is not None else []), prompt]
        done = (execute_native(command, admission, home) if runner is execute and admission is not None
                else runner(command))
    except OSError as exc:
        raise launch_failure(scratch, call_started, exc) from exc
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
    if thread is None and events and all(e.get("type") == "error" for e in events):
        raise launch_failure(scratch, call_started,
                             ValueError(done.stderr.strip() or "exec accepted no turn"))
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


def execute_native(argv: list[str], admission: tuple[codex_ticket.Store, codex_ticket.Assignment, str],
                   home: Path) -> subprocess.CompletedProcess[str]:
    """Publish exec acceptance while the root can still launch children."""
    import tempfile

    store, assignment, token = admission
    output = []
    native: str | None = None
    with tempfile.TemporaryFile(mode="w+") as errors:
        with subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                              stderr=errors, text=True) as process:
            assert process.stdout is not None
            for line in process.stdout:
                output.append(line)
                try:
                    event = json.loads(line)
                    if event.get("thread_id"):
                        native = str(event["thread_id"])
                        (assignment.scratch / "codex-session").write_text(native + "\n")
                    if native is not None and event.get("type") == "turn.started":
                        turns = codex_rollout.turns(native, home)
                        if turns and turns[-1].ended is None:
                            store.accepted(assignment.agent, token, native, turns[-1].turn)
                except (OSError, ValueError, KeyError):
                    pass
            result = process.wait()
        errors.seek(0)
        return subprocess.CompletedProcess(argv, result, "".join(output), errors.read())


def launch_failure(scratch: Path, started: float, error: Exception) -> ValueError:
    """Record a proved failure before either transport accepted work."""
    from uuid import uuid4

    failure = {"id": uuid4().hex, "started": started, "ended": time.time(),
               "error": str(error)}
    with (scratch / "codex-launch-failures.jsonl").open("a") as record:
        record.write(json.dumps(failure) + "\n")
    return ValueError(f"launch failed before Codex started [{failure['id']}]: {error}")


def run(agent: str, scratch: Path, brief: Path, model: str, effort: str, item: str,
        root: Path, home: Path, main: Path, cwd: Path,
        runner: Callable[[list[str]], subprocess.CompletedProcess[str]] = execute,
        agent_type: str | None = None,
        transport: Callable[[], Any] = codex_daemon.Proxy,
        resume: bool = False,
        assignment: codex_ticket.Assignment | None = None,
        store_path: Path | None = None,
        agent_id: str | None = None) -> str:
    """Hold exclusive ownership from validation through completion publication."""
    import codex_ticket

    scratch = scratch.resolve()
    if assignment is None:
        codex_ticket.legacy_guard(scratch)
    scratch.parent.mkdir(parents=True, exist_ok=True)
    with (scratch.parent / ("." + scratch.name + ".codex-work.lock")).open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError(BUSY_REFUSAL) from exc
        thread = saved_thread(scratch, resume)
        scratch.mkdir(parents=True, exist_ok=True)
        if resume:
            assert thread is not None
            try:
                previous = codex_rollout.turns(thread, home)
            except (OSError, ValueError, KeyError) as exc:
                if isinstance(exc, ValueError) and str(exc) == f"expected one live rollout for {thread}, found 0":
                    previous = []
                elif assignment is not None:
                    raise codex_ticket.Refused(mctx("agent {agent}: {reason}").format(
                        agent=assignment.agent, reason=exc)) from exc
                else:
                    raise
            if previous and previous[-1].ended is None:
                raise launch_failure(scratch, time.time(), ValueError(
                    "saved turn is active; use show or interrupt, wait for its end, then resume"))
        done = scratch / DONE
        done.unlink(missing_ok=True)
        admission = None
        if assignment is not None:
            if (store_path is None or assignment.scratch.resolve() != scratch
                    or assignment.brief.resolve() != brief.resolve()
                    or assignment.worktree.resolve() != cwd.resolve()
                    or assignment.role != Role(agent)):
                raise codex_ticket.Refused("root execution differs from its assignment")
            store = codex_ticket.Store(store_path)
            store.file(assignment)
            from tree_reads import scratch as session_scratch
            agents = store.snapshot()["agents"]
            resumed = agents.get(assignment.agent)
            if (resumed is not None
                    and any(item["phase"] != codex_ticket.Phase.ENDED for item in agents.values())
                    and (scratch / "codex-session").exists()):
                codex_ticket.reconcile(
                    scratch, assignment.agent, (scratch / "codex-session").read_text().strip(), home)
            token = store.reserve(assignment)
            try:
                codex_ticket.register(store.path, session_scratch(ticket_numbers.session_id()), assignment.agent)
                (scratch / "codex-dispatch.json").unlink(missing_ok=True)
            except Exception:
                store.refused(assignment.agent, token)
                raise
            admission = store, assignment, token
        try:
            return work(agent, scratch, brief, model, effort, item, root, home, main, cwd,
                        runner, agent_type, transport, thread, admission, agent_id)
        finally:
            try:
                if admission is not None:
                    store, enrolled, token = admission
                    failures = scratch / "codex-launch-failures.jsonl"
                    reserved = store.snapshot()["agents"][enrolled.agent]["reserved"]
                    proved_refused = (failures.exists() and any(
                        json.loads(line)["started"] >= reserved for line in failures.read_text().splitlines()))
                    if proved_refused and store.snapshot()["agents"][enrolled.agent]["phase"] == codex_ticket.Phase.RESERVED:
                        store.refused(enrolled.agent, token)
                    elif (scratch / "codex-session").exists():
                        native = (scratch / "codex-session").read_text().strip()
                        codex_ticket.reconcile(scratch, enrolled.agent, native, home)
            finally:
                done.touch()


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
    parser.add_argument("--agent-id")
    parser.add_argument("--resume", action="store_true",
                        help="continue the saved thread; required for later turns")
    parser.add_argument("--operator")
    parser.add_argument("--subject")
    parser.add_argument("--identity")
    parser.add_argument("--report", type=Path)
    parser.add_argument("--store", type=Path)
    return parser


def work_args(argv: list[str]) -> argparse.Namespace | None:
    """The arguments `main` runs a turn with, or None where `argv` is a control
    call or `main` exits before its turn (help, or arguments its parser refuses)."""
    if argv and argv[0] in (*CONTROLS, "enrollment"):
        return None
    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
        try:
            return work_parser().parse_args(argv)
        except SystemExit:
            return None


def enrollment(identity: str) -> dict[str, str]:
    """Read root enrollment data from the operator's filed Claude launch."""
    from entry_reads import entries_forward
    from filed_texts import brief_report_file
    from operations.roles import described
    from report_file_hook import brief
    from run_reads import agent_type, parent_id, read_meta, session_of
    from transcripts import find
    from tree_reads import scratch

    path = find(identity)
    operator = parent_id(path)
    if agent_type(find(operator)) != Role.OPERATOR.agent_type:
        raise ValueError("root's owning agent is not an operator")
    description = described((read_meta(path) or {})["description"])
    if description is None:
        raise ValueError("root launch has no operations role and subject")
    undecided: list[str] = []
    text = brief(entries_forward(path), "root enrollment", undecided)
    report = brief_report_file(text) if text is not None else None
    if undecided or report is None:
        raise ValueError("root launch has no readable filed brief and report")
    return {"operator": operator, "subject": description.subject, "identity": identity,
            "role": description.role.value,
            "report": str(report), "store": str(scratch(session_of(path).name) / "codex-tickets" / identity)}


def main(argv: list[str]) -> int:
    if argv and argv[0] == "enrollment":
        parser = argparse.ArgumentParser()
        parser.add_argument("action", choices=("enrollment",))
        parser.add_argument("identity")
        args = parser.parse_args(argv)
        try:
            print(json.dumps(enrollment(args.identity)))
            return 0
        except (OSError, ValueError, KeyError) as exc:
            parser.exit(1, f"codex_agent: {exc}\n")
    if argv and argv[0] in CONTROLS:
        try:
            return control(argv)
        except (OSError, ValueError) as exc:
            print(f"codex_agent: {exc}", file=sys.stderr)
            return 1
    args = work_parser().parse_args(argv)
    enrollment_fields = (args.operator, args.subject, args.identity, args.report, args.store)
    if any(value is not None for value in enrollment_fields) and not all(value is not None for value in enrollment_fields):
        raise ValueError("enrollment requires --operator, --subject, --identity, --report and --store")
    try:
        item = input_text()
    except (OSError, ValueError) as exc:
        print(f"codex_agent: {exc}", file=sys.stderr)
        return 1
    try:
        assignment = None
        if args.store is not None:
            from codex_reports import digest
            expected = enrollment(args.identity)
            supplied = {"operator": args.operator, "subject": args.subject,
                        "role": args.agent, "report": str(args.report.resolve()),
                        "store": str(args.store.resolve())}
            if any(supplied[key] != expected[key] for key in supplied):
                raise ValueError("root enrollment differs from the owning operator's filed launch")
            manifests = (args.store / "assignments").glob(f"{args.identity}-*.json")
            revision = max((int(path.stem.rsplit("-", 1)[1]) for path in manifests), default=0) + 1
            inputs = args.store / "inputs"
            inputs.mkdir(parents=True, exist_ok=True)
            filed_brief = inputs / f"{args.identity}-{revision}-root.txt"
            with filed_brief.open("x") as output:
                output.write(item if args.resume else
                             "\n\n".join(filter(None, [args.brief.read_text(), item])))
            assignment = codex_ticket.Assignment(args.subject, args.operator, args.identity,
                Role(args.agent), revision, args.cwd.resolve(), filed_brief.resolve(),
                args.scratch.resolve(), args.report.resolve(), digest(filed_brief.read_bytes()),
                subject=args.subject, agent_type=args.agent_type or Role(args.agent).agent_type,
                model=args.model, effort=ReasoningEffort(args.effort))
        message = run(args.agent, args.scratch, assignment.brief if assignment else args.brief, args.model, args.effort,
                      "" if assignment else item, checkout.ROOT, Path.home(),
                      checkout.main_worktree(checkout.ROOT), args.cwd.resolve(),
                      agent_type=args.agent_type, resume=args.resume,
                      assignment=assignment, store_path=args.store, agent_id=args.agent_id)
        if assignment is not None:
            dispatch = args.scratch / "codex-dispatch.json"
            outcome = json.loads(dispatch.read_text())["outcome"] if dispatch.exists() else "finished"
            accepted = codex_ticket.accept(args.scratch, assignment.agent, Path.home(), outcome)
    except (OSError, ValueError) as exc:
        if isinstance(exc, TurnFailed) and exc.message:
            print(exc.message, flush=True)
        print(f"codex_agent: {exc}", file=sys.stderr)
        return 1
    else:
        value = accepted["dispatch"] if assignment is not None and accepted["outcome"] == "needs-operator" else {}
        if assignment is not None and value.get("call"):
            value["report"] = str(assignment.report)
            print(json.dumps(value), flush=True)
            return 0
        print(message, end="" if message.endswith("\n") else "\n", flush=True)
        return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
