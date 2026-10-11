"""Start claude with the coordinator's appendix (`coordinator_appendix`)
appended to the session's system prompt, after writing the handbook agents
that a spawned role runs under. Arguments pass through to claude.

The session this starts is the coordinator, the session the user talks
with, and it reads both that appendix and the session-start hook's text
(`handbook.coordinator_document`). Its reader is `user-session`.

    uv run python scripts/claude.py [claude args]
"""

import hashlib
import os
import sys

from handbook.paths import console_importable

console_importable()

from handbook.agents import write_agent  # noqa: E402
from handbook.context import sweep_digests  # noqa: E402
from handbook.coordinator_document import SESSION_READER_ENV, coordinator_appendix  # noqa: E402
from handbook.reader_names import ReaderName  # noqa: E402
from solver_console import config  # noqa: E402


def main() -> None:
    write_agent()
    text = coordinator_appendix()
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
    os.environ[SESSION_READER_ENV] = ReaderName.USER_SESSION
    os.execvp(config.CLAUDE, [config.CLAUDE, "--append-system-prompt-file", str(path),
                              *sys.argv[1:]])


if __name__ == "__main__":
    main()
