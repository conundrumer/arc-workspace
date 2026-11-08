"""The TableHash of each table at each gold query of the feature corpus, from a decode of the gold program as a stream.

    python -I engine/arclog-py/gold_table_hashes.py --out OUT.jsonl.zst [--corpus DIR] [--tasks-dir DIR] [--shard K/N] [--limit N] [--world closed|open] [--cap N] [TASK ...]

Run it with the interpreter of the site to test: it imports that site's `arclog` and `zstandard`. Run both sites with the same arguments and compare the outputs.
`-I` keeps the working directory and this file's directory off the module path, so `import arclog` finds the installed package.

For each task of `DIR/*/mutants/<task>.json.zst` (default `work/feature-spec/results/all-merged`; task 981571dc is left out), it reads the field `gold`, the gold
program, and the field `queries`, whose entries name a top-level form of the program (`form`) and the query's name. It reads the task file `TASKS/<task>.json`
(default `data/tasks`), makes a session with `table_work_cap` `--cap` (default 2^20) in the `--world` (default closed), decodes the gold program as a stream token
by token, as the model wrote it, and after each such token takes `arclog.step_tables` of the step, chained as `before`, with no body table, no rows and no summary.
It keeps each table of a finished query whose top-level form is the form of a gold query.

OUT is a zstd stream of JSON lines, flushed after each task, so a run that stops leaves the tasks it finished. A line has no table row and no grid:
    task      the task id
    queries   [[form, name], ...] of the gold queries
    tables    [{step, form, name, slot, query, hash, hashed, reason, types}, ...] in the order of the steps: `step` the index of the model's token, `form` the form's path,
              `slot` the relation's slot, `query` the QueryHash and `hash` the TableHash as 32 hexadecimal digits, `hashed` 1 where the engine gave a TableHash,
              `reason` why it gave none (empty where it gave one), `types` the type name of each column
    ended     whether the decode ended
    stop      null, or {token, kind}: the index of the model token at which the decode stopped, and the class of the exception
    seconds   the task's wall time
The last line is {"done": true, "tasks": N, "tables": N, "hashed": N, "stopped": N}.
A summary of the same counts goes to stderr. `--shard K/N` runs the tasks at the places K, K+N, ... of the sorted list, so N processes run one each.
"""

import argparse
import glob
import json
import os
import sys
import time

os.environ.setdefault("ARCLOG_THREADS", "1")

import arclog  # noqa: E402
import zstandard  # noqa: E402

LEFT_OUT = {"981571dc"}
CASE = "gold"


def read_json(path):
    with open(path, "rb") as handle:
        return json.load(zstandard.ZstdDecompressor().stream_reader(handle))


def cells(value, code):
    """The cells of a column that the export gives as a buffer or as a list."""
    if isinstance(value, (bytes, bytearray, memoryview)):
        return memoryview(value).cast("B").cast(code).tolist()
    return list(value)


def hex_run(value, at):
    """The 32 hexadecimal digits of the 16-byte little-endian value at place `at` of a buffer."""
    raw = bytes(memoryview(value).cast("B")[16 * at : 16 * at + 16])
    return format(int.from_bytes(raw, "little"), "032x")


def top_form(path):
    return int(path.split(".")[0]) if path else None


def task_line(task, mutants, tasks_dir, world, cap):
    started = time.time()
    gold = mutants["gold"]
    forms = {query["form"] for query in mutants["queries"]}
    text = open(os.path.join(tasks_dir, task + ".json")).read()
    session = arclog.Session(arclog.Task.from_json(text, world), arclog.DecodeSettings(table_work_cap=cap))
    ids, model, _ = arclog.StudyProgram.from_sexp(gold, session.settings).decode_stream()
    decoder = session.decoder()
    tables, stop, before, step = [], None, None, 0
    for token, (id_, written) in enumerate(zip(ids, model)):
        if not written:
            continue
        try:
            decoder.step(int(id_))
            before = arclog.step_tables(decoder, task, CASE, bodies=False, before=before, by_assignment=True, rows=False, summaries=False)
        except Exception as error:
            stop = {"token": token, "kind": type(error).__name__}
            break
        found = before.tables
        relation = cells(found["relation"], "i")
        has_query = cells(found["has_query"], "B")
        hashed = cells(found["hashed"], "B")
        reasons = found["unhashed_reason"]
        types = found["column_types"]
        for row, slot in enumerate(relation):
            top = top_form(found["form"][row])
            if slot < 0 or not has_query[row] or top not in forms:
                continue
            tables.append(
                {
                    "step": step,
                    "form": found["form"][row],
                    "name": found["name"][row],
                    "slot": slot,
                    "query": hex_run(found["query"], row),
                    "hash": hex_run(found["hash"], row),
                    "hashed": hashed[row],
                    "reason": reasons[row],
                    "types": list(types[row]),
                }
            )
        step += 1
    return {
        "task": task,
        "queries": [[query["form"], query["name"]] for query in mutants["queries"]],
        "tables": tables,
        "ended": bool(decoder.ended),
        "stop": stop,
        "seconds": round(time.time() - started, 1),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("tasks", nargs="*")
    parser.add_argument("--out", required=True)
    parser.add_argument("--corpus", default="work/feature-spec/results/all-merged")
    parser.add_argument("--tasks-dir", default="data/tasks")
    parser.add_argument("--shard", default="0/1")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--world", choices=["closed", "open"], default="closed")
    parser.add_argument("--cap", type=int, default=1 << 20)
    args = parser.parse_args()
    world = arclog.World.Closed if args.world == "closed" else arclog.World.Open
    shard, shards = (int(part) for part in args.shard.split("/"))
    files = {}
    for path in glob.glob(os.path.join(args.corpus, "*", "mutants", "*.json.zst")):
        task = os.path.basename(path)[: -len(".json.zst")]
        if task not in LEFT_OUT and (not args.tasks or task in args.tasks):
            files.setdefault(task, path)
    names = sorted(files)[shard::shards][: args.limit]
    counts = {"tasks": 0, "tables": 0, "hashed": 0, "stopped": 0}
    with open(args.out, "wb") as handle:
        writer = zstandard.ZstdCompressor(level=6).stream_writer(handle)

        def write(line):
            writer.write((json.dumps(line, separators=(",", ":")) + "\n").encode())
            writer.flush(zstandard.FLUSH_FRAME)

        for task in names:
            try:
                line = task_line(task, read_json(files[task]), args.tasks_dir, world, args.cap)
            except Exception as error:
                line = {"task": task, "queries": [], "tables": [], "ended": False, "stop": {"token": -1, "kind": type(error).__name__}, "seconds": 0}
            write(line)
            counts["tasks"] += 1
            counts["tables"] += len(line["tables"])
            counts["hashed"] += sum(table["hashed"] for table in line["tables"])
            counts["stopped"] += line["stop"] is not None
        write({"done": True, **counts})
        writer.close()
    print(json.dumps(counts), file=sys.stderr)


if __name__ == "__main__":
    main()
