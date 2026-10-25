"""Write the labels file of a rollout export: one JSON line per sampled or gold continuation.

    work/lm/.venv/bin/python lm/rollout_labels.py <sampler lines> <rollout export> [<out>]

The sampler lines are JSON lines: the first a settings object, then one line per continuation with the fields task,
case (the corpus case, or null for a sample from nothing), branch (the rule index of the branch point), rollout (the
sample's index k, or "gold"), ids, model, prefix_tokens (the stream's tokens before the branch), prefix_rules,
ended, consistency, solved_test, attempts, tokens and program_form. The export is the tables export of those
streams (engine/arclog-py/tables_export.py, `export_streams`), whose case names are `<task>__<case>__b<j>__r<k>`,
`<task>__<case>__b<j>__gold` and `<task>__none__b0__r<k>`.

<out> (default `<rollout export>/labels.jsonl`) gets, per sampler line, {"case": the export's case name, "task",
"corpus_case", "branch", "rollout", "prefix_rules", "prefix_tables", "ended" (the sampler's), "consistency" (the
verdict of the export's `report.txt` at the last RULE end, `ended <kind> at token <i>`, else the sampler's),
"solved_test", "fault" (the report's fault line for the case, or null)}. `prefix_tables` is the count of the case's
export tables that the prefix gives: the evidence tables, and each table whose `token`, the stream index of the step
that gives it, is below prefix_tokens. The export numbers a case's tables in the order of their steps, so the first
table after the branch is export table `prefix_tables`. It is null for a case that the export does not hold.
"""
import json, sys
from pathlib import Path

import pandas as pd

POINT_EVIDENCE = 2   # the point code of an evidence table in tables.parquet


def case_name(task, case, branch, rollout):
    member = "gold" if rollout == "gold" else f"r{int(rollout)}"
    return f"{task}__{case if case is not None else 'none'}__b{int(branch)}__{member}"


def read_report(path):
    """{(task, case): verdict} and {(task, case): fault line} of a report.txt."""
    verdicts, faults = {}, {}
    for line in open(path).read().splitlines():
        head, sep, rest = line.partition(": ")
        parts = head.split(" ")
        if not sep or len(parts) != 2:
            continue
        key = tuple(parts)
        if rest.startswith("ended "):
            verdicts[key] = rest.split(" ")[1]
        else:
            faults[key] = line
    return verdicts, faults


def prefix_tables(tables, prefix_tokens):
    """{(task, case): the count of export tables before the branch}, from tables.parquet's rows of the cases."""
    out = {}
    for (task, case), t in tables.groupby(["task", "case"], sort=False):
        t = t.sort_values("table")
        if (t["token"].diff().dropna() < 0).any():
            raise ValueError(f"{task} {case}: the export's tables are not in the order of their steps")
        n = prefix_tokens.get((task, case))
        if n is not None:
            out[(task, case)] = int(((t["point"] == POINT_EVIDENCE) | (t["token"] < n)).sum())
    return out


def labels(sampler_path, export):
    lines = [json.loads(l) for l in open(sampler_path) if l.strip()][1:]   # the first line is the settings
    export = Path(export)
    verdicts, faults = read_report(export / "report.txt")
    names = [case_name(s["task"], s["case"], s["branch"], s["rollout"]) for s in lines]
    tables = pd.read_parquet(export / "tables.parquet", columns=["task", "case", "table", "token", "point"])
    counts = prefix_tables(tables, {(s["task"], n): int(s["prefix_tokens"]) for s, n in zip(lines, names)})
    out = []
    for s, n in zip(lines, names):
        key = (s["task"], n)
        out.append({"case": n, "task": s["task"], "corpus_case": s["case"], "branch": int(s["branch"]),
                    "rollout": s["rollout"], "prefix_rules": s["prefix_rules"], "prefix_tables": counts.get(key),
                    "ended": s["ended"], "consistency": verdicts.get(key, s["consistency"]),
                    "solved_test": s["solved_test"], "fault": faults.get(key)})
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
