"""Check that `StudyTaskEvaluator.gold_tables` gives the same tables with and without the form cache, and time both.

    python scripts/check_gold_form_cache.py TASK PROGRAM_FILE [PROGRAM_FILE ...] [--tasks DIR] [--work-cap N] [--order forward|reverse] [--form-cache-bytes N]

Each PROGRAM_FILE holds one program as an S-expression. For each program, in the order given, the check calls
`gold_tables` in two evaluators of the task, one made with `form_cache=False` and one with `form_cache=True`, each
reused across the programs. It prints, for each program, the seconds of each call, the status of the tables, and
whether a digest of the packed tables (every column of `tables`, `entries`, `assigned` and `values`) and of the status
(less its timings and references) is equal in the two. It prints the cache's counts after the last call, and the
sum of the seconds of each evaluator. It exits 1 where any digest differs. It prints ids, counts and digests, and no
table content.

This check tracks the form cache, an in-progress feature: delete it when the feature is done.
"""

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

# scripts/arclog.py would shadow the engine package, so the directory of this file stays off the module path.
sys.path = [p for p in sys.path if Path(p or ".").resolve() != Path(__file__).resolve().parent]

import arclog  # noqa: E402

# largest_counts gives the work that ran, which a walk taken from the form cache does not do.
VOLATILE = {"tables_ref", "cached", "form_cache", "native_columns_seconds", "timings", "snapshot_ref", "largest_counts"}


def stable(value):
    """The status with no timing and no reference to a snapshot."""
    if isinstance(value, dict):
        return {k: stable(v) for k, v in sorted(value.items()) if k not in VOLATILE and not k.endswith("_seconds")}
    if isinstance(value, list):
        return [stable(v) for v in value]
    return value


def digest_columns(tables):
    """A digest of every column of the packed tables."""
    digest = hashlib.sha256()
    for part in ("tables", "entries", "assigned"):
        columns = getattr(tables, part)
        for key in sorted(columns):
            value = columns[key]
            digest.update(f"{part}.{key}:".encode())
            if isinstance(value, (bytes, bytearray, memoryview)):
                digest.update(bytes(value))
            else:
                digest.update(json.dumps(list(value), default=str).encode())
    values = tables.values
    digest.update(bytes(values) if isinstance(values, (bytes, bytearray, memoryview)) else json.dumps(list(values)).encode())
    return digest.hexdigest()[:16]


def run(task, tasks, settings, programs, form_cache, form_cache_bytes=None):
    extra = {} if form_cache_bytes is None else {"form_cache_bytes": form_cache_bytes}
    evaluator = arclog.StudyTaskEvaluator(task, tasks, settings, form_cache=form_cache, **extra)
    rows = []
    for text in programs:
        program = arclog.StudyProgram.from_sexp(text, settings)
        started = time.monotonic()
        status, tables = evaluator.gold_tables(program)
        seconds = time.monotonic() - started
        report = json.loads(status)
        rows.append(
            dict(
                seconds=seconds,
                status=report.get("status"),
                tables=digest_columns(tables),
                report=hashlib.sha256(json.dumps(stable({k: v for k, v in report.items() if k != "packed_correspondence"}), sort_keys=True).encode()).hexdigest()[:16],
                form_cache=report.get("form_cache"),
            )
        )
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("task")
    parser.add_argument("programs", nargs="+")
    parser.add_argument("--tasks", default="data/tasks")
    parser.add_argument("--work-cap", type=int, default=None)
    parser.add_argument("--form-cache-bytes", type=int, default=None)
    parser.add_argument("--order", choices=["forward", "reverse"], default="forward")
    args = parser.parse_args()
    paths = list(args.programs)
    if args.order == "reverse":
        paths.reverse()
    programs = [Path(path).read_text() for path in paths]
    settings = arclog.DecodeSettings() if args.work_cap is None else arclog.DecodeSettings(table_work_cap=args.work_cap)
    tasks = str(Path(args.tasks).resolve())
    off = run(args.task, tasks, settings, programs, False)
    on = run(args.task, tasks, settings, programs, True, args.form_cache_bytes)
    differs = 0
    for i, (a, b) in enumerate(zip(off, on)):
        same = a["status"] == b["status"] and a["tables"] == b["tables"] and a["report"] == b["report"]
        differs += not same
        print(f"program {i}: off {a['seconds']:.2f}s on {b['seconds']:.2f}s status {a['status']}/{b['status']} tables {a['tables']}/{b['tables']} report {a['report']}/{b['report']} {'equal' if same else 'DIFFERENT'}")
    print(f"total: off {sum(r['seconds'] for r in off):.2f}s on {sum(r['seconds'] for r in on):.2f}s")
    print(f"form cache after the last program: {json.dumps(on[-1]['form_cache'])}")
    print(f"{differs} of {len(off)} programs differ")
    sys.exit(1 if differs else 0)


main()
