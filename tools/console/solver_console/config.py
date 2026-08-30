"""Paths, environment settings, and the flags the console launches
workers with."""

import os
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
STATE_DIR = Path(os.environ.get("CONSOLE_STATE_DIR", HERE / "state"))
STATE_FILE = STATE_DIR / "state.json"
APPROVED_FILE = STATE_DIR / "approved.txt"
SAMPLE_FILE = STATE_DIR / "usage-samples.jsonl"
LOG_DIR = STATE_DIR / "logs"
REPORT_DIR = STATE_DIR / "reports"
LEDGER = REPORT_DIR / "ledger.jsonl"
FLAGS_FILE = STATE_DIR / "flags.json"
SOLVERS = ROOT / "programs" / "solvers"
LIB = ROOT / "programs" / "lib.dl"
DOCS = ROOT / "docs" / "wf-solver"
TASKS = ROOT / "data" / "tasks"
AGENT_DIR = ROOT / ".claude" / "agents"
REF_DIR = (ROOT.parent / "arc-synth-bun").resolve()

FAKE = os.environ.get("CONSOLE_FAKE") == "1"
CLAUDE = os.environ.get("CONSOLE_CLAUDE", "claude")
MODELS = {"create": os.environ.get("CONSOLE_CREATE_MODEL", "claude-opus-5"),
          "refine": os.environ.get("CONSOLE_REFINE_MODEL", "claude-fable-5")}
CODEX_MODEL = os.environ.get("CONSOLE_CODEX_MODEL", "gpt-5.6-sol")
CODEX_EFFORT = os.environ.get("CONSOLE_CODEX_EFFORT", "high")
COMMIT_MODEL = os.environ.get("CONSOLE_COMMIT_MODEL", "claude-opus-5")

# The user's global prompt hook checks this and stays quiet for workers.
# The task tools are off by default for the worker models, so the cadence's
# "a task per step" had nothing to call. They arrive deferred: the worker
# reaches them through ToolSearch, and the init event lists them, so they also
# have to sit in WORKER_TOOLS.
WORKER_ENV = {**os.environ, "CLAUDE_NO_HEADLINE": "1",
              "CLAUDE_CODE_ENABLE_TODO_TOOLS": "1"}

WORKER_FLAGS = [
    "--output-format", "stream-json", "--input-format", "stream-json", "--verbose",
    "--permission-mode", "acceptEdits",
    # ref_note.py hooks in to note reads of unratified solvers, and
    # includeGitInstructions drops the git status block: it is rebuilt at
    # every spawn, so a resume that follows a commit or a solver write would
    # otherwise miss the cache on everything after the static prompt.
    # Both hook commands there address their script through
    # CLAUDE_PROJECT_DIR and skip a script they cannot find. A hook runs in
    # the shell's tracked cwd, which a worker's own `cd` moves, and python3
    # leaves the same exit code for a missing file as the protocol reads as
    # a block — so a relative path turns one `cd` into every later Bash call
    # refused, the `cd` back among them.
    "--settings", str(HERE / "worker-settings.json"),
    "--allowedTools",
    "Bash(uv run:*)", "Bash(cat:*)", "Bash(ls:*)", "Bash(souffle:*)",
    # Schemas a solver session never calls, kept out of the request. ToolSearch
    # stays: without it every deferred tool loads, which costs more than the
    # rest of this list saves. Dropping a name from here adds it to
    # WORKER_TOOLS. Denying Skill also drops the skill listing, which the
    # appendix already carries; `--disable-slash-commands` saves the same
    # tokens but takes `/compact` with it.
    "--disallowedTools",
    "AskUserQuestion", "CronCreate", "CronDelete", "CronList", "DesignSync",
    "EnterPlanMode", "EnterWorktree", "ExitPlanMode", "ExitWorktree",
    "ListAgents", "NotebookEdit", "PushNotification",
    "RemoteTrigger", "ReportFindings", "ScheduleWakeup", "Skill",
    "WebFetch", "WebSearch", "Workflow",
    "--add-dir", str(REF_DIR),
    "--exclude-dynamic-system-prompt-sections",
    # The claude.ai connectors are unauthenticated here and cost nothing while
    # they stay deferred. This holds them out whatever the deferral does.
    "--strict-mcp-config",
    # Permission prompts come to the console over the same pipe as the stream,
    # where answer_permission settles them. Without this the CLI has no one to
    # ask and refuses on its own.
    "--permission-prompt-tool", "stdio",
]
# What those flags leave loaded. A release that adds a tool lands it in the
# worker's context, and a denylist cannot know its name, so the init event is
# checked against this set and the difference goes to the feed. Dropping a name
# from here adds it to the denylist above.
WORKER_TOOLS = {"Task", "Bash", "Edit", "Monitor", "Read", "SendMessage",
                "TaskCreate", "TaskGet", "TaskList", "TaskOutput", "TaskStop",
                "TaskUpdate", "ToolSearch", "Write"}
STAGGER_TIMEOUT = 120  # seconds to wait for the first worker's first API response
# A worker holds its process for as long as it sits idle. Past the prompt
# cache, that process buys nothing a resume would not: the chain gives each
# phase its own session, so a worker that has reported is only ever woken by a
# review comment.
# How long a message written into a running turn stays the explanation for a
# turn the worker starts next. Past it the turn absorbed the message, and an
# init that follows belongs to something else.
STEER_RACE = 5
IDLE_TTL = 3600
IDLE_POLL = 60
# How long a handoff held for a background task waits. A subagent sweep takes
# minutes; past this the task is treated as one that never reports, and the
# stage lands with no report for the user to rule on.
BG_TTL = 1200
# Autopilot leaves a landed phase's process resident, so the count climbs with
# every handoff and what the machine holds becomes the limit that matters. On
# 14 cores and 24 GB, 63 workers ran with no latency cost and memory gave out
# into swap between 74 and 80. The cap counts the running workers too, and a
# reaped worker costs only a --resume on the next comment.
NIGHT_WORKER_CAP = 30
# What a worker session is allowed to leave behind. The brief and the
# leftovers check read the same list, so widening it moves both.
COMMIT_SCOPE = ["programs", "docs/wf-solver", "src/dl", "scripts", "tests"]
COMMIT_BRIEF = f"""Commit the changes that solver workers left in the working tree.

Scope: files git already tracks, under {", ".join(p + "/" for p in COMMIT_SCOPE)}. A session that hits a gap in the runner fixes it there, so those changes belong in the same sweep. Never stage untracked files, and leave changes outside that scope alone.

Read git status and the diffs, and recent git log for message style. Group the changes into clean commits the way the log does; write each message from what the diff shows."""
COMMITTER_FLAGS = [
    "--output-format", "json",
    "--allowedTools", "Bash(git status:*)", "Bash(git diff:*)", "Bash(git log:*)",
    "Bash(git show:*)", "Bash(git add:*)", "Bash(git commit:*)",
    "--add-dir", str(REF_DIR),
    "--exclude-dynamic-system-prompt-sections",
]
