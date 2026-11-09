"""Stream the stage-2 audit with case checkpoints and supervised task workers.

No evaluation of OUT is needed for a complete-program round trip. Every
unique mutant still gets the AST audit, sexp reread and exact grammar replay.
"""
import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import fcntl
import json
import os
from pathlib import Path
from queue import Empty, Full, Queue
import re
import signal
import shutil
import subprocess
import sys
import tempfile
from threading import Event, Lock, Thread
import time

from check_stage1_all import CaseDeadline, inventory, read_checked
from engine import checkout  # on the path since check_stage1_all put `src/` there

POLICY = "complete-domain-unique-text-gold-names-v7"
READER = "complete-program-bindings-v2"
COVERAGE = "stage2-unit-free-v1"


def emit(event):
    print(json.dumps(event, separators=(",", ":")), flush=True)


def failure(row, phase, exc, context=None):
    message = str(exc)
    checks = sorted(set(re.findall(r"Check\((\w+)\)", message)))
    row["failures"].append(dict(phase=phase, category="+".join(checks) if checks else type(exc).__name__,
        exception=type(exc).__name__, message=message, **(context or {})))


def measured(row, phase, function, *args, **kwargs):
    row.setdefault("cursor", {})["location"] = phase
    emit(dict(event="cursor", task=row["task"], case=row["case"], cursor=row["cursor"]))
    started = time.monotonic()
    try:
        return function(*args, **kwargs)
    finally:
        row["timings"][phase] += time.monotonic() - started


def audit_case(args, row, source, session, settings, samples):
    import arclog
    if source.fault:
        raise RuntimeError(source.fault)
    program = measured(row, "gold_ingest", arclog.StudyProgram.from_sexp, source.arclog, settings, session=session)
    points = program.points()
    if args.body is not None:
        points = [p for p in points if p.body_path == args.body]
    row["counts"]["points"] += len(points)
    # Keys are exact JSON identities on this one immutable gold handle.
    # Only successful independent round trips enter this case-local memo.
    verified = {}
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
                        raise TimeoutError("completion-domain search reached its explicit node cap")
                    identities = [spec.identity_json for spec in specs]
                    if len(set(identities)) != len(identities):
                        raise RuntimeError("sampling without replacement returned a duplicate")
                    if len(specs) < args.per_point and not stats["counts"].get("domain_exhausted"):
                        raise RuntimeError("short draw without proof of domain exhaustion")
                except Exception as exc:
                    failure(row, "domain", exc, context)
                    continue
                for spec, identity_json in zip(specs, identities, strict=True):
                    phase = "construct"
                    mutant = written = sexp = None
                    try:
                        mutant = measured(row, "construct", program.construct, spec)
                        row["counts"]["constructed"] += 1
                        identity = json.loads(identity_json)
                        if spec.k != k or mutant.k != k:
                            raise RuntimeError("K differs from the certified edit count")
                        if identity != json.loads(mutant.identity_json):
                            raise RuntimeError("identity changed during construction")
                        cached = identity_json in verified
                        if cached:
                            audit, reference = verified[identity_json]
                            row["counts"]["verification_cache_hits"] += 1
                        else:
                            phase = "exact_edit_audit"
                            audit = json.loads(measured(row, phase, mutant.audit_json))
                            if audit["changed_atoms"] != k:
                                raise RuntimeError("K differs from actual changed atoms")
                            phase = "mutant_print"
                            sexp, written = measured(row, phase, lambda: (mutant.sexp(), mutant.decode_stream()))
                            phase = "mutant_sexp_roundtrip"
                            reread = measured(row, phase, lambda: arclog.StudyProgram.from_sexp(sexp, settings, session=session).decode_stream())
                            if reread[:2] != written[:2]:
                                raise RuntimeError("mutant sexp changed its own decode stream")
                            del reread
                            phase = "mutant_stream_replay"
                            # The native entry point checks grammar, binding, all
                            # whole-program checks AND exact output == input.
                            # Re-writing the same returned handle once more adds
                            # no independent assertion to that contract.
                            measured(row, phase, arclog.StudyProgram.from_stream, session, written[0], written[1])
                            reference = len(verified) + 1
                            verified[identity_json] = (audit, reference)
                            row["counts"]["unique_verified"] += 1
                        record = dict(event="mutant", task=args.worker, case=row["case"], identity=identity,
                                      audit=audit, status="verified", verification_ref=reference,
                                      verification_cached=cached, **context)
                        if not cached and samples[0] < args.program_samples:
                            record.update(sexp=sexp, stream=dict(ids=written[0], model=list(written[1])))
                            samples[0] += 1
                        emit(record)
                        record = None
                        row["counts"]["verified"] += 1
                    except Exception as exc:
                        failure(row, phase, exc, context)
                        specimen = dict(event="mutant_failure", task=args.worker, case=row["case"],
                                        identity=json.loads(identity_json), phase=phase, message=str(exc), **context)
                        if sexp is not None:
                            specimen["sexp"] = sexp
                        elif mutant is not None:
                            try:
                                specimen["sexp"] = mutant.sexp()
                            except Exception as printing:
                                specimen["specimen_fault"] = str(printing)
                        if written is not None:
                            specimen["stream"] = dict(ids=written[0], model=list(written[1]))
                        emit(specimen)
                    finally:
                        # No previous mutant or native stream remains alive
                        # while constructing the next one.
                        mutant = written = sexp = None
    if not row["failures"]:
        row["passed_phases"] = ["domain_contract", "construct", "exact_edit_audit", "sexp_roundtrip", "stream_roundtrip"]


def check_task(args):
    import arclog
    names = json.loads(args.worklist.read_text())
    emit(dict(event="inventory", task=args.worker, expected_cases=names))
    sources = arclog.case_files(args.worker, read_checked(args.corpus / f"{args.worker}.arclog"),
                               read_checked(args.corpus / f"{args.worker}.arcdata"), str(args.corpus))
    sources = {case.case: case for case in sources}
    settings = (arclog.DecodeSettings(mutation_node_cap=args.domain_nodes, rule_tests=False)
                if args.domain_nodes else arclog.DecodeSettings.corpus())
    task = arclog.Task.from_json((args.tasks / f"{args.worker}.json").read_text(), arclog.World.Closed)
    session = arclog.Session(task, settings, session_bytes=arclog.STUDY_SESSION_BYTES)
    samples = [args.sample_start]
    previous = signal.getsignal(signal.SIGALRM)
    def deadline(*_):
        raise CaseDeadline("case exceeded its time limit")
    signal.signal(signal.SIGALRM, deadline)
    try:
        for name in names:
            started = time.monotonic()
            row = dict(event="case", task=args.worker, case=name, complete=False, failures=[],
                       passed_phases=[], counts=Counter(), timings=defaultdict(float))
            emit(dict(event="case_start", task=args.worker, case=name))
            signal.setitimer(signal.ITIMER_REAL, args.case_seconds)
            try:
                session.reset_program_replay()
                audit_case(args, row, sources[name], session, settings, samples)
                row["complete"] = not any(error["exception"] == "TimeoutError" for error in row["failures"])
            except CaseDeadline as exc:
                failure(row, "case_deadline", TimeoutError(str(exc)), row.get("cursor"))
            except BaseException as exc:
                if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                    raise
                failure(row, "case_worker", exc, row.get("cursor"))
            finally:
                signal.setitimer(signal.ITIMER_REAL, 0)
                session.reset_program_replay()
            row.pop("cursor", None)
            row["seconds"] = round(time.monotonic() - started, 4)
            emit(row)
    finally:
        signal.signal(signal.SIGALRM, previous)


def read_jsonl(path):
    """Yield intact rows and their byte ends, ignoring only a torn final row."""
    if not path.exists():
        return
    with path.open("rb") as src:
        while line := src.readline():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                if line.endswith(b"\n"):
                    raise
                break
            yield row, src.tell(), not line.endswith(b"\n")


def repair_tail(path):
    end, needs_newline = 0, False
    for _, end, needs_newline in read_jsonl(path):
        pass
    with path.open("r+b") as out:
        out.seek(end)
        out.truncate()
        if needs_newline:
            out.write(b"\n")


def run_task(args, task, names, receive, cancel, job_dir):
    """Stream a bounded pipe; a dead case never fabricates failures for later ones."""
    remaining = dict.fromkeys(names)
    samples = 0
    hard_end = time.monotonic() + args.task_seconds if args.task_seconds else None
    while remaining and not cancel.is_set():
        if hard_end is not None and time.monotonic() >= hard_end:
            receive(dict(event="task_failure", task=task, remaining_cases=len(remaining), reason="task_budget_exhausted"))
            break
        worklist = job_dir / (task + ".json")
        worklist.write_text(json.dumps(list(remaining)))
        command = [sys.executable, "-B", str(Path(__file__).resolve()), "--worker", task,
            "--worklist", str(worklist), "--export", str(args.export), "--corpus", str(args.corpus),
            "--tasks", str(args.tasks), "--case-seconds", str(args.case_seconds),
            "--domain-nodes", str(args.domain_nodes), "--per-point", str(args.per_point),
            "--seed", str(args.seed), "--program-samples", str(args.program_samples),
            "--sample-start", str(samples), "--ks", *map(str, args.ks), "--operations", *args.operations]
        if args.body is not None:
            command += ["--body", *map(str, args.body)]
        env = dict(os.environ, ARCLOG_THREADS="1", RAYON_NUM_THREADS="1", OMP_NUM_THREADS="1",
                   OPENBLAS_NUM_THREADS="1", VECLIB_MAXIMUM_THREADS="1", PYTHONDONTWRITEBYTECODE="1")
        messages, halt_reader = Queue(maxsize=8), Event()
        active, cursor, active_started = None, {}, 0.0
        deadline = time.monotonic() + args.startup_seconds if args.startup_seconds else float("inf")
        fault = None
        with tempfile.TemporaryFile(dir=job_dir) as errors:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=errors, text=True,
                                       bufsize=1, env=env)
            def enqueue(value):
                while not halt_reader.is_set():
                    try:
                        messages.put(value, timeout=.2)
                        return
                    except Full:
                        pass
            def read_pipe():
                try:
                    for line in process.stdout:
                        try:
                            enqueue(("row", json.loads(line)))
                        except ValueError:
                            enqueue(("error", "worker emitted invalid JSON: " + line[:2000]))
                            return
                finally:
                    enqueue(("eof", None))
            reader = Thread(target=read_pipe, daemon=True)
            reader.start()
            try:
                while not cancel.is_set():
                    now = time.monotonic()
                    if now >= deadline or hard_end is not None and now >= hard_end:
                        fault = "task_budget_exhausted" if hard_end is not None and now >= hard_end else "case_watchdog" if active else "task_startup_watchdog"
                        break
                    try:
                        kind, row = messages.get(timeout=min(.25, max(.001, deadline-now)))
                    except Empty:
                        continue
                    if kind == "error":
                        fault = "worker_protocol: " + row
                        break
                    if kind == "eof":
                        code = process.wait()
                        if remaining:
                            errors.seek(0, 2)
                            errors.seek(max(0, errors.tell()-4000))
                            fault = f"worker_exit_{code}: " + errors.read().decode(errors="replace")
                        break
                    event = row.get("event")
                    if row.get("task") != task or event not in {"inventory", "case_start", "cursor", "case", "draw", "mutant", "mutant_failure"}:
                        fault = "worker_protocol: unexpected event or task"
                        break
                    if event == "case_start" and (active is not None or row["case"] not in remaining):
                        fault = "worker_protocol: unexpected case start"
                        break
                    if event in {"case", "cursor", "draw", "mutant", "mutant_failure"} and row.get("case") != active:
                        fault = "worker_protocol: event is outside the active case"
                        break
                    if event == "case_start":
                        active, cursor = row["case"], {}
                        active_started = time.monotonic()
                        # A case's matrix grows with its AST and is not a unit
                        # of bounded work. A hard case/stall guard must
                        # be explicitly requested by the caller.
                        deadline = (active_started + args.case_seconds if args.case_seconds
                                    else active_started + args.stall_seconds if args.stall_seconds else float("inf"))
                    elif event == "cursor":
                        cursor = row["cursor"]
                        if not args.case_seconds and args.stall_seconds:
                            deadline = time.monotonic() + args.stall_seconds
                    elif event == "case":
                        remaining.pop(row["case"], None)
                        active, cursor = None, {}
                        deadline = time.monotonic() + args.startup_seconds if args.startup_seconds else float("inf")
                    elif event == "mutant" and "sexp" in row:
                        samples += 1
                    receive(row)
            finally:
                halt_reader.set()
                if process.poll() is None:
                    process.kill()
                process.wait()
                reader.join(timeout=2)
                process.stdout.close()
            if fault and not cancel.is_set():
                if active is not None:
                    receive(dict(event="case", task=task, case=active, complete=False, counts={},
                        passed_phases=[], timings={}, seconds=time.monotonic()-active_started,
                        failures=[dict(phase="case_watchdog", category=fault.split(":",1)[0],
                                       exception="TimeoutError" if "watchdog" in fault or "budget" in fault else "WorkerExit",
                                       message=fault, **cursor)]))
                    remaining.pop(active, None)
                else:
                    receive(dict(event="task_failure", task=task, remaining_cases=len(remaining),
                                 reason=fault))
                    break
                # A failed active case is recorded once; the next worker
                # starts at the first case that has not actually run.
    receive(dict(event="task_end", task=task, remaining_cases=len(remaining)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export", type=Path, default=Path("/Users/davidlu/code/arc-workspace/work/lm/data-full-9fac8128"))
    parser.add_argument("--corpus", type=Path, default=checkout.arclog())
    parser.add_argument("--tasks", type=Path, default=Path(__file__).parent / "engine/data/tasks")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--task")
    group.add_argument("--only", nargs="+")
    group.add_argument("--task-file", type=Path, help="one task ID per line")
    parser.add_argument("--cases", nargs="+")
    parser.add_argument("--body", nargs="+", type=int)
    parser.add_argument("--ks", nargs="+", type=int, default=[1, 2, 3])
    parser.add_argument("--operations", nargs="+", choices=["substitute", "delete", "mixed"], default=["substitute", "delete", "mixed"])
    parser.add_argument("--per-point", type=int, default=2)
    parser.add_argument("--seed", type=int, default=4231)
    parser.add_argument("--workers", "--jobs", type=int, default=int(os.environ.get("ARC_HEAVY_CPUS", "1")))
    parser.add_argument("--case-seconds", type=float, default=0, help="optional whole-case limit; 0 (default) lets the full matrix finish")
    parser.add_argument("--domain-nodes", type=int, default=0, help="optional native search node cap; 0 (default) finishes the finite domain")
    parser.add_argument("--startup-seconds", type=float, default=0, help="optional startup limit; 0 (default) lets task expansion finish")
    parser.add_argument("--stall-seconds", type=float, default=0, help="optional guard for time without a new audit phase; 0 disables it")
    parser.add_argument("--task-seconds", type=float, help="optional hard total task budget; default is case supervision")
    parser.add_argument("--program-samples", type=int, default=2)
    parser.add_argument("--output", type=Path, default=Path(__file__).parent / "stage2-check.json")
    parser.add_argument("--resume", action="store_true", help="append intact JSONL and skip completed cases from this exact runtime/configuration")
    parser.add_argument("--resume-from", type=Path, help="inherit completed cases into a new output prefix from an earlier compatible audit")
    parser.add_argument("--retry-failed", action="store_true", help="with --resume, retry completed audits that reported failures too")
    parser.add_argument("--frozen", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--worker", help=argparse.SUPPRESS)
    parser.add_argument("--worklist", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--sample-start", type=int, default=0, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if not args.worker and not args.frozen:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        snapshot = Path(tempfile.mkdtemp(prefix=args.output.stem+".code-", dir=args.output.parent)).resolve()
        for filename in ("check_stage2.py", "check_stage1_all.py"):
            shutil.copy2(Path(__file__).parent / filename, snapshot / filename)
        command = [sys.executable, "-B", str(snapshot / "check_stage2.py"), *sys.argv[1:], "--frozen",
                   "--tasks", str(args.tasks.resolve()), "--output", str(args.output.resolve())]
        print("checker code snapshot: " + str(snapshot), flush=True)
        os.execv(sys.executable, command)
    import arclog
    policy = arclog.StudyProgram.mutation_policy()
    reader = getattr(arclog.StudyProgram, "stream_reader_policy", lambda: None)()
    if policy != POLICY or reader != READER or not hasattr(arclog.Session, "reset_program_replay"):
        parser.error("use the isolated stage-2 runtime built from this revision (complete-program reader and case reset required)")
    if args.worker:
        check_task(args)
        return
    budget = int(os.environ.get("ARC_HEAVY_CPUS", str(args.workers)))
    if (not 1 <= args.workers <= budget or min(args.case_seconds, args.startup_seconds) < 0
            or min(args.domain_nodes, args.stall_seconds) < 0
            or args.task_seconds is not None and args.task_seconds <= 0):
        parser.error("invalid workers/deadline; workers must not exceed ARC_HEAVY_CPUS")
    if args.per_point < 1 or args.program_samples < 0 or not args.ks or min(args.ks) < 1:
        parser.error("per-point and K must be positive; program-samples must be nonnegative")
    if args.task:
        tasks = [args.task]
    elif args.only:
        tasks = args.only
    elif args.task_file:
        tasks = args.task_file.read_text().split()
    else:
        tasks = json.loads((args.export / "keys.json").read_text())
    tasks = sorted(set(tasks))
    # Keep the exact audit/runtime configuration separate from scheduling and
    # resume controls. A changed mutation policy must not skip older coverage.
    binaries = sorted(Path(arclog.__file__).parent.glob("*.so"))
    if not binaries:
        raise RuntimeError("cannot identify the installed native extension for checkpoint provenance")
    runtime = hashlib.sha256()
    for binary in binaries:
        with binary.open("rb") as src:
            for data in iter(lambda: src.read(1 << 20), b""):
                runtime.update(data)
    config = dict(schema=3, coverage=COVERAGE, policy=policy, reader=reader, native_sha256=runtime.hexdigest(),
        checker_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        export=str(args.export.resolve()), corpus=str(args.corpus.resolve()), tasks_path=str(args.tasks.resolve()),
        tasks=tasks, cases=args.cases, body=args.body, ks=args.ks, operations=args.operations,
        per_point=args.per_point, seed=args.seed, case_seconds=args.case_seconds,
        domain_nodes=args.domain_nodes, program_samples=args.program_samples,
        resume_from=str(args.resume_from.resolve()) if args.resume_from else None)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    output_lock = args.output.with_suffix(".lock").open("a+")
    try:
        fcntl.flock(output_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        parser.error("another stage-2 writer owns this output prefix")
    paths = {name: args.output.with_suffix("."+name+".jsonl") for name in ("cases", "mutants", "draws")}
    config_path = args.output.with_suffix(".config.json")
    inherited_path = args.output.with_suffix(".inherited.json")
    existing = any(path.exists() for path in paths.values())
    if args.resume and existing:
        if not config_path.exists() or json.loads(config_path.read_text()) != config:
            parser.error("checkpoint runtime/configuration differs or lacks provenance; choose a new --output")
    elif existing and not args.resume:
        parser.error("JSONL output exists; use --resume or choose a new --output")
    else:
        inherited = dict(cases=[], source=None)
        if args.resume_from:
            if args.resume_from.resolve() == args.output.resolve():
                parser.error("--resume-from requires a new output prefix")
            source_config = json.loads(args.resume_from.with_suffix(".config.json").read_text())
            if source_config.get("coverage") != COVERAGE:
                parser.error("--resume-from predates the Unit-free audit contract; start fresh for corpus-v6 coverage")
            coverage = ("policy", "export", "corpus", "tasks_path", "tasks", "cases", "body", "ks", "operations", "per_point", "seed")
            if any(source_config.get(key) != config[key] for key in coverage):
                parser.error("--resume-from mutation policy or audit coverage differs")
            if args.domain_nodes and source_config.get("domain_nodes") != args.domain_nodes:
                parser.error("--resume-from native search node cap differs")
            if source_config.get("reader") not in ("complete-program-grammar-v1", READER):
                parser.error("--resume-from has an incompatible complete-program reader")
            source_cases = {}
            source_inherited = args.resume_from.with_suffix(".inherited.json")
            ancestors = json.loads(source_inherited.read_text()) if source_inherited.exists() else None
            if ancestors:
                source_cases.update({(row["task"],row["case"]): dict(complete=True, failures=[{}] if row["failed"] else [])
                                     for row in ancestors["cases"]})
            for row, _, _ in read_jsonl(args.resume_from.with_suffix(".cases.jsonl")):
                if row.get("event") == "case":
                    source_cases[(row["task"], row["case"])] = row
            inherited = dict(source=str(args.resume_from.resolve()), config=source_config, ancestors=ancestors,
                cases=[dict(task=task, case=case, failed=bool(row["failures"]))
                       for (task,case),row in source_cases.items() if row.get("complete", False)
                       and not any(error.get("exception") == "TimeoutError" for error in row["failures"])])
        inherited_path.write_text(json.dumps(inherited, indent=2)+"\n")
        temporary = config_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(config, indent=2)+"\n")
        temporary.replace(config_path)
    inherited = json.loads(inherited_path.read_text())
    completed = {(row["task"],row["case"]): (True,row["failed"]) for row in inherited["cases"]}
    if args.resume:
        for row, _, _ in read_jsonl(paths["cases"]):
            if row.get("event") == "case":
                completed[(row["task"], row["case"])] = (row.get("complete", False), bool(row["failures"]))
        for path in paths.values():
            if path.exists():
                repair_tail(path)
    skip = {key for key,(done,failed) in completed.items() if done and (not args.retry_failed or not failed)}
    skipped_failed = sum(completed[key][1] for key in skip)
    work, expected, skipped = {}, 0, 0
    for task in tasks:
        names = inventory(args.export, task)
        if args.cases:
            names = [name for name in names if name in args.cases]
        expected += len(names)
        pending = [name for name in names if (task,name) not in skip]
        skipped += len(names)-len(pending)
        if pending:
            work[task] = pending
    started = time.monotonic()
    lock, cancel, stop = Lock(), Event(), Event()
    total = passed = complete = done_tasks = 0
    counts, reasons, phases, events = Counter(), Counter(), Counter(), Counter()
    timings, examples, active = defaultdict(float), defaultdict(list), {}
    handles = {name: path.open("a" if args.resume else "w", buffering=1) for name,path in paths.items()}

    def receive(row):
        nonlocal total, passed, complete, done_tasks
        event, task = row.get("event"), row["task"]
        with lock:
            if event == "inventory":
                return
            if event == "case_start":
                active[task] = dict(case=row["case"], phase="gold_ingest", since=time.monotonic())
                return
            if event == "cursor":
                active[task] = dict(case=row["case"], phase=row["cursor"]["location"], since=time.monotonic())
                return
            if event == "task_end":
                done_tasks += 1
                active.pop(task, None)
                return
            target = "cases" if event == "case" else "mutants" if event in ("mutant", "mutant_failure") else "draws"
            handles[target].write(json.dumps(row, separators=(",", ":"))+"\n")
            events[event] += 1
            if event == "task_failure":
                reasons["task_worker/"+row["reason"].split(":",1)[0]] += 1
            if event != "case":
                return
            active.pop(task, None)
            total += 1
            passed += not row["failures"]
            complete += bool(row["complete"])
            counts.update(row["counts"])
            for key,value in row.get("timings", {}).items():
                timings[key] += value
            phases.update(row["passed_phases"])
            for error in row["failures"]:
                key = error["phase"]+"/"+error.get("category",error["exception"])
                reasons[key] += 1
                if len(examples[key]) < 5:
                    examples[key].append(dict(task=task, case=row["case"], **error))

    def progress():
        with lock:
            elapsed = time.monotonic()-started
            phases_now = Counter(value["phase"] for value in active.values())
            print(f"{done_tasks}/{len(work)} tasks; {total}/{expected-skipped} new cases, {passed} passed; "
                  f"skipped={skipped}; elapsed={elapsed:.1f}s rate={total/max(elapsed,1e-9):.2f} cases/s; "
                  f"active={dict(phases_now)}; oldest_phase_s={max((time.monotonic()-value['since'] for value in active.values()),default=0):.1f}; "
                  f"failures={dict(reasons)}", file=sys.stderr, flush=True)
    def ticker():
        while not stop.wait(1):
            progress()
    progress()
    heartbeat = Thread(target=ticker, daemon=True)
    heartbeat.start()
    interrupted = False
    try:
        with tempfile.TemporaryDirectory(prefix=args.output.stem+".workers-", dir=args.output.parent) as job_dir:
            pool = ThreadPoolExecutor(max_workers=args.workers)
            jobs = {}
            try:
                jobs = {pool.submit(run_task,args,task,names,receive,cancel,Path(job_dir)): task for task,names in work.items()}
                for future in as_completed(jobs):
                    try:
                        future.result()
                    except Exception as exc:
                        receive(dict(event="task_failure", task=jobs[future], remaining_cases=len(work[jobs[future]]),
                                     reason=f"supervisor:{type(exc).__name__}: {exc}"))
                        receive(dict(event="task_end", task=jobs[future], remaining_cases=len(work[jobs[future]])))
            except BaseException:
                cancel.set()
                raise
            finally:
                pool.shutdown(wait=True, cancel_futures=True)
    except KeyboardInterrupt:
        interrupted = True
    finally:
        stop.set()
        heartbeat.join()
        for handle in handles.values():
            handle.close()
    summary = dict(stage=2, scope="this_invocation", tasks=len(tasks), active_tasks=len(work),
        expected_cases=expected, checked_cases=total, complete_cases=complete, passed_cases=passed,
        failed_cases=total-passed, skipped_cases=skipped, skipped_failed_cases=skipped_failed,
        remaining_cases=expected-skipped-complete, inherited_checkpoint=str(inherited_path), failure_counts=dict(reasons), failure_examples=dict(examples),
        phase_pass_counts=dict(phases), counts=dict(counts), events=dict(events), timings=dict(timings),
        seconds=round(time.monotonic()-started,3), streams_digest=arclog.streams_digest(),
        export=str(args.export), corpus=str(args.corpus), policy=policy, reader=reader,
        status="interrupted" if interrupted else "needs_fix" if reasons or skipped_failed or expected-skipped-complete else "passed")
    temporary = args.output.with_suffix(".tmp")
    temporary.write_text(json.dumps(summary,indent=2)+"\n")
    temporary.replace(args.output)
    print(json.dumps(summary,indent=2),flush=True)
    if interrupted:
        raise SystemExit(130)


if __name__ == "__main__":
    main()
