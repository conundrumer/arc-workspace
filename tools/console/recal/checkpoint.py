#!/usr/bin/env python3
"""Label store for recalibration runs.

labels.json holds one record per classified pair, keyed by task plus a hash
of the comment text, with the pair's timestamp. Eras are assigned at counts
time from the timestamps, so the era cut is a free choice per run. A rubric
change invalidates the store: records carry the rubric date they were
labeled under, and counts refuse a store with mixed rubric dates.

Subcommands:
  todo <sample.json> <out.json>   rows of the sample not yet in the store
  merge <sample.json> <batches/>  fold classifier outputs into the store
  counts <era-cut>                era-split per-kind counts from the store
"""
import collections
import glob
import hashlib
import json
import os
import re
import sys

OUT = os.path.dirname(os.path.abspath(__file__))
LABELS = os.path.join(OUT, "labels.json")
RUBRIC_DATE = "2026-08-30"

KINDS = ["lib_candidates", "doc_gaps", "simplification", "naming_vocab",
         "correctness_risk", "lint_tooling", "alt_models", "unwitnessed_edges",
         "hedges", "other"]
ALIAS = {
    "alt_model": "alt_models", "unwitnessed_edge": "unwitnessed_edges",
    "hedge": "hedges", "hedge_caveat": "hedges", "doc_gap": "doc_gaps",
    "lib_candidate": "lib_candidates", "lib_promotion": "lib_candidates",
    "naming": "naming_vocab", "naming_and_vocabulary": "naming_vocab",
    "lint_and_tooling": "lint_tooling", "correctness": "correctness_risk",
    "simplifications": "simplification",
}


def key(task, text):
    norm = re.sub(r"\W+", "", text.lower())[:200]
    return task + ":" + hashlib.sha1(norm.encode()).hexdigest()[:12]


def load():
    return json.load(open(LABELS)) if os.path.exists(LABELS) else []


def norm_kinds(ks):
    out = []
    for k in ks:
        if not isinstance(k, str):
            continue
        k = ALIAS.get(k, k)
        out.append(k if k in KINDS else "other")
    return out


def cmd_todo(sample_path, out_path):
    have = {l["key"] for l in load()}
    rows = [r for r in json.load(open(sample_path))
            if key(r["task"], r["user_comment"]) not in have]
    json.dump(rows, open(out_path, "w"), indent=1)
    print(f"unlabeled rows: {len(rows)}")


def cmd_merge(sample_path, batches_dir):
    sample = {r["id"]: r for r in json.load(open(sample_path))}
    labels = load()
    have = {l["key"] for l in labels}
    added = 0
    for p in sorted(glob.glob(os.path.join(batches_dir, "out_*.json"))):
        for l in json.load(open(p)):
            r = sample.get(l.get("id"))
            if not r:
                continue
            k = key(r["task"], r["user_comment"])
            if k in have:
                continue
            have.add(k)
            added += 1
            labels.append({
                "key": k, "task": r["task"], "ts": r["ts"],
                "origin": l.get("origin"),
                "raised_kinds": norm_kinds(l.get("raised_kinds", [])),
                "picked_kinds": norm_kinds(l.get("picked_kinds", [])),
                "note": l.get("note", ""),
                "rubric": RUBRIC_DATE,
            })
    labels.sort(key=lambda l: l["ts"] or "")
    json.dump(labels, open(LABELS, "w"), indent=1)
    print(f"added {added}, store total {len(labels)}")


def cmd_counts(era_cut):
    labels = load()
    rubrics = sorted({l["rubric"] for l in labels})
    if len(rubrics) > 1:
        sys.exit(f"mixed rubric dates in store: {rubrics}; re-classify before counting")
    counts = {k: {"picked_old": 0, "raised_old": 0,
                  "picked_new": 0, "raised_new": 0} for k in KINDS}
    for l in labels:
        e = "new" if (l["ts"] or "") >= era_cut else "old"
        rc = collections.Counter(l["raised_kinds"])
        pc = collections.Counter(l["picked_kinds"])
        for k, n in rc.items():
            counts[k][f"raised_{e}"] += n
        for k, n in pc.items():
            counts[k][f"picked_{e}"] += min(n, rc.get(k, 0))
    json.dump(counts, open(os.path.join(OUT, "counts.json"), "w"), indent=1)
    n_old = sum(1 for l in labels if (l["ts"] or "") < era_cut)
    print(f"pairs: old={n_old} new={len(labels) - n_old}")
    print(f"{'kind':22} {'old p/r':>12} {'old %':>6}   {'new p/r':>12} {'new %':>6}")
    for k in KINDS:
        c = counts[k]
        po, ro = c["picked_old"], c["raised_old"]
        pn, rn = c["picked_new"], c["raised_new"]
        fo = f"{po / ro:.0%}" if ro else "-"
        fn = f"{pn / rn:.0%}" if rn else "-"
        print(f"{k:22} {po:5}/{ro:<6} {fo:>6}   {pn:5}/{rn:<6} {fn:>6}")


if __name__ == "__main__":
    cmds = {"todo": cmd_todo, "merge": cmd_merge, "counts": cmd_counts}
    if len(sys.argv) < 2 or sys.argv[1] not in cmds:
        sys.exit(__doc__)
    cmds[sys.argv[1]](*sys.argv[2:])
