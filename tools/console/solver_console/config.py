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
DEBRIEF_FILE = STATE_DIR / "debrief.json"
SOLVERS = ROOT / "programs" / "solvers"
LIB = ROOT / "programs" / "lib.dl"
DOCS = ROOT / "docs" / "wf-solver"
TASKS = ROOT / "data" / "tasks"
AGENT_DIR = ROOT / ".claude" / "agents"
REF_DIR = (ROOT.parent / "arc-synth-bun").resolve()
QUEUE_CACHE = ROOT / "scripts" / ".queue-cache"

# The Claude home the workers run under: the account they are logged into,
# their transcripts, and the usage cache the pacer reads. A home of its own
# keeps the console's account apart from the user's own sessions, so neither
# spends the other's windows. The console's account logs in there once, with
# `CLAUDE_CONFIG_DIR=<home> claude` and `/login`, spelled the same way as here:
# the keychain entry is keyed by the path string.
CLAUDE_HOME = Path(os.environ.get("CONSOLE_CLAUDE_HOME",
                                  Path.home() / ".claude-console"))
PROJECTS = CLAUDE_HOME / "projects"   # the CLI's transcripts, one per session
# The account's rate-limit windows: the OAuth usage API cache the fetch
# script writes, and the file the statusline of an interactive session in
# that home writes from its own responses, which is the fresher of the two
# while such a session is open.
USAGE_API = CLAUDE_HOME / "usage-api.json"
USAGE_STATUS = CLAUDE_HOME / "usage.json"
USAGE_FETCH = Path.home() / ".claude" / "scripts" / "fetch-usage-api.sh"
# Seconds between usage fetches. The usage endpoint rate-limits a token that
# asks about once a minute; see quota.fetch for the pause a refusal earns.
USAGE_POLL = 120

FAKE = os.environ.get("CONSOLE_FAKE") == "1"
CLAUDE = os.environ.get("CONSOLE_CLAUDE", "claude")
# The models the pipeline settings pick between, under the names the console
# shows for them.
MODEL_IDS = {"opus": os.environ.get("CONSOLE_OPUS_MODEL", "claude-opus-5"),
             "fable": os.environ.get("CONSOLE_FABLE_MODEL", "claude-fable-5")}
# What each settable stage runs until the user sets it. The finalize pass has
# no setting: it is the fable read.
PIPELINE_DEFAULTS = {"create": "opus", "refine": "opus"}
FINALIZE_MODEL = "fable"
# The console's automatic moves, off until the user turns them on. `finalize`
# lets a wave item hand itself into the finalize stage; `compact` compacts an
# unapproved finalize session before its cache goes cold or its worker is
# reaped; `compact_landing` compacts a finalize session the autopilot opened
# as soon as its callouts land, while the account can still afford the turn.
AUTO_DEFAULTS = {"finalize": False, "compact": False, "compact_landing": False}
# What a claude stage runs at when its chain names no effort; it overrides
# the per-model default in the user's settings.
CLAUDE_EFFORT = os.environ.get("CONSOLE_CLAUDE_EFFORT", "high")
COMMIT_MODEL = os.environ.get("CONSOLE_COMMIT_MODEL", "claude-opus-5")
# What a stage moves to when its model's safeguards refuse a report ask twice
# over. A report summarizes the transcript, so a smaller model writes it.
REFUSAL_MODEL = os.environ.get("CONSOLE_REFUSAL_MODEL", "claude-sonnet-5")

# CLAUDE_CONFIG_DIR puts the worker in the console's home. A home of its own
# carries none of the user's settings, so worker-settings.json restates the
# ones a worker needs. The user's global prompt hook checks CLAUDE_NO_HEADLINE
# and stays quiet for workers, for a console run in the user's own home.
# The task tools are off by default for the worker models, so the cadence's
# "a task per step" had nothing to call. They arrive deferred: the worker
# reaches them through ToolSearch, and the init event lists them, so they also
# have to sit in WORKER_TOOLS.
WORKER_ENV = {**os.environ, "CLAUDE_CONFIG_DIR": str(CLAUDE_HOME),
              "CLAUDE_NO_HEADLINE": "1",
              "CLAUDE_CODE_ENABLE_TODO_TOOLS": "1"}

WORKER_FLAGS = [
    "--output-format", "stream-json", "--input-format", "stream-json", "--verbose",
    "--permission-mode", "auto",
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
    # Allow rules resolve before the classifier, so the calls workers make
    # constantly skip its round-trip.
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
# The prompt-cache TTL, counted from a session's last landing.
CACHE_TTL = 3600
# How close to the cache expiry, or the idle reap, the auto compact fires.
COMPACT_MARGIN = 180
# How long a handoff held for a background task waits. A subagent survey takes
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
COMMIT_TIMEOUT = 900  # seconds a committer session may run
COMMITTER_FLAGS = [
    # The stream feeds the committer panel, so a run in progress can be read.
    "--output-format", "stream-json", "--verbose",
    "--allowedTools", "Bash(git status:*)", "Bash(git diff:*)", "Bash(git log:*)",
    "Bash(git show:*)", "Bash(git add:*)", "Bash(git commit:*)",
    "Bash(git restore:*)",
    # untracked_note.py holds the scope the brief states: the console commits
    # the approved solvers itself, so a file git does not track yet is one
    # nobody approved. Restoring the index is how the committer answers a
    # refusal, so that call is allowed too.
    "--settings", str(HERE / "committer-settings.json"),
    "--add-dir", str(REF_DIR),
    "--exclude-dynamic-system-prompt-sections",
]
