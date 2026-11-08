"""Inspect every exported gold case, with task isolation and classified failures.

Uses only the standard library and the built arclog wheel. Reads the task-local
NPZ inventory and streams, not the large masks or aggregate arrays.
"""
import argparse
import ast
from collections import Counter, defaultdict
import json
import re
from pathlib import Path
import struct
import subprocess
import os
import signal
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
import sys
import time
import zipfile


def npy(archive, name):
    with archive.open(name + ".npy") as src:
        magic = src.read(8)
        if magic[:6] != b"\x93NUMPY":
            raise ValueError("bad NPY magic")
        size = int.from_bytes(src.read(2 if magic[6] == 1 else 4), "little")
        header = ast.literal_eval(src.read(size).decode())
        dtype = header["descr"]
        data = src.read()
    if dtype.startswith("<U"):
        width = int(dtype[2:]) * 4
        return [data[i:i + width].decode("utf-32-le").rstrip("\0") for i in range(0, len(data), width)]
    formats = {"<u2": "<H", "<u4": "<I", "<i8": "<q", "|b1": "?", "|u1": "B"}
    return [row[0] for row in struct.iter_unpack(formats[dtype], data)]


def inventory(export, task, streams=False):
    with zipfile.ZipFile(export / "tasks" / task / "cases.npz") as archive:
        cases = npy(archive, "case")
        if not streams:
            return cases
        return cases, npy(archive, "offsets"), npy(archive, "ids"), npy(archive, "model")


class CaseDeadline(BaseException):
    pass


def check_task(args):
    import arclog
    cases, offsets, exported_ids, exported_model = inventory(args.export, args.worker, True)
    print(json.dumps({"task": args.worker, "expected_cases": cases}), flush=True)
    files = arclog.case_files(args.worker, (args.corpus / f"{args.worker}.arclog").read_text(),
                              (args.corpus / f"{args.worker}.arcdata").read_text(), str(args.corpus))
    files = {case.case: case for case in files}
    task = arclog.Task.from_json((args.tasks / f"{args.worker}.json").read_text(), arclog.World.Closed)
    settings = arclog.DecodeSettings(rule_tests=False)
    vocab = json.loads((args.export / "vocab.json").read_text())
    session = arclog.Session(task, settings, session_bytes=arclog.STUDY_SESSION_BYTES)
    v = session.vocabulary
    vocabulary_matches = ([v.name(i) for i in range(len(v))] == vocab["names"] and
                          [v.kind(i) for i in range(len(v))] == vocab["kinds"])
    results = []
    previous = signal.getsignal(signal.SIGALRM)
    def deadline(*_):
        raise CaseDeadline("case exceeded its time limit")
    signal.signal(signal.SIGALRM, deadline)
    for index, name in enumerate(cases):
        if args.worker_case is not None and name != args.worker_case:
            continue
        started = time.monotonic()
        row = dict(task=args.worker, case=name, failures=[], passed_phases=[])
        signal.setitimer(signal.ITIMER_REAL, args.case_seconds)
        try:
            def phase(label, fn):
                try:
                    value = fn()
                    row["passed_phases"].append(label)
                    return value
                except Exception as exc:
                    message = str(exc)
                    checks = sorted(set(re.findall(r"Check\((\w+)\)", message)))
                    category = "+".join(checks) if checks else (
                        "echo_mismatch" if "echo mismatch" in message else
                        "refusal" if type(exc).__name__ == "Refusal" else
                        "missing_out" if "through OUT" in message else
                        "unsupported_form" if "standalone case" in message else type(exc).__name__)
                    row["failures"].append(dict(phase=label, category=category, exception=type(exc).__name__, message=message))
                    return None

            def require(condition, message):
                if not condition:
                    raise RuntimeError(message)

            def source():
                case = files[name]
                require(case.fault is None, str(case.fault))
                return case.arclog

            sexp = phase("source_case", source)
            program = phase("sexp_ingest", lambda: arclog.StudyProgram.from_sexp(sexp, settings)) if sexp else None
            if program is not None:
                phase("source_names_layout", lambda: require(program.sexp() == sexp, "source names/layout changed"))
                written = phase("stream_write", program.decode_stream)
                if written is not None:
                    phase("sexp_roundtrip", lambda: require(arclog.StudyProgram.from_sexp(program.sexp(), settings).decode_stream() == written,
                                                           "sexp roundtrip changed stream or AST paths"))

            lo, hi = offsets[index:index + 2]
            ids, model = exported_ids[lo:hi], [int(flag) for flag in exported_model[lo:hi]]
            compatible = phase("export_vocabulary", lambda: require(
                vocabulary_matches, "8b09b24d wheel/export vocabulary mismatch"))
            if "export_vocabulary" in row["passed_phases"]:
                decoded = phase("export_stream_ingest", lambda: arclog.StudyProgram.from_stream(session, ids, model))
                if decoded is not None:
                    own = phase("decoded_stream_write", decoded.decode_stream)
                    if own is not None:
                        phase("export_stream_roundtrip", lambda: require((list(own[0]), list(own[1])) == (ids, model), "engine-written stream differs from exported stream"))
                        phase("decoded_sexp_roundtrip", lambda: require(
                            arclog.StudyProgram.from_sexp(decoded.program_form(), settings).decode_stream()[:2] == own[:2],
                            "decoded sexp changes its own stream"))
        except CaseDeadline as exc:
            row["failures"].append(dict(phase="case_deadline", category="timeout", exception="TimeoutError", message=str(exc)))
        except BaseException as exc:
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                raise
            row["failures"].append(dict(phase="case_worker", category=type(exc).__name__, exception=type(exc).__name__, message=str(exc)))
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
        row["seconds"] = round(time.monotonic() - started, 4)
        results.append(row)
        print(json.dumps(row), flush=True)
    signal.signal(signal.SIGALRM, previous)
    return results


def task_completions(jobs):
    pending = set(jobs)
    while pending:
        done, pending = wait(pending, timeout=2, return_when=FIRST_COMPLETED)
        if not done:
            yield None
        yield from done


def progress(done, total, started, cases, passed, counts):
    elapsed = time.monotonic() - started
    rate = done / max(elapsed, 0.001)
    eta = (total - done) / rate if rate else None
    eta_text = f"{eta:.1f}s" if eta is not None else "pending"
    print(f"{done}/{total} tasks; {passed}/{cases} cases passed; elapsed={elapsed:.1f}s "
          f"rate={rate:.2f} tasks/s ETA={eta_text}; failures={dict(counts)}", flush=True)


def run_task(args, task):
    command = [sys.executable, "-B", str(Path(__file__).resolve()), "--worker", task,
               "--export", str(args.export), "--corpus", str(args.corpus), "--tasks", str(args.tasks),
               "--case-seconds", str(args.case_seconds)]
    env = dict(os.environ, ARCLOG_THREADS="1", RAYON_NUM_THREADS="1", OMP_NUM_THREADS="1",
               OPENBLAS_NUM_THREADS="1", VECLIB_MAXIMUM_THREADS="1", PYTHONDONTWRITEBYTECODE="1")
    # Normally each native parse is well below the per-case alarm. Retain a
    # final watchdog for a process that crashes or stops responding entirely.
    try:
        run = subprocess.run(command, text=True, capture_output=True, env=env, timeout=180)
        output, error = run.stdout, f"worker_exit_{run.returncode}: {run.stderr[-4000:]}"
    except subprocess.TimeoutExpired as exc:
        output = exc.stdout or ""
        if isinstance(output, bytes):
            output = output.decode(errors="replace")
        error = "task_watchdog: worker did not finish in 180 seconds"
    names, found = None, {}
    for line in output.splitlines():
        try:
            row = json.loads(line)
            if "expected_cases" in row:
                names = row["expected_cases"]
            elif "case" in row:
                found[row["case"]] = row
        except (ValueError, KeyError):
            continue
    if names is None:
        try:
            names = inventory(args.export, task)
        except Exception as exc:
            names = ["<inventory>"]
            error = f"inventory: {type(exc).__name__}: {exc}"
    rows = [found.get(name, dict(task=task, case=name, passed_phases=[], failures=[dict(
        phase="task_worker", exception=error.split(":", 1)[0], message=error)])) for name in names]
    return task, rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export", type=Path, default=Path("/Users/davidlu/code/arc-workspace/work/lm/data-full-9fac8128"))
    parser.add_argument("--corpus", type=Path, default=Path("/Users/davidlu/code/arc-workspace/work/arclog/gen"))
    parser.add_argument("--tasks", type=Path, default=Path(__file__).parent / "engine/data/tasks")
    parser.add_argument("--output", type=Path, default=Path(__file__).parent / "stage1-all")
    parser.add_argument("--only", nargs="*")
    parser.add_argument("--workers", type=int, default=int(os.environ.get("ARC_HEAVY_CPUS", "1")))
    parser.add_argument("--case-seconds", type=float, default=5)
    parser.add_argument("--worker", help=argparse.SUPPRESS)
    parser.add_argument("--worker-case", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        check_task(args)
        return
    import arclog
    tasks = sorted(args.only or json.loads((args.export / "keys.json").read_text()))
    args.output.mkdir(parents=True, exist_ok=True)
    counts, examples, phases = Counter(), defaultdict(list), Counter()
    total = passed = expected = 0
    started = time.monotonic()
    with (args.output / "cases.jsonl").open("w") as records:
        budget = int(os.environ.get("ARC_HEAVY_CPUS", str(args.workers)))
        if args.workers < 1 or args.workers > budget or args.case_seconds <= 0:
            parser.error("workers must be positive and at most ARC_HEAVY_CPUS; case-seconds must be positive")
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            jobs = {pool.submit(run_task, args, task): task for task in tasks}
            index = 0
            last_progress = 0
            progress(0, len(tasks), started, total, passed, counts)
            for completed in task_completions(jobs):
                if completed is None:
                    progress(index, len(tasks), started, total, passed, counts)
                    continue
                index += 1
                task, rows = completed.result()
                expected += len(rows)
                for row in rows:
                    name = row["case"]
                    records.write(json.dumps(row) + "\n")
                    total += 1
                    passed += not row["failures"]
                    phases.update(row["passed_phases"])
                    for failure in row["failures"]:
                        key = failure["phase"] + "/" + failure.get("category", failure["exception"])
                        counts[key] += 1
                        if len(examples[key]) < 5:
                            examples[key].append(dict(task=task, case=name, message=failure["message"]))
                records.flush()
                if index % 25 == 0 or index == len(tasks) or time.monotonic() - last_progress >= 2:
                    progress(index, len(tasks), started, total, passed, counts)
                    last_progress = time.monotonic()
    summary = dict(stage=1, tasks=len(tasks), expected_cases=expected, checked_cases=total, passed_cases=passed,
                   failed_cases=total - passed, failure_counts=dict(counts), failure_examples=dict(examples),
                   phase_pass_counts=dict(phases), seconds=round(time.monotonic() - started, 3),
                   streams_digest=arclog.streams_digest(), export=str(args.export), corpus=str(args.corpus))
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
