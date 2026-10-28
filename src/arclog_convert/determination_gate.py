"""Required native exact-record end check, shared by verification and LM export.

A passing receipt is bound to source/task/case files, native checker sources and
binary, this gate, and the mask-producing engine when used for LM admission.
A replay mask or a baseline acceptance is never a determination receipt.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from arclog_convert.train_replay import engine_digest, files_digest, private_binaries
from engine.package_fingerprint import digest_files, package_files

SCHEMA = "arclog-determination-end-check-v1"


class EndCheckFailed(ValueError):
    """A missing/incomplete/differing determination is not exportable gold."""


def mask_context() -> str:
    """Identity of the installed engine that produces the admitted masks."""
    import arclog
    package = digest_files(package_files(str(Path(arclog.__file__).parent)))
    return hashlib.sha256((arclog.streams_digest() + package + sys.version).encode()).hexdigest()


def check_unchanged(receipt: dict, gen: Path, tasks: Path) -> None:
    """Fail before publishing masks if their checked inputs changed mid-call."""
    if receipt.get("schema") != SCHEMA or receipt.get("status") != "pass":
        raise EndCheckFailed("missing successful native determination end-check receipt")
    if files_digest(receipt["task"], gen, tasks) != receipt["files"]:
        raise EndCheckFailed(f'{receipt["task"]}: checked determination inputs changed during mask export')


def validate_cached(receipts: dict, expected: dict) -> None:
    """Old pickle/chunk streams need proof from their own producing engine."""
    for task, receipt in expected.items():
        if receipts.get(task, {}).get("status") != "pass" or receipts.get(task, {}).get("proof") != receipt["proof"]:
            raise EndCheckFailed(f"{task}: cached masks lack a matching native determination end-check receipt; regenerate them")


def require(stems: list[str], gen: Path, tasks: Path, records: Path,
            context: str = "") -> dict[str, dict]:
    """Require exact native end-check success for every selected solver.

    The native CLI owns row equality, shared Ident renaming, rigid placement,
    determination completeness and faults. No Python approximation is used.
    """
    gen, tasks, records = Path(gen).resolve(), Path(tasks).resolve(), Path(records)
    sources = engine_digest()
    gate = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    records.mkdir(parents=True, exist_ok=True)
    results = {}
    start = time.monotonic()
    with private_binaries() as copy:
        binary = None
        for index, task in enumerate(dict.fromkeys(stems)):
            files = files_digest(task, gen, tasks)
            path = records / f"{task}.json"
            try:
                old = json.loads(path.read_text())
            except (FileNotFoundError, ValueError):
                old = {}
            identity = dict(schema=SCHEMA, task=task, files=files, sources=sources,
                            gate=gate, context=context)
            # A successful check of this exact source tree is reusable. Binary
            # identity is retained in the receipt; source changes never use the
            # train-replay "sources OR binary" shortcut.
            if old.get("status") == "pass" and isinstance(old.get("proof"), str) and all(old.get(k) == v for k, v in identity.items()):
                check_unchanged(old, gen, tasks)
                results[task] = old
                print(f"determination end check {index + 1}/{len(stems)} {task}: cached", flush=True)
                continue
            if binary is None:
                binary = copy("arclog-cli")
            executable, digest = binary
            env = dict(os.environ, ARCLOG_THREADS="1", RAYON_NUM_THREADS="1")
            run = subprocess.run([str(executable), "determine", str(gen), str(tasks), task],
                                 capture_output=True, text=True, env=env)
            report = run.stdout + run.stderr
            receipt = dict(identity, binary=digest,
                           status="pass" if run.returncode == 0 else "failed",
                           exit_code=run.returncode, report=report)
            if files_digest(task, gen, tasks) != files or engine_digest() != sources:
                raise EndCheckFailed(f"{task}: inputs changed during native determination end check")
            receipt["proof"] = hashlib.sha256(json.dumps(
                {**identity, "binary": digest}, sort_keys=True).encode()).hexdigest()
            temp = path.with_name(path.name + f".{os.getpid()}.tmp")
            temp.write_text(json.dumps(receipt, indent=2) + "\n")
            temp.replace(path)
            elapsed = time.monotonic() - start
            print(f"determination end check {index + 1}/{len(stems)} {task}: "
                  f'{receipt["status"]}; {elapsed:.2f}s elapsed', flush=True)
            if run.returncode:
                raise EndCheckFailed(f"{task}: native determination end check failed:\n{report}")
            results[task] = receipt
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", required=True, type=Path)
    parser.add_argument("--tasks", required=True, type=Path)
    parser.add_argument("--receipts", required=True, type=Path)
    parser.add_argument("stems", nargs="+")
    args = parser.parse_args()
    try:
        require(args.stems, args.corpus, args.tasks, args.receipts)
    except EndCheckFailed as exc:
        print(exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
