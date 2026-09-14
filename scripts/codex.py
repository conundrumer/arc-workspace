"""Start codex with the handbook in its context, for prose edits. Arguments
pass through to codex.

    uv run python scripts/codex.py [codex args]

The session runs under its own Codex home, `.codex/`, written here on each
start: the handbook and the project CLAUDE.md as its AGENTS.md, and
`docs/codex-style.md` as its developer instructions, without its HTML
comments. The user's Codex home
supplies the login and the model choice, and nothing else.
"""

import json
import os
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

from dl.context import render  # noqa: E402

USER_HOME = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
HOME = ROOT / ".codex"
STYLE = ROOT / "docs" / "codex-style.md"
CLAUDE_MD = ROOT / "CLAUDE.md"
# The keys of the user's config that the session keeps.
KEPT = ("model", "model_reasoning_effort")
# The project-doc budget; the default truncates the handbook silently.
DOC_BYTES = 1 << 20


def uncommented(text: str) -> str:
    """The text without its HTML comments. A comment that fills whole lines
    takes those lines with it; an inline one takes the space before it."""
    text = re.sub(r"^[ \t]*<!--.*?-->[ \t]*\n", "", text, flags=re.S | re.M)
    return re.sub(r" ?<!--.*?-->", "", text, flags=re.S)


def config(user: dict) -> str:
    kept = {k: user[k] for k in KEPT if k in user}
    kept["developer_instructions"] = uncommented(STYLE.read_text())
    kept["project_doc_max_bytes"] = DOC_BYTES
    # json.dumps gives a TOML basic string: the escapes agree on these
    # values.
    lines = [f"{k} = {json.dumps(v)}" for k, v in kept.items()]
    lines += ["", f"[projects.{json.dumps(str(ROOT))}]", 'trust_level = "trusted"', ""]
    return "\n".join(lines)


def main() -> None:
    with open(USER_HOME / "config.toml", "rb") as f:
        user = tomllib.load(f)
    HOME.mkdir(exist_ok=True)
    (HOME / "AGENTS.md").write_text(render() + "\n---\n\n# CLAUDE.md\n\n" + CLAUDE_MD.read_text())
    (HOME / "config.toml").write_text(config(user))
    auth = HOME / "auth.json"
    if not auth.exists():
        auth.symlink_to(USER_HOME / "auth.json")
    os.environ["CODEX_HOME"] = str(HOME)
    os.execvp("codex", ["codex", "-C", str(ROOT), *sys.argv[1:]])


if __name__ == "__main__":
    main()
