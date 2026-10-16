"""The subagent path test, and the name of the subagents directory.

A hook imports this module, and a hook runs in a fresh process, so this
module imports only the standard library."""

from os import PathLike
from pathlib import PurePath

SUBAGENTS = "subagents"
"""The directory, under a session's, whose tree holds the session's
subagent transcripts, each named `agent-*.jsonl`."""


def is_subagent(path: str | PathLike[str]) -> bool:
    return SUBAGENTS in PurePath(path).parts
