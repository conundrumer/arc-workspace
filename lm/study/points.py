"""The branch points of `--points all` in mutants.py and foreign.py: every rule boundary of a task's first case.

A task's first case is its first case in the file order of `--data`'s cases.npz, as lm/sample.py's
`--prefix-cases first` takes it. Its rule boundaries are those of lm/sample.py's `Sampler.boundaries`: the end of
each RULE clause, where the engine gives a consistency and the decode has not ended. The branch point at the r-th
boundary (from 1) has the gold line of lm/sample.py's `gold`, with prefix_rules r and the consistency kinds of the
RULE clauses after it as its `rules`. The session takes the engine's default decode settings.
"""
from pathlib import Path as _StudyPath
import sys as _study_sys
_study_sys.path.insert(0, str(_StudyPath(__file__).resolve().parents[0]))
from study_paths import CODE_ROOT, DATA_ROOT, MAIN_ROOT, REPO_ROOT, data_path
import json, os, sys, time
from pathlib import Path

import numpy as np

ROOT = MAIN_ROOT
sys.path.insert(0, str(Path(__file__).resolve().parent))
import pinned   # noqa: E402
pinned.use()   # the pinned lm/ modules (pinned.py)
import arclog   # noqa: E402
from sample import SETTINGS, Sampler, gold   # noqa: E402


def first_cases(data):
    """{task: (case, ids, model)} of each task's first case in cases.npz, in file order."""
    z = np.load(Path(data) / "cases.npz")
    ids, model, off = z["ids"], z["model"], z["offsets"]
    out = {}
    for c, (task, case) in enumerate(zip(z["task"].tolist(), z["case"].tolist())):
        if task not in out:
            out[task] = (str(case), ids[off[c]:off[c + 1]].tolist(), model[off[c]:off[c + 1]].tolist())
    return out


def head(task, world, data):
    """(the session of the task under the engine's default settings, a source head as a sampler file's first line
    gives it: settings, world and args.data)."""
    session = arclog.Session(arclog.Task.from_json(open(ROOT / "data/tasks" / f"{task}.json").read(),
                                                   getattr(arclog.World, world)))
    s = session.settings
    return session, {"settings": {k: getattr(s, k) for k in SETTINGS}, "world": world, "args": {"data": str(data)}}


def golds(task, root, case, ids, model):
    """The gold line of each rule boundary of the case's stream, in stream order."""
    _, rules, kinds = Sampler.boundaries(None, root, ids, model)
    return [gold(task, case, ids, model, n, r + 1, kinds[r + 1:]) for r, n in enumerate(rules)]


def caught(e):
    """Whether `--points all` counts the error and goes on: any Exception (arclog.Refusal and arclog.Fault among
    them) or an engine panic, whose pyo3 PanicException derives from BaseException."""
    return isinstance(e, Exception) or type(e).__name__ == "PanicException"


def message(e):
    return f"{type(e).__name__}: {e}"


def refused(out, task, case, e, t0):
    """Log a task whose gold stream the engine refuses, and write its counts: {case: {"refused": the message}}."""
    (Path(out) / "counts" / f"{task}.json").write_text(json.dumps({case: {"refused": message(e)}}, indent=1))
    print(f"{task}: refused, {message(e)}, {time.time() - t0:.1f} s", flush=True)


def queued(queue):
    """The tasks of `<queue>/tasks.txt` (one per line, in order) that this process claims, one at a time: a task
    is claimed by the process that first makes the file `<queue>/claimed/<task>`, so processes that share the
    queue each take the next task that none has taken."""
    (Path(queue) / "claimed").mkdir(parents=True, exist_ok=True)
    for task in Path(queue, "tasks.txt").read_text().split():
        try:
            os.close(os.open(Path(queue) / "claimed" / task, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
        except FileExistsError:
            continue
        yield task


def write_stamp(out, task, stamps):
    """Write `<out>/samples/<task>.stamp` from the {task: stamp} `stamps`, where it gives the task. Call it once the
    task's samples and counts are written."""
    if stamps and task in stamps:
        (Path(out) / "samples" / f"{task}.stamp").write_text(stamps[task])
