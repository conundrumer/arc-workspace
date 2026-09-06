"""Start claude with the handbook: appended to the session's system
prompt, and after each agent definition under .claude/agents/, so neither the
session nor its agents read it themselves. Arguments pass through to claude.

    uv run python scripts/claude.py [claude args]
"""

import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "console"))

from dl.context import render  # noqa: E402
from solver_console import config, prompts  # noqa: E402


def main() -> None:
    text = render(config.DOCS)
    digest = hashlib.sha1(text.encode()).hexdigest()[:10]
    path = config.STATE_DIR / f"handbook-{digest}.md"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    cmd = [config.CLAUDE, "--append-system-prompt", text]
    agents = prompts.worker_agents(str(path))
    if agents:
        # An agent whose body does not open on the docs does not carry them.
        defs = json.loads(agents)
        for agent in defs.values():
            if "when the handbook does not follow this section" not in agent["prompt"]:
                agent["prompt"] = agent["prompt"].removesuffix("\n\n" + text)
        cmd += ["--agents", json.dumps(defs)]
    cmd += sys.argv[1:]
    os.execvp(cmd[0], cmd)


if __name__ == "__main__":
    main()
