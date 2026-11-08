"""The work and the counters of each request that the writer makes along each gold stream of the feature corpus.

    PYTHONPATH=SITE python gold_request_work.py --out OUT.jsonl.zst --corpus DIR --tasks-dir DIR [--shard K/N] [--limit N] [--world closed|open] [--cap N] [--successors N] [--atoms | --no-atoms] [TASK ...]

Run it with the interpreter of the site to test, with `PYTHONPATH` set to that site and without `-I`: it imports that site's `arclog` and `zstandard`.
Give `--corpus` and `--tasks-dir` as absolute paths.

For each task of `DIR/*/mutants/<task>.json.zst` (task 981571dc is left out, and its file is never opened), it reads the field `gold`, the gold program, makes a
session with `request_work_cap` `--cap` (default 2^34) in the `--world` (default closed), decodes the gold program as a stream token by token, as the model wrote
it, and at each such token makes the requests of the writer (`model/study/sampler/writer.py`) at the prefix before the token:

    admissible, admits, forced, counts, rows, projections, atoms (unless `--no-atoms`), successor_tables
        on the decoder at the prefix;
    step, admissible_fork
        on a fork of that decoder, the step of the token and the mask after it;
    advance, step_tables
        the step of the token on the decoder itself, and `step_tables` of the result with `bodies` and `rows`, chained as `before`.

Before the first token it makes `base_tables`, and after the last it makes `attempts` and `attempts_counted`. Over the whole gold program it makes `gold_tables` of a
`StudyTaskEvaluator` with the same settings. Each call is one request, and `arclog.request_stats()` gives its work and counters.
`successor_tables` takes the gold token and the first `--successors` (default 32) admissible tokens.

OUT is a zstd stream of JSON lines, one for each task, flushed after each task, so a run that stops leaves the tasks it finished. A run that starts again reads OUT,
keeps its lines and makes the tasks it lacks. A line holds ids and counts, no grid and no table row:
    task      the task id
    tokens    the count of tokens that the model wrote
    kinds     {kind: {calls, work, at, gauges}}: for each kind of request, its calls, the largest work of one of them and the model token index `at` of that call, and
              `gauges`, the largest value of each capped quantity over its calls (`request_work` is the work)
    caps      {gauge: cap}, the cap each gauge ran under
    unexercised  [gauge], the gauges that no request of the stream gave a cap, so that the stream says nothing about their caps. A gold stream exercises no study-pair cap
              (`study_row_work`, `pair_comparisons`) and none of the study filters' `max_work`, which `evaluate_pair` and the filters count in their own results.
    vocabulary  {relations, columns, labels: {max, cap}}: the relation slots (the largest slot index + 1 over the stream's tokens), the column positions
              (the largest position + 1) and the labels of one form (the largest label slot + 1 within a top-level form) that the stream uses, and the vocabulary caps
              of the session's settings. The engine has no counter for these. `box_margin` and `labeling_nodes` are gauges of the request like the others: each holds the work of the threads of that request.
    hits      [{kind, token, form, name, cap, hits, max, limit}], one for each request that passed a cap: the kind of request, the model token index, the index and
              the name of the top-level form that the token writes, the gauge, the times it passed, its largest value and its cap. A `gold_tables` call that returns a
              table with a stop has a hit with the cap `table_status` and the form of that stop.
    stops     {"kind:Stop": count}, the stops that the consistency of a step reports
    errors    {kind: {exception: count}}
    gold_tables  null, or {status, reason, form} of its report
    ended     whether the decode ended
    stop      null, or {token, kind}: the index of the model token at which the decode stopped, and the class of the exception
    seconds   the task's wall time
The last line is {"done": true, "tasks": N, "hits": N, "stopped": N} for the tasks of this run. `--shard K/N` runs the tasks at the places K, K+N, ... of the sorted
list, so N processes run one each, each with an OUT of its own.
"""

import argparse
import glob
import io
import json
import os
import re
import sys
import time

os.environ.setdefault("ARCLOG_THREADS", "1")

import arclog  # noqa: E402
import zstandard  # noqa: E402

LEFT_OUT = {"981571dc"}
TASK = CASE = "gold"


def read_json(path):
    with open(path, "rb") as handle:
        return json.load(zstandard.ZstdDecompressor().stream_reader(handle))


def read_lines(path):
    """The complete JSON lines of OUT, which a run that was killed may have left with a partial last frame."""
    lines = []
    if not os.path.exists(path):
        return lines
    with open(path, "rb") as handle:
        reader = io.TextIOWrapper(zstandard.ZstdDecompressor().stream_reader(handle, read_across_frames=True), encoding="utf-8")
        try:
            for line in reader:
                try:
                    lines.append(json.loads(line))
                except json.JSONDecodeError:
                    break
        except zstandard.ZstdError:
            pass
    return lines


def top_level_forms(text):
    """The text of each top-level form of an S-expression program."""
    forms, depth, start = [], 0, 0
    for at, char in enumerate(text):
        if char == "(":
            if depth == 0:
                start = at
            depth += 1
        elif char == ")":
            depth = max(depth - 1, 0)
            if depth == 0:
                forms.append(text[start : at + 1])
    return forms


def form_name(form):
    """`KIND &name` of the head of a top-level form."""
    found = re.match(r"\(\s*([A-Za-z_]+)(?:\s+(&?[^\s()]+))?", form)
    return " ".join(part for part in found.groups() if part) if found else "?"


def mask_ids(mask):
    ids = []
    for place, byte in enumerate(mask):
        if byte:
            ids.extend(place * 8 + bit for bit in range(8) if byte >> bit & 1)
    return ids


def top_of(path):
    if path is None:
        return None
    if isinstance(path, str):
        return int(path.split(".")[0]) if path else None
    return int(path[0]) if len(path) else None


class Meter:
    """The requests of one stream: the largest work and counters of each kind, and the hits."""

    def __init__(self):
        self.kinds, self.hits, self.errors, self.stops, self.caps, self.names = {}, [], {}, {}, {}, set()

    def run(self, kind, token, form, call):
        """The result of `call` and whether it raised, with the request of the call noted under `kind`."""
        failed, result = False, None
        try:
            result = call()
        except (KeyboardInterrupt, SystemExit):
            raise
        except BaseException as error:  # a panic of the engine is a BaseException
            failed = True
            by_type = self.errors.setdefault(kind, {})
            by_type[type(error).__name__] = by_type.get(type(error).__name__, 0) + 1
        self.note(kind, token, form, arclog.request_stats())
        return result, failed

    def note(self, kind, token, form, stats):
        entry = self.kinds.setdefault(kind, {"calls": 0, "work": 0, "at": None, "gauges": {}})
        entry["calls"] += 1
        if stats is None:
            return
        self.caps["request_work"] = stats["cap"]
        if stats["work"] >= entry["work"]:
            entry["work"], entry["at"] = stats["work"], token
        entry["gauges"]["request_work"] = max(entry["gauges"].get("request_work", 0), stats["work"])
        for name, gauge in stats["gauges"].items():
            self.names.add(name)
            if gauge["cap"]:
                self.caps[name] = gauge["cap"]
            entry["gauges"][name] = max(entry["gauges"].get(name, 0), gauge["max"])
            if gauge["hits"]:
                self.hits.append({"kind": kind, "token": token, "form": form[0], "name": form[1], "cap": name, "hits": gauge["hits"], "max": gauge["max"], "limit": gauge["cap"]})

    def stop(self, kind, consistency):
        stop = getattr(consistency, "stop", None)
        if stop is not None:
            key = f"{kind}:{stop}"
            self.stops[key] = self.stops.get(key, 0) + 1


def gold_tables(meter, task, gold, tasks_dir, settings, forms):
    """`gold_tables` over the gold program, and the stop of its report, if it has one."""
    evaluator = arclog.StudyTaskEvaluator(task, tasks_dir, settings, compact=True)
    program = arclog.StudyProgram.from_sexp(gold, settings)
    result, failed = meter.run("gold_tables", -1, (None, "gold_tables"), lambda: evaluator.gold_tables(program))
    if failed or result is None:
        return None
    report = json.loads(result[0])
    status = {"status": report.get("status"), "reason": report.get("reason"), "form": None}
    if report.get("status") not in (None, "complete"):
        found = re.search(r"PathStep\((\d+)\)", str(report.get("form", "")))
        status["form"] = int(found.group(1)) if found else None
        name = forms[status["form"]] if status["form"] is not None and status["form"] < len(forms) else "?"
        meter.hits.append({"kind": "gold_tables", "token": -1, "form": status["form"], "name": name, "cap": "table_status", "hits": 1, "max": 0, "limit": 0, "reason": status["reason"]})
    return status


def vocabulary_use(vocabulary, ids, paths, settings):
    """The slots of the vocabulary that a stream uses, with the vocabulary caps (the engine has no counter for them)."""
    relations = columns = 0
    labels, form = {}, None
    for index, id_ in enumerate(ids):
        top = top_of(paths[index]) if index < len(paths) else None
        form = top if top is not None else form
        kind, name = vocabulary.kind(int(id_)), vocabulary.name(int(id_))
        if kind == "relation":
            relations = max(relations, int(name[2:]) + 1)  # &r<slot>
        elif kind == "column":
            columns = max(columns, int(name[1:]) + 1)  # :<position>
        elif kind == "label":
            labels[form] = max(labels.get(form, 0), int(name[1:]) + 1)  # L<slot>
    return {
        "relations": {"max": relations, "cap": settings.relations},
        "columns": {"max": columns, "cap": settings.columns},
        "labels": {"max": max(labels.values(), default=0), "cap": settings.labels, "form": max(labels, key=labels.get) if labels else None},
    }


def task_line(task, mutants, tasks_dir, world, args):
    started = time.time()
    gold = mutants["gold"]
    forms = [form_name(form) for form in top_level_forms(gold)]
    text = open(os.path.join(tasks_dir, task + ".json")).read()
    settings = arclog.DecodeSettings(request_work_cap=args.cap)
    session = arclog.Session(arclog.Task.from_json(text, world), settings)
    ids, model, paths = arclog.StudyProgram.from_sexp(gold, session.settings).decode_stream()
    meter = Meter()
    vocabulary = vocabulary_use(session.vocabulary, ids, paths, session.settings)
    for name, use in vocabulary.items():
        if use["max"] > use["cap"]:
            meter.hits.append({"kind": "stream", "token": -1, "form": use.get("form"), "name": "vocabulary", "cap": "vocabulary_" + name, "hits": 1, "max": use["max"], "limit": use["cap"]})

    def form_at(index):
        top = top_of(paths[index]) if index is not None and index < len(paths) else None
        return (top, forms[top] if top is not None and top < len(forms) else "?")

    dec = session.decoder()
    meter.run("base_tables", -1, (None, "base"), lambda: arclog.base_tables(dec, TASK, CASE, rows=True))
    stop, before, written = None, None, 0
    for index, (id_, is_model) in enumerate(zip(ids, model)):
        if not is_model:
            continue
        id_, form = int(id_), form_at(index)
        mask, _ = meter.run("admissible", written, form, dec.admissible)
        admissible = mask_ids(mask) if mask is not None else []
        meter.run("admits", written, form, lambda: dec.admits([id_] + admissible[:8]))
        meter.run("forced", written, form, lambda: dec.forced(id_))
        counts, _ = meter.run("counts", written, form, dec.counts)
        if counts is not None:
            example = 0 if len(counts) > 1 else None
            meter.run("rows", written, form, lambda: dec.rows(example))
        meter.run("projections", written, form, dec.projections)
        if args.atoms:
            meter.run("atoms", written, form, lambda: dec.atoms())
        successors = [id_] + [other for other in admissible[: args.successors] if other != id_]
        meter.run("successor_tables", written, form, lambda: arclog.successor_tables(dec, successors, TASK, CASE, before=before, rows=True))
        fork = dec.fork()
        stepped, failed = meter.run("step", written, form, lambda: fork.step(id_))
        if not failed:
            meter.run("admissible_fork", written, form, lambda: fork.fork().admissible())
        advanced, failed = meter.run("advance", written, form, lambda: dec.step(id_))
        if failed:
            stop = {"token": written, "kind": next(iter(meter.errors.get("advance", {"?": 0})))}
            break
        for kind, result in (("step", stepped), ("advance", advanced)):
            if result is not None and result[1] is not None:
                meter.stop(kind, result[1])
        after, _ = meter.run("step_tables", written, form, lambda: arclog.step_tables(dec, TASK, CASE, True, before, by_assignment=True, rows=True))
        if after is not None:
            before = after
        written += 1
    if stop is None and dec.ended:
        meter.run("attempts", written, (None, "end"), dec.attempts)
        meter.run("attempts_counted", written, (None, "end"), dec.attempts_counted)
    table_status = gold_tables(meter, task, gold, tasks_dir, settings, forms)
    return {
        "task": task,
        "tokens": written,
        "kinds": meter.kinds,
        "caps": meter.caps,
        "unexercised": sorted(meter.names - set(meter.caps)),
        "vocabulary": vocabulary,
        "hits": meter.hits,
        "stops": meter.stops,
        "errors": meter.errors,
        "gold_tables": table_status,
        "ended": bool(dec.ended),
        "stop": stop,
        "seconds": round(time.time() - started, 1),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("tasks", nargs="*")
    parser.add_argument("--out", required=True)
    parser.add_argument("--corpus", required=True, help="the directory that holds <split>/mutants/<task>.json.zst, as an absolute path")
    parser.add_argument("--tasks-dir", required=True, help="the directory of the task files, as an absolute path")
    parser.add_argument("--shard", default="0/1")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--world", choices=["closed", "open"], default="closed")
    parser.add_argument("--cap", type=int, default=1 << 34, help="the request work cap of every request (default 2^34)")
    parser.add_argument("--successors", type=int, default=32)
    parser.add_argument("--atoms", action=argparse.BooleanOptionalAction, default=True, help="request the candidate atoms at each prefix, as the atom writer does (default on)")
    args = parser.parse_args()
    if not hasattr(arclog, "request_stats"):
        sys.exit("this arclog has no request_stats")
    world = arclog.World.Closed if args.world == "closed" else arclog.World.Open
    shard, shards = (int(part) for part in args.shard.split("/"))
    files = {}
    for path in glob.glob(os.path.join(args.corpus, "*", "mutants", "*.json.zst")):
        task = os.path.basename(path)[: -len(".json.zst")]
        if task not in LEFT_OUT and (not args.tasks or task in args.tasks):
            files.setdefault(task, path)
    names = sorted(files)[shard::shards][: args.limit]
    kept = [line for line in read_lines(args.out) if "task" in line]
    finished = {line["task"] for line in kept}
    counts = {"tasks": 0, "hits": 0, "stopped": 0}
    if kept:
        # The kept lines go to a new file first, so that a partial last frame of OUT never stands before a new line.
        with open(args.out + ".tmp", "wb") as handle:
            writer = zstandard.ZstdCompressor(level=6).stream_writer(handle)
            for line in kept:
                writer.write((json.dumps(line, separators=(",", ":")) + "\n").encode())
                writer.flush(zstandard.FLUSH_FRAME)
            writer.close()
        os.replace(args.out + ".tmp", args.out)
    with open(args.out, "ab" if kept else "wb") as handle:
        writer = zstandard.ZstdCompressor(level=6).stream_writer(handle)

        def write(line):
            writer.write((json.dumps(line, separators=(",", ":")) + "\n").encode())
            writer.flush(zstandard.FLUSH_FRAME)

        for task in names:
            if task in finished:
                continue
            try:
                line = task_line(task, read_json(files[task]), args.tasks_dir, world, args)
            except Exception as error:
                line = {"task": task, "tokens": 0, "kinds": {}, "caps": {}, "hits": [], "stops": {}, "errors": {}, "unexercised": [], "vocabulary": None, "gold_tables": None, "ended": False, "stop": {"token": -1, "kind": type(error).__name__}, "seconds": 0}
            write(line)
            counts["tasks"] += 1
            counts["hits"] += len(line["hits"])
            counts["stopped"] += line["stop"] is not None
            work = max((kind["work"] for kind in line["kinds"].values()), default=0)
            print(f"{task} work={work} hits={len(line['hits'])} stop={line['stop']} seconds={line['seconds']}", file=sys.stderr, flush=True)
        write({"done": True, **counts})
        writer.close()
    print(json.dumps(counts), file=sys.stderr)


if __name__ == "__main__":
    main()
