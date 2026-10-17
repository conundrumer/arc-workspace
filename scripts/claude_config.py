"""The Claude config directory, which holds the user's settings, global
`CLAUDE.md` and usage file."""

import os
from pathlib import Path


def config_dir() -> Path:
    home = os.environ.get("CLAUDE_CONFIG_DIR")
    return Path(home) if home else Path.home() / ".claude"
