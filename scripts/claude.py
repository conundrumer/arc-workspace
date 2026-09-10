"""Start claude with the handbook appended to the session's system prompt,
after writing the handbook agent that a spawned role runs under. Arguments
pass through to claude.

    uv run python scripts/claude.py [claude args]
"""

import hashlib
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "console"))

from dl.context import render, write_agent  # noqa: E402
from solver_console import config  # noqa: E402


def main() -> None:
    write_agent()
    text = render()
    digest = hashlib.sha1(text.encode()).hexdigest()[:10]
    path = config.STATE_DIR / f"handbook-{digest}.md"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    os.execvp(config.CLAUDE, [config.CLAUDE, "--append-system-prompt-file", str(path),
                              *sys.argv[1:]])


if __name__ == "__main__":
    main()
