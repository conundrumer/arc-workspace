"""Run one checklist item in the agent's Codex session.

    uv run python scripts/codex_agent.py <agent> <scratch> <brief> <model> <effort> [--cwd <dir>]

Give the item or a later message on stdin. The first call reads the rendered
agent document, the repo and user CLAUDE.md files, and the brief. Later
calls resume the thread in <scratch>/codex-session with only the new input.
`--cwd` sets the directory Codex works in, defaulting to the current directory.
The last message is printed; a failed turn prints its error and exits 1.
"""

import argparse
import json
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from controlled_markdown import mctx
from engine import checkout
from operations.roles import CODEX_ROLES

DONE = "codex-done"
"""The file under the scratch directory that the command makes once it ends,
which the Codex launcher's foreground wait checks for."""

PREAMBLE = mctx(
    "You do the work of one item of your agent's checklist at a time, given "
    "by a Claude agent. That agent runs `step.py`, makes every Agent call "
    "and SendMessage, and gives the final reply. Run no `step.py`; you have "
    "no Agent or SendMessage tool. Where your documents tell you to launch "
    "an agent, send a message or give a final reply, end your turn and tell "
    "the Claude agent what to do, with the full text to send. The Claude "
    "agent also runs `operate.py review` in its own foreground Bash call "
    "where your documents give that command; ask it for the result. It "
    "gives you the results and messages in later turns. The Codex mode "
    "procedure is for that Claude agent; do not run `codex_agent.py` yourself. "
    "End each turn with what you did on the item and anything left unfinished, "
    "with why.")


def without_front(text: str) -> str:
    """Remove the rendered document's leading YAML front matter."""
    lines = text.splitlines(keepends=True)
    if lines and lines[0].strip() == "---":
        for i, line in enumerate(lines[1:], 1):
            if line.strip() == "---":
                return "".join(lines[i + 1:]).lstrip("\n")
        raise ValueError("agent document has unclosed front matter")
    return text


def first_prompt(root: Path, home: Path, agent: str, brief: Path, item: str) -> str:
    user = home / ".claude" / "CLAUDE.md"
    return "\n\n".join([
        PREAMBLE, without_front((root / ".claude" / "agents" / f"{agent}.md").read_text()),
        (root / "CLAUDE.md").read_text(), *([user.read_text()] if user.exists() else []),
        brief.read_text(), item])


def execute(argv: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True, text=True)


def error_text(event: dict[str, Any]) -> str:
    """The message of a CLI error event, including a nested turn error."""
    error = event.get("error", event)
    return str(error.get("message", error)) if isinstance(error, dict) else str(error)


def run(agent: str, scratch: Path, brief: Path, model: str, effort: str, item: str,
        root: Path, home: Path, main: Path, cwd: Path,
        runner: Callable[[list[str]], subprocess.CompletedProcess[str]] = execute) -> str:
    """Return the last message, or raise with the CLI's error. Save a thread
    id even on failure so a later call can continue the same session."""
    scratch = scratch.resolve()
    scratch.mkdir(parents=True, exist_ok=True)
    session = scratch / "codex-session"
    thread = session.read_text().strip() if session.exists() else None
    if thread == "":
        raise ValueError(f"{session}: empty session id")
    prompt = item if thread is not None else first_prompt(root, home, agent, brief, item)
    last = scratch / "codex-last.md"
    last.unlink(missing_ok=True)
    git_dir = Path(checkout.git_out(cwd, "rev-parse", "--absolute-git-dir").strip())
    # The repository's commands write the main tree's tickets, git data and
    # caches, and uv's and cargo's caches, from any worktree. Codex keeps the
    # git dir of a worktree it runs in read-only unless that dir is a root.
    writable = [main / "tickets", main / ".git",
                *([git_dir] if git_dir != main / ".git" else []), main / ".cache",
                home / ".cache" / "uv", home / ".cargo", scratch]
    argv = ["codex", "exec", "-m", model, "-c", f'model_reasoning_effort="{effort}"',
            "-c", "project_doc_max_bytes=0", "-s", "workspace-write",
            "-c", "sandbox_workspace_write.network_access=true",
            "-c", 'approval_policy="never"', *(a for d in writable for a in ("--add-dir", str(d))),
            "--skip-git-repo-check", "-C", str(cwd), "-o", str(last), "--json"]
    done = runner([*argv, *(["resume", thread] if thread is not None else []), prompt])
    errors: list[str] = []
    for line in done.stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        if thread is None and isinstance(found := event.get("thread_id"), str) and found:
            thread = found
            session.write_text(thread + "\n")
        if event.get("type") in ("error", "turn.failed", "usage_limit"):
            errors.append(error_text(event))
        elif event.get("type") == "item.completed" and isinstance(event.get("item"), dict):
            if event["item"].get("type") == "error":
                errors.append(error_text(event["item"]))
    message = last.read_text() if last.exists() else ""
    if done.returncode or errors or not message.strip() or thread is None:
        details = "\n".join([*errors, done.stderr.strip()]).strip()
        raise ValueError(details or
                         f"codex exec exited {done.returncode} with no last message or thread id")
    return message


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("agent", choices=sorted(r.value for r in CODEX_ROLES))
    parser.add_argument("scratch", type=Path)
    parser.add_argument("brief", type=Path)
    parser.add_argument("model")
    parser.add_argument("effort", choices=("low", "medium", "high", "xhigh"))
    parser.add_argument("--cwd", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    done = args.scratch / DONE
    done.unlink(missing_ok=True)
    try:
        message = run(args.agent, args.scratch, args.brief, args.model, args.effort,
                      sys.stdin.read(), checkout.ROOT, Path.home(),
                      checkout.main_worktree(checkout.ROOT), args.cwd.resolve())
    except (OSError, ValueError) as exc:
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
