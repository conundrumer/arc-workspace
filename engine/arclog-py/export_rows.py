"""The code of `tables_export.py` that decides the rows, values and fault lines of a part.

The reuse key of `tables_export.task_key` covers the bytes of this module, the installed `arclog` package and the versions of
Python, numpy, pandas and pyarrow, so code that can change a part's rows, values or fault lines belongs here, and code that
only moves, merges, orders or reports parts belongs in `tables_export.py`, whose edits leave the key unchanged. A change to
this module, or to the engine code that writes the export's files (`engine/arclog/src/eval/flows.rs`,
`engine/arclog/src/decode/`), runs `engine/arclog-py/roundtrip_check.py` with an `arclog` built from its tree before its merge.
"""
import os
import numpy as np
import pandas as pd
import arclog

PARTS = ("tables", "entries", "assigned", "projections", "projection_rows", "flows")


def frame(case, part):
    d = {k: (np.frombuffer(v, dtype=case.dtypes[f"{part}.{k}"]) if f"{part}.{k}" in case.dtypes else v)
         for k, v in getattr(case, part).items()}
    n = len(next(iter(d.values()))) if d else 0
    return pd.DataFrame(dict(task=[case.task] * n, case=[case.case] * n, concept=[case.concept] * n, **d))


def replay(corpus, tasks, task, progress, options):
    """The (cases, lines) of the replay of `task`, with the `options` of `arclog.corpus_tables`."""
    return arclog.corpus_tables(corpus, tasks, task_ids=[task], progress=progress, **options)


def write_rows(out, k, results):
    """Writes the values files, the parquet files and `report.txt` of the part `k` of the (task id, cases, lines) results.
    Returns the part's (task, case) pairs."""
    frames, pairs = {p: [] for p in PARTS}, []
    for task, cases, _ in results:
        for case in cases:
            os.makedirs(f"{out}/values/{case.task}", exist_ok=True)
            if os.path.lexists(f"{out}/values/{case.task}/{case.case}.i32"):
                os.remove(f"{out}/values/{case.task}/{case.case}.i32")  # may be a link to a file of another export
            with open(f"{out}/values/{case.task}/{case.case}.i32", "wb") as sink:
                sink.write(case.values)
            of_case = {p: frame(case, p) for p in PARTS}
            for p in PARTS:
                frames[p].append(of_case[p])
            pairs.append((task, case.case))
    for p, fs in frames.items():
        if fs:
            rows = pd.concat(fs)
            if not len(rows):       # an empty frame would write `task` and `case` as a null type, which a filter on strings refuses
                rows = rows.astype({"task": "string", "case": "string", "concept": bool})
            rows.to_parquet(f"{out}/parts/{k:05d}.{p}.parquet")
    with open(f"{out}/parts/{k:05d}.report.txt", "w") as sink:
        sink.write("".join(line + "\n" for _, _, lines in results for line in lines))
    return pairs
