"""Start claude with a coordinator's appendix (`coordinator_appendix`)
appended to the session's system prompt, after writing the handbook agents
that a spawned role runs under. Arguments after the optional `--reader`
pass through to claude.

The session this starts is the coordinator, the session the user talks
with, and it reads both that appendix and the session-start hook's text
(`handbook.coordinator_document`). Its reader is `user-session`, or the
reader `--reader` gives, one of the keys of `APPENDIX_DOCS`.

    uv run python scripts/claude.py [--reader <reader>] [claude args]
"""

import hashlib
import os
import sys

from controlled_markdown import mctx
from engine import checkout
from handbook.agents import write_agent
from handbook.context import sweep_digests
from handbook.coordinator_document import (APPENDIX_DOCS, SESSION_READER_ENV,
                                           coordinator_appendix)
from handbook.reader_names import ReaderName

READER_FLAG = "--reader"


def reader_and_args(argv: list[str]) -> tuple[ReaderName, list[str]]:
    """The reader `argv` gives with a leading `--reader <reader>`, or
    `user-session`, and the arguments that pass through to claude."""
    if argv[:1] != [READER_FLAG]:
        return ReaderName.USER_SESSION, argv
    if len(argv) < 2 or argv[1] not in APPENDIX_DOCS:
        raise SystemExit(mctx("{flag} takes one of: {names}").format(
            flag=READER_FLAG, names=", ".join(APPENDIX_DOCS)))
    return ReaderName(argv[1]), argv[2:]


def main() -> None:
    reader, args = reader_and_args(sys.argv[1:])
    write_agent()
    text = coordinator_appendix(reader)
    digest = hashlib.sha1(text.encode()).hexdigest()[:10]
    path = checkout.caches() / f"handbook-{digest}.md"
    if path.exists():
        # The sweep dates a file by its mtime, and this session takes the file
        # now, so its age starts again here.
        os.utime(path)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        sweep_digests(path)
    os.environ[SESSION_READER_ENV] = reader
    os.execvp("claude", ["claude", "--append-system-prompt-file", str(path),
                         *args])


if __name__ == "__main__":
    main()
