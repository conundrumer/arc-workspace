"""Run one Codex session over a retro brief and print its final message.

    uv run python scripts/retro_codex.py --label <label> --schema <json> < brief.md

The brief comes in on stdin. The script writes it to
`.scratch/retro/briefs/<label>.md`, writes the schema to
`.scratch/retro/briefs/edit-schema.json`, runs `scripts/context.py --write` so
`AGENTS.md` holds the current handbook, and then runs `codex exec` once from
the repo root with the brief on stdin and that schema as the shape of the
final message. Codex writes that message to `.scratch/retro/codex/<label>.json`
and the script prints it.

A label carries a stage name and a count, such as `fix:prose:1/3`. A character
a file name cannot take folds to `-`, so that label names the files
`fix-prose-1-3.md` and `fix-prose-1-3.json`.

The model takes a strict schema alone: every object forbids further properties
and requires each one it names. The script strictifies the schema it is given.

Exit status: 0 when Codex left a final message, 1 when it left none, 2 when
the call itself is malformed.
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
BRIEF_DIR = Path(".scratch") / "retro" / "briefs"
OUT_DIR = Path(".scratch") / "retro" / "codex"
SCHEMA_NAME = "edit-schema.json"
CODEX = os.environ.get("RETRO_CODEX", "codex")
# Bytes of a failed run's output kept for the caller's report.
TAIL = 2000


def safe(label: str) -> str:
    """The label as one file name."""
    return re.sub(r"[^A-Za-z0-9._-]+", "-", label).strip("-") or "unit"


def strict(schema: Any) -> Any:
    """The schema as the model takes it, every object closed and complete."""
    if isinstance(schema, list):
        items: list[Any] = schema
        return [strict(item) for item in items]
    if isinstance(schema, dict):
        fields: dict[str, Any] = schema
        out: dict[str, Any] = {key: strict(value) for key, value in fields.items()}
        props = out.get("properties")
        if isinstance(props, dict):
            named: dict[str, Any] = props
            out["additionalProperties"] = False
            out["required"] = list(named)
        return out
    return schema


def write_whole(path: Path, text: str) -> Path:
    """Write a file whole, so a reader opening it while the write is in
    progress reads the old file or the new one. Two units of one round write
    the same schema file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(f".{os.getpid()}.tmp")
    try:
        tmp.write_text(text)
        tmp.replace(path)
    finally:
        tmp.unlink(missing_ok=True)
    return path


def prepare(root: Path, label: str, brief: str, schema: Any) -> tuple[Path, Path, Path]:
    """Write the brief and the schema, and return the brief, the schema, and
    the path the final message goes to, each under `root`."""
    name = safe(label)
    brief_path = write_whole(root / BRIEF_DIR / f"{name}.md", brief)
    schema_path = write_whole(root / BRIEF_DIR / SCHEMA_NAME,
                              json.dumps(strict(schema), indent=2) + "\n")
    out_path = root / OUT_DIR / f"{name}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.unlink(missing_ok=True)
    return brief_path, schema_path, out_path


def codex_argv(root: Path, schema: Path, out: Path, model: str | None = None,
               effort: str | None = None, codex: str = CODEX) -> list[str]:
    """The Codex call: the repo as the working root, the schema as the shape
    of the final message, and the brief on stdin."""
    cmd = [codex, "exec", "-C", str(root),
           "--output-schema", str(schema), "-o", str(out),
           "-c", 'approval_policy="never"']
    if model:
        cmd += ["--model", model]
    if effort:
        cmd += ["-c", f'model_reasoning_effort="{effort}"']
    return [*cmd, "-"]


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--label", required=True, help="the name of this unit of work")
    ap.add_argument("--schema", required=True, help="the shape of the final message, as JSON")
    ap.add_argument("--model", help="the Codex model; its own default when absent")
    ap.add_argument("--effort", help="the Codex reasoning effort; its own default when absent")
    ap.add_argument("--codex", default=CODEX, help="the codex binary")
    ap.add_argument("--root", type=Path, default=REPO_ROOT, help="the repo root")
    return ap


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    brief = sys.stdin.read()
    if not brief.strip():
        print("retro_codex: the brief on stdin is empty", file=sys.stderr)
        return 2
    try:
        schema: Any = json.loads(args.schema)
    except ValueError as exc:
        print(f"retro_codex: --schema is not JSON: {exc}", file=sys.stderr)
        return 2
    root: Path = args.root
    _, schema_path, out_path = prepare(root, args.label, brief, schema)
    handbook = subprocess.run([sys.executable, "scripts/context.py", "--write"],
                              cwd=root, capture_output=True, text=True)
    if handbook.returncode != 0:
        print(f"retro_codex: scripts/context.py --write failed:\n{handbook.stderr[-TAIL:]}",
              file=sys.stderr)
        return 2
    run = subprocess.run(codex_argv(root, schema_path, out_path, args.model,
                                    args.effort, args.codex),
                         cwd=root, input=brief, capture_output=True, text=True)
    text = out_path.read_text() if out_path.exists() else ""
    if not text.strip():
        print(f"retro_codex: codex exited with {run.returncode} and left no final message\n"
              f"{(run.stdout + run.stderr)[-TAIL:]}", file=sys.stderr)
        return 1
    sys.stdout.write(text if text.endswith("\n") else text + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
