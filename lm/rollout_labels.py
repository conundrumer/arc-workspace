"""Write the labels file of a rollout export: one JSON line per sampled or gold continuation.

    work/lm/.venv/bin/python lm/rollout_labels.py <sampler lines> <rollout export> [<out>]

The sampler lines are JSON lines: the first a settings object, then one line per continuation with the fields task,
case (the corpus case, or null for a sample from nothing), branch (the rule index of the branch point), rollout (the
sample's index k, or "gold"), ids, model, prefix_tokens (the stream's tokens before the branch), prefix_rules,
ended, consistency, solved_test, attempts, tokens, program_form and rules. The settings line gives each line its
`sampler_meta`: the prefix mode, the sampling LM's run and fold, and the data export of its prefixes. In the merged
file of lm/export_rollouts.py, each line has the `sampler_meta` of its own sampler file in its fields of
`SAMPLER_FIELDS`, and a line's own field takes the place of the settings line's. The export is the tables export of those
streams (engine/arclog-py/tables_export.py, `export_streams`), whose case names are `<task>__<case>__b<j>__r<k>`,
`<task>__<case>__b<j>__gold` and `<task>__none__b0__r<k>`.

<out> (default `<rollout export>/labels.jsonl`) gets, per sampler line, {"case": the export's case name, "task",
"corpus_case", "branch", "rollout", "prefix_tokens", "prefix_rules", "prefix_tables", "ended" (the sampler's),
"consistency" (the verdict of the export's `report.txt` at the last RULE end, `ended <kind> at token <i>`, or null),
"solved_test", "fault" (the report's fault line for the case, or null; a stream that faults or lies past the
export's step cap has one), "sampler_run" (the sampling LM's run directory, the settings line's `--model`) and
"sampler_fold" (that LM's `--fold`, k/n, from the settings line's `model_meta`, else from the run's model.json; null
for an LM trained without one); both are null for a gold continuation; "heldout" (whether the sampler's data export,
the settings line's `--data`, marks the task held out in its cases.npz; null where the line gives no `--data` or the
export holds no case of the task); "rules" (the sampler's, the engine's
verdict on each RULE clause of the continuation, in order, or null for a gold line of a sampler that gave none) and
"rule_ends" (the stream index of the end of each RULE clause of the continuation that ends)}. `prefix_tables` is
the count of the case's export tables that the prefix gives: the evidence tables, and each table whose `token`, the
stream index of the step that gives it, is below prefix_tokens. The export numbers a case's tables in the order of their steps, so the first
table after the branch is export table `prefix_tables`. A case that the export's `bases.parquet` cuts (see engine/arclog-py/tables_export.py) holds
only the tables of the steps from its token `tokens` on, after the tables of its base case numbered below its `tables`: it counts the base's tables
before min(prefix_tokens, `tokens`) with its own tables before prefix_tokens, so the count is the one that the export of the same streams without bases gives.
It is null for a case that the export does not hold.

A clause ends where the engine declares a relation (an id that the model did not write, of the kind "relation"), as
lm/sample.py's `--max-clause` counts clauses; the ids the engine emits after one model-written token end at most one
clause. A clause is a RULE clause where its first model-written token is RULE, and its end is the index of the
first such declaration. A continuation's last clause can be open (a stream cut at the sampler's step cap or at an
empty mask), with no end and no verdict.

A ValueError stops the run in each of these cases: a line's prefix mode is other than `random` or `0`, so a
prefix can end off a rule boundary; a line under `--prefix random` gives no corpus case; the lines of one task,
corpus case and branch differ in `prefix_tokens` or `prefix_tables`, or hold more than one gold continuation; the
report gives a case neither a verdict nor a fault line; a line's `rules` count other RULE clause ends than
`rule_ends`.
"""
import json, sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "engine" / "arclog-py"))
import export_checks

POINT_EVIDENCE = 2   # the point code of an evidence table in tables.parquet
ONE_CELL = '{"train": [{"input": [[0]], "output": [[0]]}], "test": [{"input": [[0]]}]}'   # a task to open a session


def vocabulary(settings):
    """The names and kinds of the engine's ids under the decode settings; the vocabulary does not depend on the task."""
    import arclog
    task = arclog.Task.from_json(ONE_CELL, arclog.World.Closed)
    v = arclog.Session(task, arclog.DecodeSettings(**settings)).vocabulary
    return [v.name(i) for i in range(len(v))], [v.kind(i) for i in range(len(v))]


def rule_ends(ids, model, names, kinds, start):
    """The stream index of the end of each RULE clause from index `start` on (the module docstring)."""
    ends, first = [], None   # first: the name of the first model-written token of the open clause
    for j in range(start, len(ids)):
        if model[j]:
            first = names[ids[j]] if first is None else first
        elif kinds[ids[j]] == "relation" and first is not None:
            if first == "RULE":
                ends.append(j)
            first = None
    return ends


def case_name(task, case, branch, rollout):
    member = "gold" if rollout == "gold" else f"r{int(rollout)}"
    return f"{task}__{case if case is not None else 'none'}__b{int(branch)}__{member}"


def read_report(path):
    """{(task, case): verdict} and {(task, case): fault line} of a report.txt. A case's line is `<task> <case>: <rest>`:
    the task ends at the first space, and the case, which can hold spaces, at the first `: ` after it. A task's own
    line, `<task>: <fault>`, names no case and is left out."""
    verdicts, faults = {}, {}
    for line in open(path).read().splitlines():
        task, _, after = line.partition(" ")
        case, sep, rest = after.partition(": ")
        if not sep or not case or task.endswith(":"):
            continue
        key = (task, case)
        if rest.startswith("ended "):
            verdicts[key] = rest.split(" ")[1]
        else:
            faults[key] = line
    return verdicts, faults


def prefix_tables(tables, bases, prefix_tokens):
    """{(task, case): the count of export tables before the branch}, from tables.parquet's rows of the cases and the export's `bases` frame
    (an empty one where it cuts no case)."""
    by_case = {key: t.sort_values("table") for key, t in tables.groupby(["task", "case"], sort=False)}
    cut = {(r.task, r.case): r for r in bases.itertuples()}
    out = {}
    for task, case in list(by_case) + [key for key in cut if key not in by_case]:
        t = by_case.get((task, case), tables.iloc[:0])
        if (t["token"].diff().dropna() < 0).any():
            raise ValueError(f"{task} {case}: the export's tables are not in the order of their steps")
        n = prefix_tokens.get((task, case))
        if n is None:
            continue
        counted = export_checks.tables_before(t, n)
        if (task, case) in cut:
            row = cut[(task, case)]
            if (task, row.base) not in by_case:
                raise ValueError(f"{task} {case}: its base {row.base} holds no tables")
            counted += export_checks.tables_before(by_case[(task, row.base)], min(n, int(row.tokens)))
        out[(task, case)] = counted
    return out


SAMPLER_FIELDS = ("prefix_mode", "sampler_run", "sampler_fold", "sampler_data")   # the fields of `sampler_meta`


def sampler_meta(settings):
    """The fields of SAMPLER_FIELDS that a sampler file's settings line gives each of its lines: `--prefix`, `--model`,
    the LM's `--fold` (from `model_meta`, else from the run's model.json) and `--data` (null where not given)."""
    run = settings["args"]["model"]
    fold = (settings.get("model_meta") or json.load(open(Path(run) / "model.json"))).get("fold")
    return dict(prefix_mode=settings["args"]["prefix"], sampler_run=run, sampler_fold=fold,
                sampler_data=settings["args"].get("data"))


def heldout_tasks(data):
    """{task: whether the data export's cases.npz marks it held out} for the export at `data`."""
    import numpy as np
    z = np.load(Path(data) / "cases.npz")
    out = {}
    for task, h in zip(z["task"].tolist(), z["heldout"].tolist()):
        out[task] = out.get(task, False) or bool(h)
    return out


def labels(sampler_path, export):
    settings, *lines = [json.loads(l) for l in open(sampler_path) if l.strip()]
    head = {}
    if any(k not in s for s in lines for k in SAMPLER_FIELDS) or not lines:
        head = sampler_meta(settings)
    metas = [{k: s.get(k, head.get(k)) for k in SAMPLER_FIELDS} for s in lines]
    modes = [m["prefix_mode"] for m in metas] or [settings["args"]["prefix"]]
    heldout_of = {}
    for d in {m["sampler_data"] for m in metas if m["sampler_data"] is not None}:
        heldout_of[d] = heldout_tasks(d)
    for prefix in modes:
        if prefix not in ("0", "random"):
            raise ValueError(f"{sampler_path}: sample.py --prefix {prefix} can end a prefix off a rule boundary, which is "
                             f"no branch point; labels take --prefix random or 0")
    spellings, kinds = vocabulary(settings["settings"])
    export = Path(export)
    verdicts, faults = read_report(export / "report.txt")
    names = [case_name(s["task"], s["case"], s["branch"], s["rollout"]) for s in lines]
    tables = pd.read_parquet(export / "tables.parquet", columns=["task", "case", "table", "token", "point"])
    bases = export_checks.read_bases(export)
    counts = prefix_tables(tables, bases, {(s["task"], n): int(s["prefix_tokens"]) for s, n in zip(lines, names)})
    groups = {}
    for s, n, prefix in zip(lines, names, modes):
        if s["case"] is None and prefix != "0":
            raise ValueError(f"{s['task']} {n}: no corpus case under sample.py --prefix {prefix}; an empty prefix "
                             f"must name its case")
        groups.setdefault((s["task"], s["case"], int(s["branch"])), []).append((s, n))
    for (task, case, b), g in groups.items():
        tokens = {int(s["prefix_tokens"]) for s, _ in g}
        held = {counts[(task, n)] for _, n in g if counts.get((task, n)) is not None}
        golds = sum(s["rollout"] == "gold" for s, _ in g)
        if len(tokens) > 1 or len(held) > 1 or golds > 1:
            raise ValueError(f"{task} {case} b{b}: the members do not share one prefix and one gold continuation: "
                             f"prefix_tokens {sorted(tokens)}, prefix_tables {sorted(held)}, {golds} gold lines")
    out = []
    for s, n, m in zip(lines, names, metas):
        key = (s["task"], n)
        if key not in verdicts and key not in faults:
            raise ValueError(f"{s['task']} {n}: the export's report.txt gives no verdict and no fault line")
        sampled = s["rollout"] != "gold"
        ends = rule_ends(s["ids"], s["model"], spellings, kinds, int(s["prefix_tokens"]))
        if s.get("rules") is not None and len(s["rules"]) != len(ends):
            raise ValueError(f"{s['task']} {n}: {len(s['rules'])} verdicts in `rules` and {len(ends)} RULE clause ends "
                             f"in the continuation")
        out.append({"case": n, "task": s["task"], "corpus_case": s["case"], "branch": int(s["branch"]),
                    "rollout": s["rollout"], "prefix_tokens": int(s["prefix_tokens"]), "prefix_rules": s["prefix_rules"],
                    "prefix_tables": counts.get(key), "ended": s["ended"], "consistency": verdicts.get(key),
                    "solved_test": s["solved_test"], "fault": faults.get(key),
                    "sampler_run": m["sampler_run"] if sampled else None,
                    "sampler_fold": m["sampler_fold"] if sampled else None,
                    "heldout": heldout_of[m["sampler_data"]].get(s["task"]) if m["sampler_data"] is not None else None,
                    "rules": s.get("rules"), "rule_ends": ends})
    return out


def main(sampler_path, export, out=None):
    rows = labels(sampler_path, export)
    out = Path(out) if out else Path(export) / "labels.jsonl"
    with open(out, "w") as f:
        f.write("".join(json.dumps(r) + "\n" for r in rows))
    missing = sum(r["prefix_tables"] is None for r in rows)
    print(f"{len(rows)} labels to {out}; {missing} cases the export does not hold; "
          f"{sum(r['fault'] is not None for r in rows)} with a fault line")


if __name__ == "__main__":
    main(*sys.argv[1:])
