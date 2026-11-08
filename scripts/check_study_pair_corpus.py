"""Stream stage-3 runtime observations across the actual exported corpus.

No tests. Defaults to twelve parallel task workers, one K=1 mutant per mutation
point in every exported case. JSONL is flushed per point/pair; progress is
printed every second even while native calls are running. No corpus result
is accumulated in memory. Use --task / --case-limit / --point-limit for a
short run. Native tables can optionally be saved with --native-dir.
"""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, wait
import base64
import json
import os
from pathlib import Path
import struct
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent / "study"))
from check_stage1_all import inventory
from study_faults import fault_group, normalized_reason


def column(table, part, name):
    value = getattr(table, part)[name]
    if not isinstance(value, bytes):
        return value
    dtype = table.dtypes[f"{part}.{name}"]
    formats = {"uint8": "B", "int32": "i", "uint32": "I", "uint64": "Q", "int64": "q",
               "u1": "B", "i4": "i", "u4": "I", "u8": "Q", "i8": "q"}
    fmt = formats.get(dtype, formats.get(dtype.lstrip("<>=|")))
    if fmt is None:
        raise ValueError(f"unknown native column dtype {dtype}")
    return [v[0] for v in struct.iter_unpack("=" + fmt, value)]


def inspect_native(table, selected):
    """Check actual exported offsets and assignment references, without numpy."""
    n = len(column(table, "tables", "token"))
    stop = getattr(table, "materialization_stop", None)
    if selected < 0 or (selected >= n and not stop):
        raise ValueError(f"clause table {selected} outside {n} native tables")
    widths = column(table, "tables", "width")
    entry_tables = column(table, "entries", "table")
    kinds = column(table, "entries", "kind")
    rows = column(table, "entries", "rows")
    offsets = column(table, "entries", "offset")
    values = len(table.values) // 4
    for t, kind, count, offset in zip(entry_tables, kinds, rows, offsets):
        if t >= n:
            raise ValueError("native entry refers to absent table")
        if kind == 0 and offset + count * widths[t] > values:
            raise ValueError("native row run exceeds values buffer")
    for entry in column(table, "assigned", "entry"):
        if entry >= len(entry_tables):
            raise ValueError("native DET assignment refers to absent entry")
    return dict(tables=n, entries=len(entry_tables), values=values,
                clause_rows=[count for t, count in zip(entry_tables, rows) if t == selected] if selected < n else None,
                clause_available=selected < n, materialization_stop=stop)


def dump_native(table, path):
    def encode(v):
        return {"base64": base64.b64encode(v).decode()} if isinstance(v, bytes) else v
    parts = {part: {k: encode(v) for k, v in getattr(table, part).items()}
             for part in ("tables", "entries", "assigned", "projections", "projection_rows", "flows", "copies")}
    path.write_text(json.dumps(dict(dtypes=table.dtypes, values=encode(table.values),
                                   materialization_stop=getattr(table, "materialization_stop", None), **parts)) + "\n")


def checkpoints(path):
    """Read terminal cases and reference high-water marks, without retaining rows.

    A final torn write is ignored; malformed newline-terminated records fail.
    The returned byte offset allows --resume to remove only that torn tail.
    """
    done, references = set(), Counter()
    valid_end, needs_newline = 0, False
    with path.open("rb") as src:
        while line := src.readline():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                if line.endswith(b"\n"):
                    raise
                break
            valid_end = src.tell()
            needs_newline = not line.endswith(b"\n")
            if row.get("type") == "case":
                done.add((row["task"], row["case"]))
            if row.get("type") == "pair":
                ref = row["evaluation"].get("gold_observation_ref")
                if ref is not None:
                    references[row["task"]] = max(references[row["task"]], int(ref))
    return done, references, valid_end, needs_newline


def main():
    from execution_evidence import example_fit

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export", type=Path, default=Path("/Users/davidlu/code/arc-workspace/work/lm/data-full-9fac8128"))
    parser.add_argument("--tasks", type=Path,
                        help="task JSON directory; defaults to checkout data/tasks when present; required for archives without task data")
    parser.add_argument("--task", action="append")
    parser.add_argument("--jobs", type=int, default=12)
    parser.add_argument("--case-limit", type=int)
    parser.add_argument("--point-limit", type=int)
    parser.add_argument("--per-point", type=int, default=1)
    parser.add_argument("--k", type=int, default=1)
    parser.add_argument("--operation", choices=("mixed", "substitute", "delete"), default="mixed")
    parser.add_argument("--work-cap", type=int, default=1 << 20)
    parser.add_argument("--seed", type=int, default=4231)
    parser.add_argument("--output", type=Path, default=ROOT / "stage3-fast.jsonl")
    parser.add_argument("--native-dir", type=Path)
    parser.add_argument("--resume", action="store_true", help="append output, skipping its terminal cases and repairing a torn final row")
    parser.add_argument("--resume-from", action="append", type=Path, default=[], help="also skip terminal cases in this JSONL; repeatable, read-only")
    parser.add_argument("--case-manifest",type=Path,help="summary JSON whose fault_cases select task/case reproducers")
    parser.add_argument("--replay-identities",action="store_true",help="re-certify and evaluate the exact identities in the case manifest")
    parser.add_argument("--gold-tables",action="store_true",help="also inspect full gold tables and the native stream_tables path")
    args = parser.parse_args()
    if args.jobs < 1 or args.per_point < 1 or args.k < 1:
        parser.error("jobs, per-point and k must be positive")
    # Archived checkers have no implicit link back to a source checkout.
    # Reject missing data before opening output or launching task workers.
    if args.tasks is None:
        args.tasks = ROOT / "data/tasks"
        if not args.tasks.is_dir():
            parser.error("this checker has no bundled task data; provide --tasks PATH")
    if not args.tasks.is_dir():
        parser.error(f"--tasks is not a task directory: {args.tasks}")
    args.tasks = args.tasks.resolve()
    # One internal engine worker per concurrently evaluated case.
    os.environ["ARCLOG_THREADS"] = "1"
    import arclog
    if not hasattr(arclog, "StudyTaskEvaluator") or not hasattr(arclog.StudyTaskEvaluator, "finish_case"):
        parser.error("build the bounded-case performance wheel with build_stage3_perf.sh first")
    tasks = args.task or sorted(p.name for p in (args.export / "tasks").iterdir() if (p / "cases.npz").exists())
    selected=None;manifest_cases={}
    if args.case_manifest:
        selected={}
        for case in json.loads(args.case_manifest.read_text())["fault_cases"]:
            selected.setdefault(case["task"],set()).add(case["case"])
            manifest_cases[(case['task'],case['case'])]=case
        tasks=[task for task in tasks if task in selected]
    for task in tasks:
        task_file = args.tasks / f"{task}.json"
        if not task_file.is_file():
            parser.error(f"selected task data is missing: {task_file}")
    if args.replay_identities and (not args.case_manifest or not hasattr(arclog.StudyTaskEvaluator,'replay')):
        parser.error('--replay-identities needs a manifest and the exact-replay wheel')
    completed, observation_starts = set(), Counter()
    sources = list(args.resume_from)
    if args.resume and args.output.exists():
        sources.append(args.output)
    output_tail = None
    for source in dict.fromkeys(path.resolve() for path in sources):
        if source == args.output.resolve() and not args.resume:
            parser.error("output is a checkpoint input; use --resume to append safely")
        print(f"scanning checkpoint {source}", file=sys.stderr, flush=True)
        done, references, valid_end, needs_newline = checkpoints(source)
        completed.update(done)
        for task, ref in references.items():
            observation_starts[task] = max(observation_starts[task], ref)
        if source == args.output.resolve():
            output_tail = (valid_end, needs_newline)
    def selected_cases(task,names,skip=True):
        return [(i,name) for i,name in enumerate(names[:args.case_limit])
                if (selected is None or name in selected[task])
                and (not skip or (task,name) not in completed)]
    # Do not ingest an entire task's stream arrays or construct an evaluator
    # when all selected cases already have terminal checkpoint rows.
    pending, skipped = [], 0
    total = 0
    for task in tasks:
        names = inventory(args.export, task)
        if args.replay_identities:
            for _, case in selected_cases(task, names, False):
                if not manifest_cases[(task, case)].get("identities"):
                    parser.error(f"--replay-identities: no identities for task {task}, case {case!r}")
        remaining = len(selected_cases(task,names))
        skipped += len(selected_cases(task,names,False)) - remaining
        if remaining:
            pending.append(task)
            total += remaining
    tasks = pending
    started = time.monotonic()
    counts, lock, stop = Counter(), threading.Lock(), threading.Event()
    fault_groups, reasons, fault_examples, phase_totals = Counter(), Counter(), {}, Counter()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.native_dir:
        args.native_dir.mkdir(parents=True, exist_ok=True)
    if output_tail is not None:
        valid_end, needs_newline = output_tail
        with args.output.open("r+b") as repair:
            repair.seek(valid_end)
            repair.truncate()
            if needs_newline:
                repair.write(b"\n")
    out = args.output.open("a" if args.resume else "w", buffering=1)

    def emit(row):
        encoded=json.dumps(row,separators=(",",":"))+"\n"
        with lock:
            out.write(encoded)
            counts[row["type"]] += 1
            if "status" in row:
                counts["status:" + row["status"]] += 1
            if row["type"] == "pair":
                counts["pair_status:" + row["status"]] += 1
                counts["pair_gold_fits:" + str(row["evaluation"].get("gold_fits"))] += 1
            if row["type"] == "case":
                phase_totals.update(row.get("timings", {}))
            if row.get("reason"):
                counts["reason:" + row["reason"][:160]] += 1
                if row.get("status") == "fault":
                    reason=normalized_reason(row["reason"]); group=fault_group(reason)
                    fault_groups[group]+=1;reasons[reason]+=1
                    examples=fault_examples.setdefault(group,[])
                    if len(examples)<3:examples.append({k:row[k] for k in ("task","case","body","kind","reason") if k in row})

    def progress():
        while not stop.wait(1):
            with lock:
                done, pairs = counts["case"], counts["pair"]
                groups=dict(fault_groups)
            elapsed = time.monotonic() - started
            print(f"done {done}/{total} cases, {pairs} pairs, elapsed={elapsed:.1f}s, rate={done/max(elapsed, 1e-9):.2f} cases/s, {pairs/max(elapsed, 1e-9):.2f} pairs/s; faults={groups}", file=sys.stderr, flush=True)

    def run(task):
        names, offsets, ids, flags = inventory(args.export, task, True)
        settings = arclog.DecodeSettings(table_work_cap=args.work_cap, rule_tests=False)
        evaluator=arclog.StudyTaskEvaluator(task,str(args.tasks),settings,compact=True,observation_start=observation_starts[task])
        def run_case(i,case):
            context = dict(task=task, case=case)
            pairs = 0
            case_started=time.monotonic(); timings=Counter()
            try:
                lo, hi = offsets[i:i + 2]
                tick=time.monotonic()
                gold = evaluator.from_stream(ids[lo:hi], [int(f) for f in flags[lo:hi]])
                timings["ingest"]+=time.monotonic()-tick
                if args.gold_tables:
                    text,native=evaluator.gold_tables(gold);gold_report=json.loads(text)
                    emit(dict(type="gold_relations",**context,**gold_report))
                    streams,lines=arclog.stream_tables(task,str(args.tasks),[(ids[lo:hi],[int(f) for f in flags[lo:hi]])],settings=settings,bodies=False,names=[case])
                    for native in streams:
                        issues=[(part,key,i,reason) for part in ("tables","entries") for key in ("fault","extent_fault") if key in getattr(native,part) for i,reason in enumerate(getattr(native,part)[key]) if reason]
                        stops=[reason for part in ("tables","entries") for key,values in getattr(native,part).items() if key.endswith('_bound') for reason in values if reason]
                        if getattr(native, "materialization_stop", None):
                            stops.append(native.materialization_stop)
                        emit(dict(type="native_stream_gold",**context,status="fault" if issues else "stopped" if stops else "complete",reason="; ".join(dict.fromkeys(v[3] for v in issues)) if issues else "; ".join(dict.fromkeys(stops)) if stops else None,issues=issues,stops=stops,lines=lines))
                    del native, streams, lines
                points = gold.points()[:args.point_limit]
                def case_mutants():
                    historical=manifest_cases.get((task,case),{}).get('identities',[])
                    if args.replay_identities:
                        for identity in historical:
                            tick=time.monotonic()
                            try:
                                point,mutant=evaluator.replay(gold,json.dumps(identity))
                            except Exception as exc:
                                emit(dict(type="historical_refusal",**context,status="fault",reason=f"historical_spec_refused: {type(exc).__name__}: {exc}",identity=identity))
                                continue
                            timings['replay']+=time.monotonic()-tick
                            yield point,mutant
                        return
                    for point in points:
                        ctx=dict(context,body=point.body_path,clause=point.clause_path,kind=point.kind)
                        tick=time.monotonic()
                        specs,stats=gold.draw_specs(point,args.k,args.per_point,args.seed,source_revision=args.export.name,task=task,case=case,operation=args.operation)
                        elapsed=time.monotonic()-tick;timings['draw']+=elapsed
                        emit(dict(type='draw',**ctx,produced=len(specs),stats=json.loads(stats),elapsed=elapsed))
                        for spec in specs:yield point,gold.construct(spec)
                for point,mutant in case_mutants():
                    ctx=dict(context,body=point.body_path,clause=point.clause_path,kind=point.kind)
                    tick = time.monotonic()
                    report_json, g, m = evaluator.evaluate_pair(gold, point, mutant)
                    eval_elapsed=time.monotonic()-tick;timings["evaluate"]+=eval_elapsed
                    tick_native=time.monotonic()
                    report = json.loads(report_json)
                    native = None
                    if "table_indices" in report:
                        ix = report["table_indices"]
                        native = dict(gold=inspect_native(g, ix["gold_all"]), mutant=inspect_native(m, ix["mutant_all"]))
                        for comparison in report["comparisons"] + report["kept_comparisons"]:
                            # Complete Undefined comparisons have null counts;
                            # only comparable row sets have numeric diagnostics.
                            if comparison["status"] == "complete" and comparison["comparable"] is True:
                                if min(comparison["kept"], comparison["extra"], comparison["missing"]) < 0:
                                    raise ValueError("negative table comparison count")
                        for output in report["outputs"]:
                            for pair in output.get("gold_train",[]):
                                if example_fit(pair, context="kept gold train") is not True:
                                    raise ValueError("kept gold assignment lacks native accepted-set FITS")
                    timings["inspect_native"]+=time.monotonic()-tick_native
                    emit_started=time.monotonic()
                    emit(dict(type="pair", **ctx, status=report["status"], reason=report.get("reason"),
                              identity=json.loads(mutant.identity_json), evaluation=report, native=native,
                              elapsed=eval_elapsed,timings=report.get("timings",{})))
                    timings["emit"]+=time.monotonic()-emit_started
                    if args.native_dir:
                        stem = task + "-" + str(i) + "-" + "_".join(map(str, point.body_path)) + "-" + str(pairs)
                        dump_native(g, args.native_dir / (stem + "-gold.json"))
                        dump_native(m, args.native_dir / (stem + "-mutant.json"))
                    pairs += 1
                    # Release packed native buffers before constructing the
                    # next mutant, rather than while replacing its result.
                    del report_json, report, g, m, mutant
                emit(dict(type="case", **context, status="complete", points=len(points), pairs=pairs,elapsed=time.monotonic()-case_started,timings=dict(timings)))
            except Exception as exc:
                emit(dict(type="case", **context, status="fault", reason=f"{type(exc).__name__}: {exc}", pairs=pairs,elapsed=time.monotonic()-case_started,timings=dict(timings)))
            finally:
                evaluator.finish_case()
        for i, case in selected_cases(task,names):
            # The frame owns all gold/point/spec/native locals and is destroyed
            # on both success and failure before the next case is ingested.
            run_case(i,case)

    print(f"done 0/{total} cases, elapsed=0.0s, rate=0.00 cases/s; jobs={args.jobs}; skipped={skipped}; output={args.output}", file=sys.stderr, flush=True)
    ticker = threading.Thread(target=progress, daemon=True)
    ticker.start()
    try:
        with ThreadPoolExecutor(max_workers=args.jobs) as pool:
            futures = {pool.submit(run, task): task for task in tasks}
            for future in futures:
                try:
                    future.result()
                except Exception as exc:
                    emit(dict(type="task_fault", task=futures[future], status="fault", reason=f"{type(exc).__name__}: {exc}"))
    finally:
        stop.set()
        ticker.join()
        elapsed = time.monotonic() - started
        summary = dict(type="summary", done=counts["case"], total=total, skipped_cases=skipped, corpus_total=total+skipped, elapsed=elapsed,
                       rate=counts["case"] / max(elapsed, 1e-9), counts=dict(counts), fault_groups=dict(fault_groups),fault_reasons=dict(reasons),fault_examples=fault_examples,phase_seconds=dict(phase_totals),streams_digest=arclog.streams_digest())
        out.write(json.dumps(summary) + "\n")
        out.close()
        print(json.dumps(summary), flush=True)


if __name__ == "__main__":
    main()
