"""Audit clause mutation across the export: one process per task, streamed output."""
import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile
import shutil
from threading import Event, Timer
import time

from check_stage1_all import CaseDeadline, inventory, progress, task_completions

POLICY = "complete-domain-without-replacement-v4"


def emit(event):
    print(json.dumps(event), flush=True)


def failure(row, phase, exc, context=None):
    message = str(exc)
    checks = sorted(set(re.findall(r"Check\((\w+)\)", message)))
    row["failures"].append(dict(phase=phase, category="+".join(checks) if checks else type(exc).__name__,
        exception=type(exc).__name__, message=message, **(context or {})))


def measured(row, phase, function, *args, **kwargs):
    row.setdefault("cursor", {})["location"] = phase
    started = time.monotonic()
    try:
        return function(*args, **kwargs)
    finally:
        row["timings"][phase] += time.monotonic() - started


def audit_case(args, row, source, session, settings, samples):
    import arclog
    if source.fault:
        raise RuntimeError(source.fault)
    program = arclog.StudyProgram.from_sexp(source.arclog, settings)
    points = program.points()
    if args.body is not None:
        points = [p for p in points if p.body_path == args.body]
    row["counts"]["points"] += len(points)
    for point in points:
        for k in args.ks:
            for operation in args.operations:
                context = dict(clause=point.clause_path, body=point.body_path, kind=point.kind, K=k, operation=operation)
                row["cursor"] = dict(location="domain", **context)
                try:
                    specs, report = measured(row, "domain", program.draw_specs, point, k, args.per_point, args.seed,
                        source_revision=args.export.name, task=args.worker, case=row["case"], operation=operation)
                    stats = json.loads(report)
                    row["counts"].update(stats["counts"])
                    row["counts"]["domain_requests"] += 1
                    emit(dict(event="draw", task=args.worker, case=row["case"], requested=args.per_point,
                              produced=len(specs), stats=stats, **context))
                    forbidden = ("draw_attempts", "no_valid_extension", "duplicate_draw", "sampling_budget_exhausted")
                    if any(stats["counts"].get(name, 0) for name in forbidden):
                        raise RuntimeError("partial-draw/retry sampler is still active")
                    if any(name.startswith("choice_check:") for name in stats["counts"]):
                        raise RuntimeError("invalid choices were offered to the sampler")
                    if any(name.startswith("domain_search_stopped:") for name in stats["counts"]):
                        raise TimeoutError("completion-domain search reached its explicit deadline")
                    identities = [spec.identity_json for spec in specs]
                    if len(set(identities)) != len(identities):
                        raise RuntimeError("sampling without replacement returned a duplicate")
                    if len(specs) < args.per_point and not stats["counts"].get("domain_exhausted"):
                        raise RuntimeError("short draw without proof of domain exhaustion")
                except Exception as exc:
                    failure(row, "domain", exc, context)
                    continue
                for spec in specs:
                    phase = "construct"
                    mutant = None
                    written = None
                    try:
                        mutant = measured(row, "construct", program.construct, spec)
                        row["counts"]["constructed"] += 1
                        phase = "exact_edit_audit"
                        audit = json.loads(measured(row, "exact_edit_audit", mutant.audit_json))
                        identity = json.loads(spec.identity_json)
                        if audit["changed_atoms"] != k or spec.k != k or mutant.k != k:
                            raise RuntimeError("K differs from actual changed atoms")
                        if identity != json.loads(mutant.identity_json):
                            raise RuntimeError("identity changed during construction")
                        phase = "mutant_sexp_roundtrip"
                        sexp, written = measured(row, "mutant_print", lambda: (mutant.sexp(), mutant.decode_stream()))
                        reread = measured(row, "mutant_sexp_roundtrip", lambda: arclog.StudyProgram.from_sexp(sexp, settings).decode_stream())
                        if reread[:2] != written[:2]:
                            raise RuntimeError("mutant sexp changed its own decode stream")
                        phase = "mutant_stream_replay"
                        replay = measured(row, "mutant_stream_replay", arclog.StudyProgram.from_stream, session, written[0], written[1])
                        if replay.decode_stream()[:2] != written[:2]:
                            raise RuntimeError("mutant stream differs after engine replay")
                        record = dict(event="mutant", task=args.worker, case=row["case"], identity=identity,
                                      audit=audit, status="verified", **context)
                        # Verify every mutant; bound redundant full-program output.
                        if samples[0] < args.program_samples:
                            record.update(sexp=sexp, stream=dict(ids=written[0], model=list(written[1])))
                            samples[0] += 1
                        emit(record)
                        row["counts"]["verified"] += 1
                    except Exception as exc:
                        failure(row, phase, exc, context)
                        # Keep the exact failed specimen for root-cause work;
                        # successful examples alone cannot reproduce a fault.
                        emit(dict(event="mutant_failure", task=args.worker, case=row["case"],
                                  identity=json.loads(spec.identity_json), phase=phase,
                                  message=str(exc), sexp=mutant.sexp() if mutant else None,
                                  stream=dict(ids=written[0], model=list(written[1]))
                                  if written else None, **context))
    if not row["failures"]:
        row["passed_phases"] = ["domain_contract", "construct", "exact_edit_audit", "sexp_roundtrip", "stream_roundtrip"]


def check_task(args):
    import arclog
    names = inventory(args.export, args.worker)
    if args.cases:
        names = [name for name in names if name in args.cases]
    emit(dict(event="inventory", task=args.worker, expected_cases=names))
    sources = arclog.case_files(args.worker, (args.corpus / f"{args.worker}.arclog").read_text(),
                               (args.corpus / f"{args.worker}.arcdata").read_text(), str(args.corpus))
    sources = {case.case: case for case in sources}
    settings = arclog.DecodeSettings(deadline_seconds=args.domain_seconds, rule_tests=False)
    task = arclog.Task.from_json((args.tasks / f"{args.worker}.json").read_text(), arclog.World.Closed)
    session = arclog.Session(task, settings, session_bytes=256 * 1024 * 1024)
    samples = [0]
    previous = signal.getsignal(signal.SIGALRM)
    def deadline(*_):
        raise CaseDeadline("case exceeded its time limit")
    signal.signal(signal.SIGALRM, deadline)
    for name in names:
        started = time.monotonic()
        row = dict(event="case", task=args.worker, case=name, failures=[], passed_phases=[], counts=Counter(), timings=defaultdict(float))
        signal.setitimer(signal.ITIMER_REAL, args.case_seconds)
        try:
            audit_case(args, row, sources[name], session, settings, samples)
        except CaseDeadline as exc:
            failure(row, "case_deadline", TimeoutError(str(exc)), row.get("cursor"))
        except BaseException as exc:
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                raise
            failure(row, "case_worker", exc)
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
        row.pop("cursor", None)
        row["seconds"] = round(time.monotonic() - started, 4)
        emit(row)
    signal.signal(signal.SIGALRM, previous)


def run_task(args, task):
    command = [sys.executable, "-B", str(Path(__file__).resolve()), "--worker", task,
        "--export", str(args.export), "--corpus", str(args.corpus), "--tasks", str(args.tasks),
        "--case-seconds", str(args.case_seconds), "--domain-seconds", str(args.domain_seconds),
        "--per-point", str(args.per_point), "--seed", str(args.seed), "--program-samples", str(args.program_samples),
        "--ks", *map(str, args.ks), "--operations", *args.operations]
    if args.cases:
        command += ["--cases", *args.cases]
    if args.body is not None:
        command += ["--body", *map(str,args.body)]
    env = dict(os.environ, ARCLOG_THREADS="1", RAYON_NUM_THREADS="1", OMP_NUM_THREADS="1",
               OPENBLAS_NUM_THREADS="1", VECLIB_MAXIMUM_THREADS="1", PYTHONDONTWRITEBYTECODE="1")
    names, cases, events = None, {}, []
    # Read the inventory header immediately, without loading the export a
    # second time in the parent. Size the watchdog to the task's case count;
    # one fixed task deadline otherwise truncates large tasks by design.
    timed_out = Event()
    with tempfile.TemporaryFile(dir=Path(__file__).parent) as errors:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=errors,
                                   text=True, bufsize=1, env=env)
        def stop():
            if process.poll() is None:
                timed_out.set()
                try:
                    process.kill()
                except ProcessLookupError:
                    pass
        limit = args.task_seconds or 30.0
        watchdog = Timer(limit, stop)
        watchdog.start()
        try:
            for line in process.stdout:
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if row.get("event") == "inventory":
                    names = row["expected_cases"]
                    watchdog.cancel()
                    limit = args.task_seconds or max(30.0, len(names) * args.case_seconds + 15.0)
                    watchdog = Timer(limit, stop)
                    watchdog.start()
                elif row.get("event") == "case":
                    cases[row["case"]] = row
                else:
                    events.append(row)
            code = process.wait()
        finally:
            watchdog.cancel()
            process.stdout.close()
        errors.seek(0, 2)
        errors.seek(max(0, errors.tell() - 4000))
        error = (f"task_watchdog: worker exceeded {limit} seconds" if timed_out.is_set()
                 else f"worker_exit_{code}: {errors.read().decode(errors='replace')}")
    if names is None:
        try:
            names = inventory(args.export, task)
        except Exception as exc:
            names = ["<inventory>"]
            error = f"inventory: {type(exc).__name__}: {exc}"
    rows = [cases.get(name, dict(task=task, case=name, counts={}, passed_phases=[], failures=[dict(
        phase="task_worker", exception=error.split(":", 1)[0], message=error)])) for name in names]
    return task, rows, events


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export", type=Path, default=Path("/Users/davidlu/code/arc-workspace/work/lm/data-full-9fac8128"))
    parser.add_argument("--corpus", type=Path, default=Path("/Users/davidlu/code/arc-workspace/work/arclog/gen"))
    parser.add_argument("--tasks", type=Path, default=Path(__file__).parent / "engine/data/tasks")
    parser.add_argument("--task", help="Single diagnostic task; default is the whole export")
    parser.add_argument("--only", nargs="+")
    parser.add_argument("--cases", nargs="+", help="Named real cases for a bounded diagnostic; default all")
    parser.add_argument("--body", nargs="+", type=int, help="AST body path for a bounded diagnostic; default all")
    parser.add_argument("--frozen", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--ks", nargs="+", type=int, default=[1, 2, 3])
    parser.add_argument("--operations", nargs="+", choices=["substitute", "delete", "mixed"], default=["substitute", "delete", "mixed"])
    parser.add_argument("--per-point", type=int, default=2)
    parser.add_argument("--seed", type=int, default=4231)
    parser.add_argument("--workers", type=int, default=int(os.environ.get("ARC_HEAVY_CPUS", "1")))
    parser.add_argument("--case-seconds", type=float, default=10)
    parser.add_argument("--domain-seconds", type=float, default=2)
    parser.add_argument("--task-seconds", type=float, help="Hard override; default watchdog scales with the inventory's case count")
    parser.add_argument("--program-samples", type=int, default=2)
    parser.add_argument("--output", type=Path, default=Path(__file__).parent / "stage2-check.json")
    parser.add_argument("--worker", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if not args.worker and not args.frozen:
        # Workers must not read the live script after the parent starts.
        # An engine/code edit in another thread cannot alter an active run.
        args.output.parent.mkdir(parents=True,exist_ok=True)
        snapshot = Path(tempfile.mkdtemp(prefix=args.output.stem+".code-",dir=args.output.parent)).resolve()
        for filename in ("check_stage2.py", "check_stage1_all.py"):
            shutil.copy2(Path(__file__).parent / filename, snapshot / filename)
        command = [sys.executable,"-B",str(snapshot / "check_stage2.py"),*sys.argv[1:],"--frozen",
                   "--tasks",str(args.tasks.resolve()),"--output",str(args.output.resolve())]
        print("checker code snapshot: "+str(snapshot),flush=True)
        os.execv(sys.executable,command)
    import arclog
    if getattr(arclog.StudyProgram, "mutation_policy", lambda: None)() != POLICY:
        parser.error("rebuild the wheel: this check requires the complete-domain sampler")
    if args.worker:
        check_task(args)
        return
    budget = int(os.environ.get("ARC_HEAVY_CPUS", str(args.workers)))
    if (not 1 <= args.workers <= budget or min(args.case_seconds, args.domain_seconds) <= 0
            or args.task_seconds is not None and args.task_seconds <= 0):
        parser.error("invalid workers or deadline; workers must not exceed ARC_HEAVY_CPUS")
    if args.per_point < 1 or any(k < 1 for k in args.ks):
        parser.error("per-point and K must be positive")
    tasks = sorted([args.task] if args.task else args.only or json.loads((args.export / "keys.json").read_text()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    total = passed = 0
    counts, reasons, phases = Counter(), Counter(), Counter()
    timings = defaultdict(float)
    examples = defaultdict(list)
    cases_path = args.output.with_suffix(".cases.jsonl")
    mutants_path = args.output.with_suffix(".mutants.jsonl")
    draws_path = args.output.with_suffix(".draws.jsonl")
    with cases_path.open("w") as records, mutants_path.open("w") as mutants, draws_path.open("w") as draws:
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            jobs = {pool.submit(run_task, args, task): task for task in tasks}
            done = 0
            last_progress = 0
            progress(done, len(tasks), started, total, passed, reasons)
            for completed in task_completions(jobs):
                if completed is None:
                    progress(done, len(tasks), started, total, passed, reasons)
                    continue
                task, rows, events = completed.result()
                done += 1
                for event in events:
                    target = mutants if event.get("event") == "mutant" else draws
                    target.write(json.dumps(event) + "\n")
                for row in rows:
                    records.write(json.dumps(row) + "\n")
                    total += 1
                    passed += not row["failures"]
                    counts.update(row["counts"])
                    for phase,seconds in row.get("timings",{}).items():
                        timings[phase] += seconds
                    phases.update(row["passed_phases"])
                    for error in row["failures"]:
                        key = error["phase"] + "/" + error.get("category", error["exception"])
                        reasons[key] += 1
                        if len(examples[key]) < 5:
                            examples[key].append(dict(task=task, case=row["case"], **error))
                for handle in (records, mutants, draws):
                    handle.flush()
                if done % 25 == 0 or done == len(tasks) or time.monotonic() - last_progress >= 2:
                    progress(done, len(tasks), started, total, passed, reasons)
                    last_progress = time.monotonic()
    summary = dict(stage=2, tasks=len(tasks), expected_cases=total, checked_cases=total,
        passed_cases=passed, failed_cases=total-passed, failure_counts=dict(reasons), failure_examples=dict(examples),
        phase_pass_counts=dict(phases), counts=dict(counts), status="passed" if not reasons else "needs_fix",
        timings=dict(timings), seconds=round(time.monotonic()-started, 3), streams_digest=arclog.streams_digest(),
        export=str(args.export), corpus=str(args.corpus), policy=POLICY)
    args.output.write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
