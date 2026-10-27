"""Write the tables of the corpus's case programs as an index and flat int32 value arrays.

    python engine/arclog-py/tables_export.py <out dir> [--all-cases] [--bodies] [--projection-cap N] [--step-cap N] [--previous <export dir>] [<task id> ...]

It needs an interpreter with `arclog`, pandas and pyarrow, such as the LM work's venv. The code that decides a part's rows, values and fault lines is in `export_rows.py`. A change to that module, or to the engine code that writes the export's files (`engine/arclog-tables/src/`, `engine/arclog-tables-py/src/`, `engine/arclog/src/decode/`), runs `engine/arclog-py/roundtrip_check.py` with an `arclog` built from its tree before its merge.

Runs one `arclog.corpus_tables` call per task id, the longest first, on a queue of N worker processes (`run_in_worker`), where N is `ARCLOG_THREADS`
if set and `os.cpu_count()` otherwise, and checks the parts it writes on N processes. `replay_order` gives the order, which `lm/export.py` takes too: the tasks the export `--previous` gives no seconds for, or all tasks where none is given, by the largest
`.arcdata` file first, then the others by the one-thread seconds each took in that export (see `parts/<k>.tasks.txt`: the line's seconds times its units), longest first. A task whose one-thread seconds would end past half the mean load of a worker (the summed one-thread seconds of the
tasks to replay over N) is replayed in `units` units on `units` engine threads, the least count (at most N and at most the cases the previous export
holds for the task) at which its expected unit time, `1 + (units - 1) / 14` times its seconds over `units`, is under that bound; any other
task is replayed in one unit. The cut of a task into units is a function of the task and its count (see `arclog.corpus_tables`). With `--previous`, each task whose key (the sha256 of its `work/arclog/gen` `.arclog` and `.arcdata`, its files under `work/arclog/gen/cases/<task>/` with their names, its task file, every file of
the installed `arclog` package, the versions of Python, numpy, pandas and pyarrow, `export_rows.py` and the text of `settings.json`) equals the key in that export's
`tasks.txt` lines is not replayed: its rows, values (hard-linked) and fault lines are those of that export,
written as parts of the out dir. Its check lines are those of that export where the sha256 of `export_checks.py` (the checks digest) equals the one in its `tasks.txt` line,
and otherwise the part is checked again in the check processes. The run prints the counts reused, of them to check again, and to replay first.
An export with no key in its lines gives no reuse.
`--previous` changes no output file but the Ident numbers of a task it gives more than one unit. The script sets `ARCLOG_THREADS=1` for the engine, so a call
of a task of one unit runs on one engine thread, and each worker process starts the next task as its task ends and writes each task as its own part.
Where a worker process dies in a call, the export prints on stderr the task and the exit status, and runs the call once more in a new worker;
where that one dies too, the task's part holds no case, the fault line `death_line` gives, and a bare `tasks.txt` line. Writes to <out dir>:
  values/<task>/<case>.i32   raw int32 (np.fromfile), every row of the case: the rows of each entry, of each DET
                             at each entry's assignment, and of each projection at each entry, each row's cells in
                             column order, equal runs of a case sharing one offset (see `arclog.decode.columns`)
  parts/<k>.<name>.parquet   the rows of one part (`bases` has a file in a part with a cut case alone)
  parts/<k>.report.txt       the fault lines of the part's tasks
  parts/<k>.tasks.txt        one line `<task> <seconds> <units> <key> <checks digest>` per task of the part, the wall seconds of its call to 0.1 s,
                             the count of units it ran in, the task's reuse key and the checks digest (see `--previous`; a bare task id where the writer gives none), written last: a part is whole where it stands.
                             A line of an older export, `<task> <seconds> <key> <checks digest>`, gives its seconds with 1 unit and no reuse
  index.parquet    one row per (table, example, entry): task, case, concept, the table's columns, the entry's columns
  tables.parquet   one row per table: its columns, its `relation_name` (the relation as the case program writes it: `&x` for a
                   declared relation, `&<instance>.<port>` for an output or input of an instance; the fact relation's name for an
                   evidence table; null for a table that faulted, and, in an export of streams, for each table at a slot), and its
                   depth in the dependency graph (0 for an evidence table and each fact
                   relation), its candidate keys (`keys`, a list of lists of column indexes: the columns of each `ONE` mark of
                   its clause, none for `(ONE)`, the row's columns of a `CHOOSE`'s chosen relation, and `E` with `P` of
                   `ex_input` and `ex_output`; the registry declares no key of a component's output, so any other table
                   gives none), and, for the table of the relation of the atom of the `OUT` form, at which the decode ended, that selects the
                   Position column, the index of that column (`output_position`), and, for the table of the relation of the atom
                   that selects the Color column, the index of that column (`output_color`), which map to `P` and `Col` of
                   `ex_output`, with the entry's example as `E`; -1 in each other table; and, per DET in `det_relations` order, `det_columns`: the path of each of its columns in
                   `det_types` order (a slot named `slot <k>`, a record's field after a `.`), equal for one column of one
                   DET relation across the tables of a case, and an empty list where the engine knows none
  flows.parquet    one row per source of a column of a table, keyed by task, case, `table` and `column`: `kind` (copy 0,
                   computed 1, constant 2, lib name 3), `source_table` (the row of the source's table in the case, -1 where
                   the case gives none: a lib relation, a constant, a lib name), `source_relation`
                   (the relation as the program spells it, `ex_input` for a read of `input`, or the lib name), `source_column`
                   (its column index, -1 for a constant or a lib name, -2 for the example of the source's entry; with `det` >= 0 the index
                   is into the table's `det_types[det]`, the `DET`'s relation as the reading table holds it in assigned.parquet), `det` (the
                   source's place in the table's `det_relations`, -1 where it is none), `atom` (the path of the atom that
                   reads it, empty where none does) and `occurrence` (which row of the atom's relation the value comes from in one
                   derivation of the table's row: 0 for an atom of a clause, a computed flow included; for a column of an instance's
                   output that a row of the registry's `copies` maps, the index of that row among the output's; -1 for a flow of no atom
                   and for a column of an instance's output that no row maps). Two copy flows into one table with the same `atom`
                   and the same `occurrence` read one row of their source. A reader labels a column of `ex_output` as computed from the input where
                   every source it reaches through the flows is `ex_input` or a constant, as computed from the train outputs
                   where one is `ex_output` or a `DET` (a determination keeps the values at which the program solves every
                   train pair), and as neither where it reaches no source. An output of an instance that reads its own outputs has no flow from them
  copies           one row per declared row of the registry's `copies` that a component's output breaks, keyed by task and case:
                   `detail`, a sentence (the engine checks each declaration at each group of each instance it runs in the replay;
                   `export_checks.check_part` writes each row as a `copies` line of `checks.txt`)
  bases.parquet    written only by an export of streams (`export_streams` with `bases`) that cuts a case, and only for such a case: one row, task, case, `base` (another case of the task,
                   which has no base), `tokens` (the length `n` of the prefix of its stream's tokens that the two share) and `tables` (the count `k` of the base's tables before token
                   `n`: the 2 evidence tables and each table whose token is below `n`). The cut case holds only the tables of the steps at or after token `n`, numbered from `k`
                   in `table`: a `table`, `source_table` of a flow, or `table` of an entry or projection below `k` names the base's table of that number, so the case's whole list of tables is
                   the base's first `k` then its own. Its entries, assigned rows, projections and projection rows are its own alone (each numbered from 0 within the case), its `values` file holds the runs of its own rows alone, and
                   its `copies` rows are the stream's. A cut case whose stream equals its base's holds no table, entry or flow of its own. An export of the same streams without `bases` gives, for a cut
                   case, rows equal to the base's rows for tables below `k` and the case's own, but for the numbers of Idents, which depend on the session that interned them
  assigned.parquet one row per DET at an entry's assignment: task, case, entry, det, rows, offset
  projections.parquet    one row per projection (columns) and projection_rows.parquet one row per projection at an entry
  orientations.json  [encoding, name] of each orientation constant; an orientation cell is its encoding
  orientation_types.json  [type name, cells] of each orientation type without a parameter (Dir, DiagDir, Dir8, Axis, DiagAxis,
                   Axis4, D4, C4, Sym, Sense): the cells its columns admit; a Pose type admits D4's
  parts/<k>.checks.txt, checks.txt  one line `<task> <case>: <invariant>: <detail>` per violation of an invariant of this layout
                   that `export_checks.check_part` checks on each case of a part, in worker processes while later tasks replay
                   (tables, entries and runs, flows, the cells against their column types, keys, the evidence tables against the
                   task file, the copy flows' values against their source columns, the engine's rows against the declared rows of the registry's `copies`); a part is whole, with its `tasks.txt`, once its
                   checks are written; `python engine/arclog-py/export_checks.py <out dir> --all` checks an existing export the same way
  settings.json    the options the calls run under, written before the first task: {"projection_cap": N, "step_cap": N, "parts": [...]} with 10000 and 10000 (null for --step-cap 0, no cap)
                   where no --projection-cap is given, each other option given, and the names of the parts of the layout (`export_rows.PARTS`)
  report.txt       the fault lines, by task id
The whole files hold the rows of the parts sorted by task, in the order of the parts within a task.
A run on an out dir whose `settings.json` gives other options prints both and exits with status 2. Otherwise the
run takes as done each task id of a `parts/*.tasks.txt`, removes the files of a part with no `tasks.txt`, runs the
other tasks, and ends with the files a run that was not stopped gives.
Every 10 s a line gives `<k> of <n> tasks ended, <s> s, about <t> s left, running past 10 s: <id> <s> s <p>% ...`:
the ended tasks (done ones of an earlier run included), the seconds since the start, the seconds left (`?` while no
task has ended in this run), then the tasks running past 10 s, longest first (the first 10 and a count of the rest
where more), each with the seconds since its call started and the share of its model steps done, as
arclog.ReplayProgress gives them. `print_progress` prints it, and `lm/export.py` calls it too.

`export_streams(out, task, streams, names=None, settings=None, bodies=False, step_cap=10000, bases=None)` writes the same layout
for the token streams of one task, for a caller that imports the module: `streams` is a list of `(ids, model)`
pairs and `bases` the list of bases as `arclog.stream_tables` takes them. `out` must not exist or be empty (else `FileExistsError`). Its
`report.txt` holds, for each stream replayed, `<task> <case>: ended <kind> at token <index>` (`<kind>` the
consistency of the last `OUT` form the stream ends, or `ended none`), then the fault line of each stream that
faults (its tables up to the fault are kept) or lies past the cap. It writes no `settings.json`.
"""
import argparse, collections, enum, hashlib, json, os, shutil, signal, subprocess, sys, glob, threading, time, types
from typing import NamedTuple
import multiprocessing, traceback
from multiprocessing.connection import Connection
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, wait, FIRST_COMPLETED
import numpy as np
import pandas as pd
import pyarrow
import arclog
import export_checks
import export_rows
from export_rows import PARTS

ROOT = os.path.dirname(os.path.abspath(__file__)) + "/../.."
CORPUS, TASKS = f"{ROOT}/work/arclog/gen", f"{ROOT}/data/tasks"
HERE = os.path.dirname(os.path.abspath(__file__))
ROWS, CHECKER = f"{HERE}/export_rows.py", f"{HERE}/export_checks.py"


class TaskLine(NamedTuple):
    """A line of a `tasks.txt`: the task, its wall seconds and unit count where the writer gives them, and its key and checks digest where it gives them."""
    task: str
    seconds: float | None = None
    units: int = 1
    key: str | None = None
    checks: str | None = None

    @classmethod
    def parse(cls, line):
        """The line `<task>`, `<task> <seconds> <units>` or `<task> <seconds> <units> <key> <checks digest>`; the older `<task> <seconds>` and `<task> <seconds> <key> <checks digest>` give their seconds with 1 unit and no key."""
        w = line.split()
        if len(w) == 5:
            return cls(w[0], float(w[1]), int(w[2]), w[3], w[4])
        if len(w) == 3:
            return cls(w[0], float(w[1]), int(w[2]))
        return cls(w[0], float(w[1]) if len(w) > 1 else None)

    def text(self):
        return self.task + (f" {self.seconds:.1f} {self.units}" if self.seconds is not None else "") + (f" {self.key} {self.checks}" if self.key else "")

    @property
    def one_thread_seconds(self):
        return self.seconds * self.units


def read_task_lines(tasks_file):
    """The `TaskLine`s of a `tasks.txt`."""
    return [TaskLine.parse(line) for line in open(tasks_file).read().splitlines() if line.strip()]


def write_files(out, k, results, ran=None, keys=None):
    """Writes the files of the part `k` of the (task id, cases, lines) results but its `checks.txt` and `tasks.txt`, with the {task: (seconds, units)} and {task: (key, checks digest)} given.
    Returns the part's (task, case) pairs."""
    pairs = export_rows.write_rows(out, k, results)
    ran, keys = ran or {}, keys or {}
    lines = []
    for t, _, _ in results:
        seconds, units = ran.get(t, (None, 1))
        key, checks = keys.get(t, (None, None))
        lines.append(TaskLine(t, seconds, units, key, checks).text() + "\n")
    with open(f"{out}/parts/{k:05d}.tasks.tmp", "w") as sink:
        sink.write("".join(lines))
    return pairs


def finish_part(out, k, lines):
    """Writes `parts/<k>.checks.txt` from the check `lines`, then makes the part whole: `parts/<k>.tasks.tmp` becomes `tasks.txt`."""
    with open(f"{out}/parts/{k:05d}.checks.txt", "w") as sink:
        sink.write("".join(line + "\n" for line in lines))
    os.rename(f"{out}/parts/{k:05d}.tasks.tmp", f"{out}/parts/{k:05d}.tasks.txt")


def write_part(out, k, results, ran=None, keys=None):
    """Writes the part `k` of the (task id, cases, lines) results, checks its cases in this process, and writes the `tasks.txt` last, with the {task: (seconds, units)} and {task: (key, checks digest)} given."""
    pairs = write_files(out, k, results, ran, keys)
    finish_part(out, k, export_checks.check_part(out, k, pairs))


MIN_SHARE_BYTES = 50_000_000     # a share of values under this costs more to start than it saves, where the part has more


def submit_checks(pool, workers, out, k, pairs):
    """Submits the check of part `k` of the (task, case) pairs, cut into at most `workers` shares, to `pool`. Returns the futures."""
    size = sum(os.path.getsize(f"{out}/values/{t}/{c}.i32") for t, c in pairs)
    cut = export_checks.shares(out, pairs, set(pairs), max(1, min(workers, size // MIN_SHARE_BYTES)))
    return [pool.submit(export_checks.check_part, out, k, share) for share in cut]


def digest_files(files):
    """The sha256 of the (name, path) pairs `files`, in the order of the names: each name and the bytes of its file."""
    digest = hashlib.sha256()
    for name, f in sorted(files):
        digest.update(name.encode() + b"\0" + open(f, "rb").read() + b"\0")
    return digest.hexdigest()


def package_files():
    """The (name, path) pairs of the files of the installed `arclog` package, its compiled library among them (it holds the lib's registry and constructions)."""
    package = os.path.dirname(arclog.__file__)
    return [(os.path.relpath(f, package), f) for f in glob.glob(f"{package}/**", recursive=True) if os.path.isfile(f) and "__pycache__" not in f]


def engine_digest():
    """The sha256 of the files `package_files` gives and of one line of the versions of Python, numpy, pandas and pyarrow."""
    files = package_files()
    versions = f"{sys.version} {np.__version__} {pd.__version__} {pyarrow.__version__}"
    return hashlib.sha256((digest_files(files) + versions).encode()).hexdigest()


def checks_digest():
    """The sha256 of `export_checks.py` (the file `CHECKER` gives)."""
    return digest_files([("export_checks.py", CHECKER)])


def task_key(engine, task, settings, modules):
    """The sha256 of the task's generated program and data, its files under `gen/cases/<task>/` with their names, its task file, the files `modules` gives, the `engine` digest and the settings text."""
    digest = hashlib.sha256()
    cases = sorted(glob.glob(f"{CORPUS}/cases/{task}/*"))
    for f in (f"{CORPUS}/{task}.arclog", f"{CORPUS}/{task}.arcdata", *cases, f"{TASKS}/{task}.json", *modules):
        digest.update((os.path.basename(f).encode() + b"\0" if f in cases else b"") + open(f, "rb").read() + b"\0")
    digest.update(engine.encode() + b"\0" + settings.encode())
    return digest.hexdigest()


def line_task(line):
    """The task id a report or check line starts with: its first word without a trailing colon (a fault line may be `<task>: <text>`)."""
    return line.split()[0].rstrip(":") if line.split() else ""


def reuse_parts(out, previous, keys, k, skip, checks, pool, workers):
    """Writes parts from `previous`, from its `k`-th on, for each task of `keys` ({task: key}, not in `skip`) whose task key the previous export's `tasks.txt` lines give equal.

    A part takes the rows, fault lines and values (hard-linked) of the tasks of one previous part. Where every such line gives the
    checks digest `checks`, the part takes their check lines and `tasks.txt` lines as well. Otherwise its check is submitted to `pool`, of `workers` processes,
    and its `tasks.txt` lines are given `checks`, for `main` to finish as it finishes a replayed part.
    Returns the set of tasks reused, the next part number and {part: [the (task, case) pairs, the check futures, []]} of the parts to check again (`main`'s `open_parts`).
    """
    reused, again = set(), {}
    for tasks_file in sorted(glob.glob(f"{previous}/parts/*.tasks.txt")):
        stem = os.path.basename(tasks_file).split(".")[0]
        lines = [l for l in read_task_lines(tasks_file) if l.key and l.task not in skip and keys.get(l.task) == l.key]
        if not lines:
            continue
        tasks = [l.task for l in lines]
        for p in PARTS:
            f = f"{previous}/parts/{stem}.{p}.parquet"
            if os.path.exists(f):
                rows = pd.read_parquet(f)
                rows = rows[rows["task"].isin(tasks)]
                rows.to_parquet(f"{out}/parts/{k:05d}.{p}.parquet")
        kinds = ("report", "checks") if all(l.checks == checks for l in lines) else ("report",)
        for kind in kinds:
            with open(f"{out}/parts/{k:05d}.{kind}.txt", "w") as sink:
                sink.write("".join(l + "\n" for l in open(f"{previous}/parts/{stem}.{kind}.txt").read().splitlines() if line_task(l) in tasks))
        for task in tasks:
            os.makedirs(f"{out}/values/{task}", exist_ok=True)
            for name in os.listdir(f"{previous}/values/{task}") if os.path.isdir(f"{previous}/values/{task}") else []:
                if os.path.lexists(f"{out}/values/{task}/{name}"):
                    os.remove(f"{out}/values/{task}/{name}")
                os.link(f"{previous}/values/{task}/{name}", f"{out}/values/{task}/{name}")
        with open(f"{out}/parts/{k:05d}.tasks.tmp", "w") as sink:
            sink.write("".join(l._replace(checks=checks).text() + "\n" for l in lines))
        if len(kinds) == 2:
            os.rename(f"{out}/parts/{k:05d}.tasks.tmp", f"{out}/parts/{k:05d}.tasks.txt")
        else:
            pairs = part_cases(out, k, tasks)
            if pairs:
                again[k] = [pairs, set(submit_checks(pool, workers, out, k, pairs)), []]
            else:
                finish_part(out, k, [])
        reused |= set(tasks)
        k += 1
    return reused, k, again


def part_cases(out, k, tasks):
    """The (task, case) pairs of the `tasks` in part `k` of `out`: the cases of its `tables` rows in their order, then the other cases with a values file."""
    f = f"{out}/parts/{k:05d}.tables.parquet"
    pairs = list(dict.fromkeys(map(tuple, pd.read_parquet(f, columns=["task", "case"]).values.tolist()))) if os.path.exists(f) else []
    seen = set(pairs)
    for task in tasks:
        extra = sorted(n[:-len(".i32")] for n in os.listdir(f"{out}/values/{task}") if n.endswith(".i32"))
        pairs += [(task, c) for c in extra if (task, c) not in seen]
    return pairs


SPLIT_SHARE = 0.5   # a task is split where its one-thread seconds pass this share of the mean load of a worker


def cut_cost(units):
    """How many times the one-thread seconds of a task the replay of its `units` units takes in all: the cut breaks the prefix sharing of the streams (1.5 at 8 units for a251c730)."""
    return 1 + (units - 1) / 14


def unit_count(seconds, bound, cap):
    """The least count of units, at most `cap`, at which a task of `seconds` one-thread seconds takes under `bound` seconds a unit, and `cap` where none does."""
    return next((k for k in range(1, cap) if seconds * cut_cost(k) / k <= bound), cap)


def previous_cases(previous, task):
    """The count of cases the export `previous` holds for `task`, at least 1: the units of a task do not pass it."""
    directory = f"{previous}/values/{task}"
    return max(1, sum(n.endswith(".i32") for n in os.listdir(directory)) if os.path.isdir(directory) else 0)


def replay_order(task_ids, seconds):
    """`task_ids` for the longest processing time first: the tasks `seconds` ({task: seconds}) gives, by those seconds, after the tasks it does not give,
    which go by the largest .arcdata file, as the slowest tasks are among them."""
    return sorted(task_ids, key=lambda t: (t in seconds, -seconds.get(t, 0), -os.path.getsize(f"{CORPUS}/{t}.arcdata"), t))


def print_progress(begin, ended, count, done, running):
    """Prints the 10 s line of an export: `ended` of `count` tasks ended (`done` of them before this run), the seconds since `begin`, the seconds left, and the
    tasks of `running` ({task: (start, arclog.ReplayProgress)}) running past 10 s, longest first (the first 10, and a count of the rest)."""
    now = time.time()
    slow = sorted((start, t, progress) for t, (start, progress) in running.items() if start < now - 10)
    shown = " ".join(f"{t} {now - start:.0f} s {100 * progress.done / progress.total if progress.total else 0:.0f}%" for start, t, progress in slow[:10])
    more = f" and {len(slow) - 10} more" if len(slow) > 10 else ""
    left = f"{(now - begin) * (count - ended) / (ended - done):.0f}" if ended > done else "?"
    print(f"{ended} of {count} tasks ended, {now - begin:.0f} s, about {left} s left, running past 10 s: {shown}{more}", flush=True)


def take_workers():
    """The count of worker processes of an export's queue of calls, `ARCLOG_THREADS` if set and `os.cpu_count()` otherwise, and sets `ARCLOG_THREADS` to 1,
    so that each call runs on one engine thread, in the worker process that makes it."""
    workers = int(os.environ.get("ARCLOG_THREADS") or os.cpu_count())
    os.environ["ARCLOG_THREADS"] = "1"
    return workers


class WorkerDied(Exception):
    """The worker processes of two runs of one task call died; `status` gives how the second one ended, as `exit_status` gives it."""
    def __init__(self, status):
        super().__init__(status)
        self.status = status


class Message(enum.IntEnum):
    """The kind of a message a worker process sends. It is sent as its value: a worker of `main` runs this file as `__main__`, where the class pickles under another module name."""
    PROGRESS = 0    # (done, total) of the call's arclog.ReplayProgress
    ERROR = 1       # the traceback of an exception the call raised
    REPLY = 2       # what the call gave


TEST_ABORT = "ARCLOG_EXPORT_TEST_ABORT"     # `<task>:<n>`: the worker calls os.abort() on the first n runs of that task's call
_threads = threading.local()                # the worker process of each thread of an export's queue
_started, _stopping = [], threading.Event()  # every worker process started; set once `stop_workers` runs


def exit_status(code):
    """The text of the return code of a process: `signal <n> (<name>)` for a process a signal ended, `exit status <n>` otherwise."""
    if code < 0:
        try:
            return f"signal {-code} ({signal.Signals(-code).name})"
        except ValueError:
            return f"signal {-code}"
    return f"exit status {code}"


def stream_fields(stream):
    """The fields of an arclog.CaseStream as a dict, its buffers as bytes, for a pickle."""
    return dict(task=stream.task, case=stream.case, concept=stream.concept, ids=bytes(stream.ids), model=bytes(stream.model),
                masks=None if stream.masks is None else bytes(stream.masks), mask_fault=stream.mask_fault)


def death_line(task, status):
    """The fault line of a task whose call killed its worker process on both runs, the second ending with `status`."""
    return f"{task}: the worker process died on both runs of the task ({status})"


def start_worker(command):
    """Starts `command` with `--worker` and the descriptors of its two pipes, as `serve` reads them. Gives the process and the parent's ends: requests, replies."""
    requests_r, requests_w = os.pipe()
    replies_r, replies_w = os.pipe()
    process = subprocess.Popen([*command, "--worker", str(requests_r), str(replies_w)], pass_fds=(requests_r, replies_w))
    os.close(requests_r)
    os.close(replies_w)
    worker = process, Connection(requests_w, readable=False), Connection(replies_r, writable=False)
    _started.append(worker)
    return worker


def run_in_worker(command, task, payload, progress):
    """Runs the call of `task` with `payload` in this thread's worker process, which `command` starts where the thread has none, and gives its reply.

    While the call runs, `progress` takes the `done` and `total` the worker sends. Where the worker dies, the death is printed on stderr at once
    and the call runs once more in a new worker; where that one dies too, raises `WorkerDied`. A call that raises in the worker raises `RuntimeError`
    with the worker's traceback."""
    for attempt in (1, 2):
        if _stopping.is_set():
            raise RuntimeError("the export stopped its worker processes")
        if getattr(_threads, "worker", None) is None:
            _threads.worker = start_worker(command)
        process, requests, replies = _threads.worker
        try:
            requests.send((task, attempt, payload))
            while True:
                kind, *message = replies.recv()
                match Message(kind):
                    case Message.PROGRESS:
                        progress.done, progress.total = message
                    case Message.ERROR:
                        raise RuntimeError(f"{task}: {message[0]}")
                    case Message.REPLY:
                        return message[0]
        except (EOFError, BrokenPipeError):
            status = exit_status(process.wait())
            requests.close()
            replies.close()
            _threads.worker = None
            if _stopping.is_set():
                raise RuntimeError("the export stopped its worker processes")
            then = "it runs again in a new worker process" if attempt == 1 else "it gets a fault line"
            print(f"the worker process {process.pid} died on task {task} ({status}); {then}", file=sys.stderr, flush=True)
    raise WorkerDied(status)


def close_workers():
    """Ends each worker process at its next read of a request, and waits for it."""
    for process, requests, _ in _started:
        requests.close()
        process.wait()


def stop_workers():
    """Kills each worker process, and stops the queue from starting another."""
    _stopping.set()
    for process, _, _ in _started:
        process.kill()


def serve(handle):
    """The loop of a worker process that `start_worker` started: for each request `(task, attempt, payload)`, sends the reply `handle(payload, progress)`,
    with `progress` an `arclog.ReplayProgress` whose `done` and `total` it sends each second while `handle` runs. Ends at the end of the requests."""
    signal.signal(signal.SIGINT, signal.SIG_IGN)       # the export ends its workers itself
    requests, replies = Connection(int(sys.argv[-2]), writable=False), Connection(int(sys.argv[-1]), readable=False)
    test_task, _, test_runs = os.environ.get(TEST_ABORT, "").partition(":")
    while True:
        try:
            task, attempt, payload = requests.recv()
        except EOFError:
            return
        if task == test_task and attempt <= int(test_runs):
            os.abort()
        progress, ended = arclog.ReplayProgress(), threading.Event()

        def send_progress():
            while not ended.wait(1):
                replies.send((Message.PROGRESS.value, progress.done, progress.total))
        sender = threading.Thread(target=send_progress, daemon=True)
        sender.start()
        try:
            reply = (Message.REPLY.value, handle(payload, progress))
        except Exception:
            reply = (Message.ERROR.value, traceback.format_exc())
        ended.set()
        sender.join()
        replies.send(reply)


def main(out, task_ids, previous=None, **options):
    workers = take_workers()
    os.makedirs(f"{out}/parts", exist_ok=True)
    settings = {**options, "parts": list(PARTS)}
    if os.path.exists(f"{out}/settings.json"):
        found = json.load(open(f"{out}/settings.json"))
        if found != settings:
            print(f"{out} holds settings {json.dumps(found)}, this run has {json.dumps(settings)}", file=sys.stderr)
            sys.exit(2)
    settings_text = json.dumps(settings)
    json.dump(settings, open(f"{out}/settings.json", "w"))
    done, k = set(), 0
    for f in sorted(glob.glob(f"{out}/parts/*")):
        stem = os.path.basename(f).split(".")[0]
        if os.path.exists(f"{out}/parts/{stem}.tasks.txt"):
            k = max(k, int(stem) + 1)
            if f.endswith(".tasks.txt"):
                done |= {line.split()[0] for line in open(f) if line.strip()}
        else:
            os.remove(f)
    engine, checks = engine_digest(), checks_digest()
    keys = {t: task_key(engine, t, settings_text, (ROWS,)) for t in task_ids}
    tagged = {t: (key, checks) for t, key in keys.items()}
    check_pool = ProcessPoolExecutor(workers, mp_context=multiprocessing.get_context("spawn"))
    reused, k, open_parts = reuse_parts(out, previous, keys, k, done, checks, check_pool, workers) if previous else (set(), k, {})
    checking = {f: part for part, (_, futures, _) in open_parts.items() for f in futures}   # check future -> its part
    done |= reused
    before = {}
    for f in glob.glob(f"{previous}/parts/*.tasks.txt") if previous else []:
        before.update({l.task: l.one_thread_seconds for l in read_task_lines(f) if l.seconds is not None})
    todo = replay_order([t for t in task_ids if t not in done], before)
    bound = SPLIT_SHARE * sum(before.get(t, 0) for t in todo) / workers
    units = {t: unit_count(before[t], bound, min(workers, previous_cases(previous, t))) if t in before else 1 for t in todo}
    print(f"{len(reused)} tasks reused, {len({t for pairs, _, _ in open_parts.values() for t, _ in pairs})} of them to check again, {len(todo)} to replay", flush=True)
    started, progress = {}, {}

    def run(task, part):
        progress[task] = types.SimpleNamespace(done=0, total=0)
        started[task] = time.time()
        try:
            return part, run_in_worker([sys.executable, os.path.abspath(__file__)], task, (out, part, task, CORPUS, TASKS, options, units[task], tagged[task]), progress[task])
        except WorkerDied as died:
            clear_part(out, part, task)
            write_files(out, part, [(task, [], [death_line(task, died.status)])])
            return part, []

    pool = ThreadPoolExecutor(workers)
    futures = {t: pool.submit(run, t, k + i) for i, t in enumerate(todo)}
    pending, ended, begin, last = set(futures.values()) | set(checking), len(done), time.time(), time.time()
    failure = None
    while pending and not failure:
        got, pending = wait(pending, timeout=max(0.0, last + 10 - time.time()), return_when=FIRST_COMPLETED)
        for f in got:
            if f.exception():
                failure = failure or f.exception()
            elif f in checking:
                pairs, waiting, lines = open_parts[checking[f]]
                waiting.remove(f)
                lines += f.result()
                if not waiting:
                    position = {f"{t} {c}": i for i, (t, c) in enumerate(pairs)}
                    finish_part(out, checking[f], sorted(lines, key=lambda l: position[l.split(": ", 1)[0]]))
                    del open_parts[checking[f]]
            else:
                part, pairs = f.result()
                new = submit_checks(check_pool, workers, out, part, pairs) if pairs else []
                if new:
                    open_parts[part] = [pairs, set(new), []]
                    checking.update({c: part for c in new})
                    pending |= set(new)
                else:
                    finish_part(out, part, [])
                ended += 1
        replaying = pending & set(futures.values())
        if time.time() - last >= 10 or not replaying or failure:
            print_progress(begin, ended, len(task_ids), len(done), {t: (started[t], progress[t]) for t in list(started) if futures[t] in pending})
            last = time.time()
    if failure:
        stop_workers()
        pool.shutdown(wait=False, cancel_futures=True)
        workers_running = list((check_pool._processes or {}).values())
        check_pool.shutdown(wait=False, cancel_futures=True)
        for process in workers_running:
            process.kill()
        raise failure
    pool.shutdown()
    close_workers()
    check_pool.shutdown()
    merge(out)


def clear_part(out, k, task):
    """Removes the files of part `k` and the values of `task`, which a worker process that died while it wrote them may have left."""
    for f in glob.glob(f"{out}/parts/{k:05d}.*"):
        os.remove(f)
    shutil.rmtree(f"{out}/values/{task}", ignore_errors=True)


def replay_part(payload, progress):
    """The call of a worker process of `main`: replays the task of `payload` and writes it as its own part, but for the part's `checks.txt` and `tasks.txt`.
    Gives the part's (task, case) pairs."""
    out, k, task, corpus, tasks, options, units, tag = payload
    clear_part(out, k, task)
    start = time.time()
    cases, lines = export_rows.replay(corpus, tasks, task, progress, options, units if units > 1 else None)
    return write_files(out, k, [(task, cases, lines)], {task: (time.time() - start, units)}, {task: tag})


def merge(out):
    """Writes the whole files, `orientations.json` and `report.txt` from the parts of `out`, and prints the counts."""
    parts = lambda p: sorted(glob.glob(f"{out}/parts/*.{p}.parquet"))
    lines = [l for f in sorted(glob.glob(f"{out}/parts/*.report.txt")) for l in open(f).read().splitlines()]
    lines.sort(key=lambda l: l.split()[0])
    json.dump(sorted(arclog.orientation_names()), open(f"{out}/orientations.json", "w"))
    json.dump(arclog.orientation_types(), open(f"{out}/orientation_types.json", "w"))
    open(f"{out}/report.txt", "w").write("\n".join(lines) + "\n")
    checks = [l for f in sorted(glob.glob(f"{out}/parts/*.checks.txt")) for l in open(f).read().splitlines()]
    checks.sort(key=lambda l: l.split()[0])
    open(f"{out}/checks.txt", "w").write("".join(l + "\n" for l in checks))
    by_invariant = collections.Counter(l.split(": ", 1)[1].split(": ", 1)[0] for l in checks)
    summary = f", {len(checks)} check lines" + (": " + ", ".join(f"{inv} {n}" for inv, n in sorted(by_invariant.items())) if checks else "")
    if not parts("tables"):
        print(f"0 index rows, {len(lines)} fault lines{summary}")
        return
    whole = {p: pd.concat([pd.read_parquet(f) for f in parts(p)]).sort_values("task", kind="stable") for p in PARTS if parts(p)}   # no part is written for `bases` where no case is cut
    for rows in whole.values():
        if "concept" in rows:
            rows["concept"] = rows["concept"].astype(bool)
    tables, entries = whole["tables"], whole["entries"]
    export_checks.number_rows(tables, entries, whole.get("bases", export_checks.empty_bases()))
    entries.merge(tables, on=["task", "case", "table"], suffixes=("", "_table")).to_parquet(f"{out}/index.parquet")
    for p in whole:
        if p != "entries":      # the entries stand in index.parquet
            whole[p].to_parquet(f"{out}/{p}.parquet")
    print(f"{len(entries)} index rows, {len(lines)} fault lines{summary}")


def export_streams(out, task, streams, names=None, settings=None, bodies=False, step_cap=10000, bases=None):
    """Writes the tables export of the token `streams` of `task` to the new or empty directory `out`.

    `streams`, `names`, `settings`, `bodies` and `bases` are those of `arclog.stream_tables`, and `step_cap` is its
    cap, 10000 as in the corpus export. The layout is that of `main`, with one part and no `settings.json`; its
    `report.txt` holds, for each stream replayed, the line `<task> <case>: ended <kind> at token <index>` (or
    `ended none`) and then the fault lines of the streams that fault or lie past the cap. A stream cut from its
    base (see `bases.parquet` in the module docstring) gives a row of `bases.parquet`.
    """
    if os.path.exists(out) and os.listdir(out):
        raise FileExistsError(f"{out} exists and is not empty")
    os.makedirs(f"{out}/parts", exist_ok=True)
    cases, lines = arclog.stream_tables(task, TASKS, streams, names=names, settings=settings, bodies=bodies, step_cap=step_cap, bases=bases)
    write_part(out, 0, [(task, cases, lines)])
    merge(out)


if __name__ == "__main__" and sys.argv[1:2] == ["--worker"]:
    serve(replay_part)
elif __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("out", help="the new or empty output directory")
    parser.add_argument("--all-cases", action="store_true", help="the tables of every case of a task, not of its concept case alone")
    parser.add_argument("--bodies", action="store_true", help="table the bodies in progress as well as the relations of the finished forms")
    parser.add_argument("--previous", help="an earlier export directory whose parts of the tasks with an equal key are reused")
    parser.add_argument("--projection-cap", type=int, default=10000, help="the cap of the rows of a projection")
    parser.add_argument("--step-cap", type=int, default=10000, help="the cap of the model steps of a replay; 0 for no cap")
    parser.add_argument("task_ids", nargs="*", help="the tasks to export; every task of the corpus where none is given")
    parsed = parser.parse_intermixed_args(sys.argv[1:])
    options = {"projection_cap": parsed.projection_cap, "step_cap": parsed.step_cap or None}
    for flag in ("all_cases", "bodies"):
        if getattr(parsed, flag):
            options[flag] = True
    if parsed.previous:
        options["previous"] = parsed.previous
    ids = parsed.task_ids
    ids = ids or sorted(os.path.basename(f)[:-len(".arcdata")] for f in glob.glob(f"{CORPUS}/*.arcdata"))
    try:
        main(parsed.out, ids, **options)
    except Exception:       # a failed task or check ends the run at once: the replay threads of the other tasks do not delay the exit
        traceback.print_exc()
        sys.stderr.flush()
        os._exit(1)
