"""Compare v5/v6 draw-kind shares on decoded gold ASTs, before study filters.

One process per task, loaded once. Draw records stream immediately to JSONL.
Use --pairs to inspect every point of the task/cases represented in a batch.
"""
import argparse
import hashlib
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
from threading import Lock
import time

from check_stage1_all import CaseDeadline, inventory


POLICY = "complete-domain-unique-text-gold-names-v7"
REFERENCE = "complete-domain-without-replacement-v5"


def worker(args):
    import arclog
    names, offsets, ids, flags = inventory(args.export, args.worker, True)
    selected = set(args.cases or names)
    settings = arclog.DecodeSettings(mutation_node_cap=args.draw_nodes, rule_tests=False)
    task = arclog.Task.from_json((args.tasks / (args.worker + ".json")).read_text(), arclog.World.Closed)
    session = arclog.Session(task, settings, session_bytes=arclog.STUDY_SESSION_BYTES)
    def deadline(*_):
        raise CaseDeadline("case deadline")
    signal.signal(signal.SIGALRM, deadline)
    for index, name in enumerate(names):
        if name not in selected:
            continue
        signal.setitimer(signal.ITIMER_REAL, args.case_seconds)
        try:
            lo, hi = offsets[index:index + 2]
            gold = arclog.StudyProgram.from_stream(session, ids[lo:hi], [int(f) for f in flags[lo:hi]])
            for point in gold.points():
                for k in args.ks:
                    report = json.loads(gold.audit_draw_order(point, k, args.count, args.seed,
                        source_revision=args.export.name, task=args.worker, case=name,
                        operation="substitute"))
                    if report.get("before_policy") != REFERENCE or report.get("after_policy") != POLICY:
                        raise RuntimeError("native reference/production policies differ from audit contract")
                    for side in ("before", "after"):
                        counts = report[side]["counts"]
                        edits = sum(v for key,v in counts.items() if key.startswith("drawn_edit_kind:"))
                        if edits != k * counts.get("specs_drawn", 0):
                            raise RuntimeError("draw-kind counters do not account for every selected edit")
                    before = report["before"]["counts"]
                    after = report["after"]["counts"]
                    if not any(key.startswith("domain_search_stopped:") for counts in (before, after) for key in counts):
                        if before.get("specs_drawn",0) > after.get("specs_drawn",0):
                            raise RuntimeError("expanded legal domain lost valid assignments")
                    print(json.dumps(dict(event="draw", task=args.worker, case=name,
                        body=point.body_path, K=k, requested=args.count, **report)), flush=True)
        except (Exception, CaseDeadline) as error:
            print(json.dumps(dict(event="failure", task=args.worker, case=name,
                reason=type(error).__name__ + ": " + str(error))), flush=True)
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            session.reset_program_replay()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export", type=Path, default=Path("/Users/davidlu/code/arc-workspace/work/lm/data-full-9fac8128"))
    parser.add_argument("--tasks", type=Path, required=True)
    parser.add_argument("--current", type=Path, default=Path("run/CURRENT.json"))
    parser.add_argument("--runtime-manifest", type=Path, help="explicit immutable candidate ready.json; otherwise use CURRENT")
    parser.add_argument("--draw-nodes", type=int, default=1 << 14)
    parser.add_argument("--pairs", type=Path)
    parser.add_argument("--only", nargs="+")
    parser.add_argument("--ks", type=int, nargs="+", default=[1, 2, 3])
    parser.add_argument("--count", type=int, default=10)
    parser.add_argument("--seed", type=int, default=4231)
    parser.add_argument("--case-seconds", type=float, default=10)
    parser.add_argument("--workers", type=int, default=int(os.environ.get("ARC_HEAVY_CPUS", "1")))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--worker", help=argparse.SUPPRESS)
    parser.add_argument("--cases", nargs="+", help=argparse.SUPPRESS)
    args = parser.parse_args()
    for key in ("ARCLOG_THREADS", "RAYON_NUM_THREADS", "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
        os.environ[key] = "1"
    # The study harness owns selection and authentication, shared with the
    # kept-stream checker. Never maintain a second bootstrap here.
    provenance_path = args.current.resolve().parent / "provenance.py"
    sys.path.insert(0, str(provenance_path.parent))
    import provenance as runtime_provenance
    if Path(runtime_provenance.__file__).resolve() != provenance_path:
        raise RuntimeError("imported provenance module differs from the study harness")
    selection = runtime_provenance.select_runtime(args.current, args.runtime_manifest)
    ready = selection["ready"]
    import arclog
    if arclog.StudyProgram.mutation_policy() != POLICY:
        raise RuntimeError("v6 audit requires an immutable v6 runtime; selected " + ready["revision"])
    if args.worker:
        worker(args)
        return
    budget = int(os.environ.get("ARC_HEAVY_CPUS", "1"))
    if not 1 <= args.workers <= budget or min(args.ks) < 1 or args.count < 1 or args.case_seconds <= 0 or args.draw_nodes <= 0:
        parser.error("positive counts/deadlines required; workers must fit run_heavy CPU budget")
    selected = defaultdict(set)
    if args.pairs:
        import gzip
        opener = gzip.open if args.pairs.suffix == ".gz" else open
        with opener(args.pairs, "rt") as source:
            for line in source:
                row = json.loads(line)
                selected[row["task"]].add(row["case"])
    tasks = sorted(args.only or selected or json.loads((args.export / "keys.json").read_text()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    done = draws = 0
    counts = {side: Counter() for side in ("before", "after")}
    failures = Counter()
    lock = Lock()
    def progress():
        elapsed = time.monotonic() - started
        rate = done / max(elapsed, .001)
        eta = f"{(len(tasks)-done)/rate:.1f}s" if rate else "pending"
        print(f"{done}/{len(tasks)} tasks; {draws} draw comparisons; elapsed={elapsed:.1f}s "
              f"rate={rate:.2f} tasks/s ETA={eta}; failures={dict(failures)}", flush=True)
    provenance = dict(ready=ready, build=selection["build"],
                      selector_module=str(provenance_path),
                      selector_sha256=hashlib.sha256(provenance_path.read_bytes()).hexdigest(),
                      python=sys.executable, prefix=sys.prefix,
                      script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                      export=str(args.export.resolve()), tasks=str(args.tasks.resolve()),
                      reference_policy=REFERENCE, production_policy=POLICY,
                      ks=args.ks, seed=args.seed, requested=args.count,
                      draw_nodes=args.draw_nodes, case_seconds=args.case_seconds)
    with args.output.with_suffix(".jsonl").open("w", buffering=1) as records:
        records.write(json.dumps(dict(event="start", provenance=provenance, total=len(tasks))) + "\n")
        records.flush()
        def run(task):
            nonlocal draws
            command = [sys.executable, "-B", str(Path(__file__).resolve()), "--worker", task,
                "--export", str(args.export), "--tasks", str(args.tasks),
                "--current", str(args.current.resolve()), "--draw-nodes", str(args.draw_nodes),
                "--ks", *map(str,args.ks),
                "--count", str(args.count), "--seed", str(args.seed), "--case-seconds", str(args.case_seconds),
                "--output", str(args.output)]
            if args.runtime_manifest is not None:
                command += ["--runtime-manifest", str(args.runtime_manifest.resolve())]
            if selected.get(task):
                command += ["--cases", *sorted(selected[task])]
            env = dict(os.environ, ARCLOG_THREADS="1", RAYON_NUM_THREADS="1", OMP_NUM_THREADS="1")
            with subprocess.Popen(command, stdout=subprocess.PIPE, text=True, env=env) as process:
                for line in process.stdout:
                    row = json.loads(line)
                    with lock:
                        records.write(line)
                        records.flush()
                        if row["event"] == "draw":
                            draws += 1
                            for side in counts:
                                counts[side].update(row[side]["counts"])
                                for reason, count in row[side]["counts"].items():
                                    if reason.startswith("domain_search_stopped:"):
                                        failures[side + "/" + reason] += count
                        else:
                            failures[row["reason"]] += 1
                if process.wait():
                    with lock:
                        failures["worker_exit"] += 1
        progress()
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            pending = {pool.submit(run, task) for task in tasks}
            while pending:
                complete, pending = wait(pending, timeout=2, return_when=FIRST_COMPLETED)
                for job in complete:
                    job.result()
                    done += 1
                with lock:
                    progress()
    summary = dict(provenance=provenance, tasks=len(tasks), draws=draws, failures=dict(failures),
                   seconds=time.monotonic()-started, counts={k:dict(v) for k,v in counts.items()})
    for side in counts:
        shares = {}
        for prefix in ("domain_primitive_kind:", "drawn_edit_kind:"):
            values = {k.removeprefix(prefix):v for k,v in counts[side].items() if k.startswith(prefix)}
            total = sum(values.values())
            shares[prefix.rstrip(":")] = {k:dict(count=v, share=v/total if total else None) for k,v in values.items()}
        summary[side] = shares
    args.output.write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2), flush=True)
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
