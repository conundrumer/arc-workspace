"""Start claude with the handbook appended to the session's system prompt,
after writing the handbook agents that a spawned role runs under. Arguments
pass through to claude.

    uv run python scripts/claude.py [claude args]
"""

import hashlib
import os
import sys

from handbook.paths import console_importable

console_importable()

from handbook.agents import write_agent  # noqa: E402
from handbook.context import USER_SESSION_DOC, entry_text, sweep_digests  # noqa: E402
from solver_console import config  # noqa: E402


def main() -> None:
    write_agent()
    text = entry_text(USER_SESSION_DOC)
    digest = hashlib.sha1(text.encode()).hexdigest()[:10]
    path = config.STATE_DIR / f"handbook-{digest}.md"
    if path.exists():
        # The sweep dates a file by its mtime, and this session takes the file
        # now, so its age starts again here.
        os.utime(path)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        sweep_digests(path)
    os.execvp(config.CLAUDE, [config.CLAUDE, "--append-system-prompt-file", str(path),
                              *sys.argv[1:]])


if __name__ == "__main__":
    main()
