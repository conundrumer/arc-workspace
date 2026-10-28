"""Puts a fixed list of tasks through the tables export, the export's checks and the loader, with the engine under test.

    <LM venv>/bin/python -u engine/arclog-py/roundtrip_check.py [--export-python <python>] [--keep <dir>] [--from <export dir>]

Run it from the repo root, with the interpreter of the LM work's venv (the `load` stage imports `lm/encoder.py`, which imports
torch). It runs three stages and prints `PASS <stage> (<s>s)` or `FAIL <stage> (<s>s)` with the stage's output for each, and
exits 1 where any stage fails:
  export  `tables_export.py` with `--all-cases` on `TASKS`, in a temporary directory (`--keep <dir>`, which must not exist,
          writes it there instead and keeps it), by the interpreter `--export-python` gives (this one by default). Fails
          where the run exits other than 0.
  checks  `export_checks.check_export` on that export with the values of every case checked; fails on any violation and on
          any non-empty line of the export's `checks.txt`.
  load    `lm/encoder.py` `load_tables` on that export, with a cache directory in the temporary directory, `strict=True` and
          `allow_violations=False`; fails where it raises.
`--from <export dir>` skips `export` and runs the other two on that export, such as a full export or a kept one.

To test the engine of a worktree, build its `arclog` into a scratch venv that holds numpy, pandas and pyarrow, and pass that
venv's python as `--export-python`; the LM work's venv, which other runs use, stays as it is:
    cd <worktree>/engine/arclog-py && VIRTUAL_ENV=<scratch venv> CARGO_TARGET_DIR=<scratch target> uvx maturin develop --release
"""
import argparse, io, os, subprocess, sys, tempfile, time, traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(HERE), str(ROOT / "lm")]

# The tasks whose cases the Evidence of the named tickets gives, less a64e4611 (20-146, 20-150; its export takes about 80 s)
# and a8d7556c (20-153; about 112 s), whose exports take over 20 s.
TASKS = [
    "007bbfb7",  # 20-130
    "00576224", "0becf7df",  # 20-134
    "b9e38dc0",  # 20-146, 20-150
    "4c177718",  # 20-149
    "696d4842",  # 20-153
    "aba27056",  # 20-154
    "891232d6",  # 20-155
    "05a7bcf2", "135a2760",  # 20-160
    "a680ac02", "a1aa0c1e",  # 20-161
    "0934a4d8",  # 20-166
]


def export_stage(out, tmp, python):
    run = subprocess.run([python, "-u", str(HERE / "tables_export.py"), out, "--all-cases", *TASKS],
                         env=os.environ, capture_output=True, text=True, timeout=300)
    if run.returncode:
        raise RuntimeError(f"exit {run.returncode}\n{run.stdout}{run.stderr}")
    return run.stdout[-2000:]


def checks_stage(out, tmp):
    import export_checks
    sink = io.StringIO()
    violations = export_checks.check_export(out, sample=None, out=sink)
    lines = [l for l in (Path(out) / "checks.txt").read_text().splitlines() if l.strip()]
    if violations or lines:
        raise RuntimeError(f"{sum(violations.values())} violations\n{sink.getvalue()}" + ("\nchecks.txt:\n" + "\n".join(lines[:20]) if lines else ""))
    return sink.getvalue()


def load_stage(out, tmp):
    import encoder
    encoder.load_tables(out, f"{tmp}/tables.cache", strict=True, allow_violations=False)
    return ""


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--export-python", default=sys.executable)
    ap.add_argument("--keep", help="export here, to a directory that does not exist, and keep it")
    ap.add_argument("--from", dest="source", help="skip the export; check and load this export")
    args = ap.parse_args()
    tmp = tempfile.mkdtemp()
    if args.source:
        out, stages = args.source, [("checks", checks_stage), ("load", load_stage)]
    else:
        if args.keep and os.path.exists(args.keep):
            sys.exit(f"{args.keep} exists")
        out = args.keep or f"{tmp}/export"
        stages = [("export", lambda out, tmp: export_stage(out, tmp, args.export_python)), ("checks", checks_stage), ("load", load_stage)]
    failed = False
    for name, stage in stages:
        print(f"start {name}", flush=True)
        t = time.time()
        try:
            text, ok = stage(out, tmp), True
        except Exception as e:
            text, ok = (str(e) if isinstance(e, RuntimeError) else traceback.format_exc()), False
        failed |= not ok
        print(f"{'PASS' if ok else 'FAIL'} {name} ({time.time() - t:.1f}s)", flush=True)
        if text.strip():
            print(text.rstrip(), flush=True)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
