"""The names of the readers the `context` command knows. The PreToolUse
hooks name a reader by them, so this module imports only the standard
library."""

from enum import StrEnum


class ReaderName(StrEnum):
    """The name of a reader the `context` command knows, as its command
    line gives it."""

    COORDINATOR = "coordinator"
    USER_SESSION = "user-session"
    SESSION = "session"
    CODEX = "codex"
    AGENT = "agent"
    ROLE = "role"
    WORKFLOW = "workflow"
    FRAGMENTS = "fragments"
