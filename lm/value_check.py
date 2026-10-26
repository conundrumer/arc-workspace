"""Checks the value head's data path and loss on a synthetic rollout export written to a temporary directory.

The export holds two tasks, `ta` and `tb`, each with branch points of the corpus case `$C`, and the branch point of
the empty prefix of the corpus case `$D $E` (`$D` below; its name holds a space, as corpus case names can), which has no gold line and whose continuations all fail. A branch point of
`$C` has six continuations: the gold one and r0, which solve, r1 and r2, which do not, r3, whose first table after the
branch is empty, and r4, whose first table after the branch faults and which the sampler and the report's verdict
mark solved. Every case holds the evidence tables, one prefix table (none for `$D`) and two tables after the branch,
each table (Number, Color) of 8 rows on each of two train examples; the first table after the branch of a solving
continuation has one Color on all its rows, and every other table random Colors. The labels file comes from
lm/rollout_labels.py, on sampler lines, whose settings line gives an LM of a fold that holds neither task and a data
export that marks `tb` held out, and a report written beside the export.

Each continuation's stream holds a DET clause and two RULE clauses after the branch, the first table after the branch
in the first rule and the second in the second, where the DET clause stands; r2's stream stops before the second
rule's end, an open last clause. The members' verdicts per rule (`rules`) are mixed: C for Consistent, N for
NotConsistent, F for Fault, S for SeveralValues: gold C N, r0 N C, r1 C N, r2 N (open), r3 C C, r4 C F, and for `$D`
r0 N N, r1 N C, r2 C S.

- Labels: `prefix_tables` must be 3 for a `$C` case and 2 for `$D`, the consistency must be the report's, r4 must
  have its fault line, and a sampled case must give the sampler's run and fold. A `$D` case must get the report's
  verdict, its name's space read as part of the case. `heldout` must be true for each case of `tb` alone. Where
  lm/export_rollouts.py merges two sampler files of different runs, each sampled case must give its own file's run.
  `rules` must be the sampler's and
  `rule_ends` the two RULE clause ends (one for r2), the DET clause's end not among them; rollout_labels.py must
  refuse a line whose `rules` count another number of RULE clause ends. A case whose report gives a fault line
  and no verdict, as a stream past the export's step cap, must give no consistency. rollout_labels.py must refuse
  `--prefix random-token`, a line with no corpus case under `--prefix random`, two members of one branch point with
  different prefix_tokens, and a case the report gives neither a verdict nor a fault line. A line's `prefix_mode` takes
  the place of the settings line's `--prefix`: `0` lets a line with no corpus case pass that check, `random` refuses it.
- Records (`encoder.load_rollouts`): the group, the member, the positions (-3 to 1, and -2 to 2 for `$D`), and
  the flags: r3's first table after the branch empty, r4's faulted, and no other flag; r4 is not solving. Each table
  after the branch has the consistent label of its rule's verdict, and r2's second table, of the open clause, and
  every table of the prefix none, flagged unjudged. The load must raise a DataFault where a sampled case's LM has a
  fold that holds its task, and load where that task is held out (`tb`).
- Lists and losses, under the solving label: a list of a `$C` branch point holds the gold continuation, r0, r1 and
  r2; a change to the logits
  of the excluded tables must leave the ranking and the binary loss unchanged; the list of `$D` is not ranked,
  and the ranking loss and the pairwise ranking accuracy must be the same without its members; a list of `$C` must
  give 4 pairs, 2 of them of sampled continuations alone; the ranking loss must equal its formula on one list, and
  the binary loss must take each member's own label as its target, so that it changes when r0's and r1's scores
  swap.
- The consistent label, over positions 0 and 1: the lists of `$C` take each member's verdict of the table's rule, the
  gold continuation's its own, and leave out r2's unjudged table; their pairs count 4 and 6, and 2 and 4 of sampled
  continuations alone. A change to the logit of r2's unjudged table must leave both losses unchanged under the
  consistent label and change the binary loss under the solving label, where the table is listed.
- AUC (pretrain.py's `value_metrics`): two lists with 3 of 4 and 1 of 4 solving and a constant score within each
  must give `value_auc` and `value_auc_sampled` 0.5.
- The two evaluation paths: three draws of per-table scores must give pretrain.py's held-out entries
  (`value_heldout_metrics`) and value_eval.py's report the same metrics, those of the draws' mean score, with each
  metric's least and greatest value over the draws taken one at a time.
- The probe (value_probe.py): on the members of a `$C` branch point and of `$D`, the probe must take the tables that
  `value_lists` takes, and the head's logit of the probe's vectors must equal `value_scores`' under the same draws;
  its ridge regression must recover a linear target of six columns of different scales, held-out R^2 over 0.99.
- With --learn: 100 steps of the ranking loss alone, under the solving label (AdamW, lr 5e-4 or --lr=<lr>, warmup 10, clip 1.0), two `ta`
  branch points a step, at c 32 in float32, through pretrain.py's `value_step`; every 25 steps, the pairwise
  ranking accuracy on the `tb` branch points and the mean training loss of the last 25 steps. The run passes where
  its last accuracy is over 0.9 and its last loss is more than 0.3 under ln 4, the loss of equal scores on a list
  of 4 with 2 solving. A run whose labels are permuted among each drawn `ta` branch point's listed continuations,
  afresh at each draw, passes where its last loss is within 0.1 of ln 4: no score vector has an expected loss under
  ln 4 on such labels. Its held-out accuracy is printed and not judged: every solving table of the fixture differs
  from the others along one direction, so a head that has learned nothing still ranks them all one way or all the
  other. The two runs take about 30 s together.

    work/lm/.venv/bin/python lm/value_check.py [--learn] [--lr=<lr>] [--tables=<dir>]
"""
import json, shutil, sys, tempfile, time
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn

sys.path.insert(0, str(Path(__file__).parent))
import encoder as E
import export_rollouts as XR
import pretrain as P
import rollout_labels as RL
import value_eval as VE
import value_probe as VP
from train import fold_of

FOLD = next(k for k in range(4) if k not in {fold_of("ta", 4), fold_of("tb", 4)})   # a fold of 4 with neither task
LEARN = "--learn" in sys.argv[1:]
TABLES = next((x.split("=", 1)[1] for x in sys.argv if x.startswith("--tables=")), "work/tables/dev")
ORIENT = [tuple(x) for x in json.load(open(f"{TABLES}/orientations.json"))]
N_ROWS, BRANCHES = 8, 16
LR = float(next((x.split("=")[1] for x in sys.argv if x.startswith("--lr=")), 5e-4))
UNIFORM = float(np.log(4))   # the ranking loss of equal scores on a list of 4 with 2 solving
NAMES, KINDS = RL.vocabulary({})
ID = {n: i for i, n in enumerate(NAMES)}
REL = next(i for i, k in enumerate(KINDS) if k == "relation")
VERDICT = dict(C="Consistent", N="NotConsistent", F="Fault", S="SeveralValues")
RULES = {("$C", "gold"): "CN", ("$C", 0): "NC", ("$C", 1): "CN", ("$C", 2): "N", ("$C", 3): "CC", ("$C", 4): "CF",
         ("$D $E", 0): "NN", ("$D $E", 1): "NC", ("$D $E", 2): "CS"}   # the verdict of each rule of the continuation


def stream(case, m):
    """(ids, model) of a continuation: a RULE clause ($C) or a DET clause ($D) in tokens 0 to 4, then a RULE clause
    whose END is token 10, a DET clause, and a RULE clause whose END is token 20 (r2's stream stops there), then an
    open RULE clause. An engine-emitted relation declaration ends each clause."""
    w = lambda n: (ID[n], 1)
    e = (REL, 0)
    toks = [w("RULE" if case == "$C" else "DET"), w("input"), w("END"), e, e,
            w("RULE")] + [w("input")] * 4 + [w("END"), e, w("DET"), w("END"), e, w("RULE")] + [w("input")] * 4 + [w("END")]
    toks += [] if (case, m) == ("$C", 2) else [e, w("RULE")] + [w("input")] * 7
    return [i for i, _ in toks], [b for _, b in toks]
failed = []


def verdict(ok, what):
    print(f"  {what} {'PASS' if ok else 'FAIL'}")
    if not ok:
        failed.append(what)


def write_export(d, rng, tasks=("ta", "tb"), branches=BRANCHES, tasks_dir=None, data_dir=None):
    """A rollout export in `d`, its sampler lines at `d/sampler.jsonl`, where `tasks_dir` is given, a task file
    per task there (2 by 2 grids, two train pairs, one test pair), and, where `data_dir` is given, the sampler's data
    export there: a cases.npz of one case per task that marks the last task held out."""
    if data_dir is not None:
        np.savez(Path(data_dir) / "cases.npz", task=np.array(tasks), heldout=np.array([t == tasks[-1] for t in tasks]))
    if tasks_dir is not None:
        for task in tasks:
            g = lambda: rng.integers(0, 10, (2, 2)).tolist()
            json.dump({"train": [{"input": g(), "output": g()} for _ in range(2)], "test": [{"input": g()}]},
                      open(Path(tasks_dir) / f"{task}.json", "w"))
    grid = dict(point=2, relation=-1, column_types=["Example", "Box", "Color"], width=6, det_relations=[],
                det_widths=[], det_columns=[], token=0, fault=None)
    rel = lambda r, token, fault=None: dict(point=0, relation=r, column_types=["Number", "Color"], width=2,
                                            det_relations=[], det_widths=[], det_columns=[], token=token, fault=fault)
    random_rows = lambda: [[i, int(rng.integers(0, 10))] for i in range(N_ROWS)]
    settings = {"settings": {}, "world": "Closed", "args": {"model": "runs/synthetic", "prefix": "random",
                                                           "data": None if data_dir is None else str(data_dir)},
                "model_meta": {"fold": f"{FOLD}/4"}}
    tables, index, sampler, report = [], [], [settings], []
    for task in tasks:
        (d / "values" / task).mkdir(parents=True)
        members = [(("$C", b), m) for b in range(1, branches + 1) for m in ("gold", 0, 1, 2, 3, 4)]
        members += [(("$D $E", 0), m) for m in (0, 1, 2)]
        prefix = {}
        for (case, b), m in members:
            name = RL.case_name(task, case, b, m)
            solving = case == "$C" and m in ("gold", 0)
            color = int(rng.integers(0, 10))
            first = [[i, color] for i in range(N_ROWS)] if solving else random_rows()
            pre = prefix.setdefault((case, b), [random_rows(), random_rows()])
            tabs = [(grid, None), (grid, None)]
            if case == "$C":
                tabs.append((rel(0, 2), pre))
            tabs += [(rel(1, 10, "a check" if m == 4 else None), None if m == 4 else [] if m == 3 else [first, first]),
                     (rel(2, 20), [random_rows(), random_rows()])]
            values, entry = [], 0
            for i, (t, rows) in enumerate(tabs):
                tables.append(dict(task=task, case=name, concept=False, table=i, projections=0, **t))
                if t["point"] != 0 or rows is None:
                    continue
                for e in range(2):
                    r = rows[e] if rows else []
                    index.append(dict(task=task, case=name, table=i, entry=entry, kind=0, rows=len(r),
                                      offset=len(values), example_kind=1, example_index=e, model=0))
                    values += [x for row in r for x in row]
                    entry += 1
            np.array(values, np.int32).tofile(d / "values" / task / f"{name}.i32")
            ids, model = stream(case, m)
            sampler.append(dict(task=task, case=case, branch=b, rollout=m, ids=ids, model=model,
                                rules=[VERDICT[v] for v in RULES[(case, m)]],
                                prefix_tokens=5 if case == "$C" else 0, prefix_rules=b, ended=True,
                                consistency={"kind": "Consistent", "assignments": 1, "stop": None, "message": None},
                                solved_test=None if m == "gold" else solving or m == 4, attempts=1, tokens=len(ids),
                                program_form=None))
            report.append(f"{task} {name}: ended {'Consistent' if solving or m == 4 else 'NotConsistent'} at token 20")
            if m == 4:
                report.append(f"{task} {name}: a check fault")
    pd.DataFrame(tables).to_parquet(d / "tables.parquet")
    pd.DataFrame(index).to_parquet(d / "index.parquet")
    pd.DataFrame(columns=["task", "case", "entry", "det", "rows", "offset"]).to_parquet(d / "assigned.parquet")
    pd.DataFrame(columns=["task", "case", "table", "columns", "width"]).to_parquet(d / "projections.parquet")
    pd.DataFrame(columns=["task", "case", "projection", "entry", "defined", "rows", "offset"]).to_parquet(
        d / "projection_rows.parquet")
    (d / "report.txt").write_text("\n".join(report) + "\n")
    with open(d / "sampler.jsonl", "w") as f:
        f.write("".join(json.dumps(s) + "\n" for s in sampler))


def encoder(seed=0):
    torch.manual_seed(seed)
    in_names = [f":{i}" for i in range(64)] + ["ex_input", "ex_output"]
    enc = E.FeatureEncoder(nn.Embedding(len(in_names), 48), in_index={n: i for i, n in enumerate(in_names)},
                           id_dim=16, orientations=ORIENT, K=4, layers=2, c=32, heads=4)
    return enc, E.ValueHead(32, 16, 4)


t0 = time.time()
tmp = tempfile.TemporaryDirectory()
d, tasks_dir, data_dir = Path(tmp.name) / "rollouts", Path(tmp.name) / "tasks", Path(tmp.name) / "data"
d.mkdir(); tasks_dir.mkdir(); data_dir.mkdir()
write_export(d, np.random.default_rng(0), tasks_dir=tasks_dir, data_dir=data_dir)
RL.main(d / "sampler.jsonl", d)

print("== labels (rollout_labels.py)")
labels = E.read_value_labels(d / "labels.jsonl")
lab = lambda m, case="$C", b=1, task="ta": labels[(task, RL.case_name(task, case, b, m))]
verdict(all(l["prefix_tables"] == (3 if l["corpus_case"] == "$C" else 2) for l in labels.values()),
        f"prefix_tables 3 for $C and 2 for $D, over {len(labels)} cases")
verdict(lab("gold")["consistency"] == "Consistent" and lab(1)["consistency"] == "NotConsistent"
        and lab(4)["fault"] == f"ta {RL.case_name('ta', '$C', 1, 4)}: a check fault" and lab(0)["fault"] is None,
        "the report's consistency, and r4's fault line")
verdict(lab(1)["sampler_run"] == "runs/synthetic" and lab(1)["sampler_fold"] == f"{FOLD}/4"
        and lab("gold")["sampler_run"] is None and lab("gold")["sampler_fold"] is None,
        "a sampled case gives the sampler's run and fold, the gold one neither")
verdict(lab(0, case="$D $E", b=0)["consistency"] == "NotConsistent"
        and lab(0, case="$D $E", b=0)["case"] == "ta__$D $E__b0__r0",
        "the report's verdict of a case whose name holds a space")
verdict(lab(1)["heldout"] is False and lab("gold")["heldout"] is False and lab(1, task="tb")["heldout"] is True,
        "heldout per task from the sampler's data export: ta not, tb held out")
two = Path(tmp.name) / "two-files"
two.mkdir()
whole = [json.loads(l) for l in open(d / "sampler.jsonl")]
for name, run, task in (("a", "runs/synthetic", "ta"), ("b", "runs/other", "tb")):
    head = dict(whole[0], args=dict(whole[0]["args"], model=run))
    (two / f"{name}.jsonl").write_text("".join(json.dumps(s) + "\n" for s in [head] + [s for s in whole[1:] if s["task"] == task]))
first, merged = XR.read_lines([two / "a.jsonl", two / "b.jsonl"])
(two / "samples.jsonl").write_text(XR.merged_text(first, merged))
by_run = {(l["task"], l["sampler_run"]) for l in RL.labels(two / "samples.jsonl", d) if l["rollout"] != "gold"}
verdict(by_run == {("ta", "runs/synthetic"), ("tb", "runs/other")},
        f"the merged file of two sampler files of different runs gives each line its own file's run: {sorted(by_run)}")
verdict(lab("gold")["rules"] == ["Consistent", "NotConsistent"] and lab("gold")["rule_ends"] == [11, 21]
        and lab(2)["rule_ends"] == [11] and lab(2, case="$D $E", b=0)["rule_ends"] == [11, 21],
        "rules are the sampler's; rule_ends the RULE clause ends, the DET clause's not, one for r2's open clause")
sampler = [json.loads(l) for l in open(d / "sampler.jsonl")]
r1 = next(i for i, s in enumerate(sampler) if s.get("case") == "$C" and s["branch"] == 1 and s["rollout"] == 1)


def refused(name, lines, text, export=d):
    """Whether rollout_labels.py refuses the sampler `lines` with a ValueError whose message holds `text`."""
    p = Path(tmp.name) / f"{name}.jsonl"
    p.write_text("".join(json.dumps(s) + "\n" for s in lines))
    try:
        RL.labels(p, export)
    except ValueError as e:
        return text in str(e)
    return False


verdict(refused("random-token", [dict(sampler[0], args=dict(sampler[0]["args"], prefix="random-token"))] + sampler[1:],
                "--prefix random-token"), "labels refuse --prefix random-token")
verdict(refused("no-case", sampler + [dict(sampler[r1], case=None, branch=0, prefix_tokens=0)], "no corpus case"),
        "labels refuse a line with no corpus case under --prefix random")
none_line = dict(sampler[r1], case=None, branch=0, prefix_tokens=0)   # its case is not in the export: the next refusal
verdict(refused("mode-0", sampler + [dict(none_line, prefix_mode="0")], "no verdict and no fault line"),
        "labels take a line's prefix_mode 0 over the settings line's --prefix random: no refusal for its missing case")
verdict(refused("mode-random", [dict(sampler[0], args=dict(sampler[0]["args"], prefix="0"))] + sampler[1:]
                + [dict(none_line, prefix_mode="random")], "no corpus case"),
        "labels take a line's prefix_mode random over the settings line's --prefix 0")
verdict(refused("two-prefixes", sampler[:r1] + [dict(sampler[r1], prefix_tokens=6)] + sampler[r1 + 1:],
                "do not share one prefix"), "labels refuse two members of one branch point with different prefix_tokens")
verdict(refused("rules-count", sampler[:r1] + [dict(sampler[r1], rules=["Consistent"])] + sampler[r1 + 1:],
                "verdicts in `rules`"), "labels refuse a line whose rules count another number of RULE clause ends")
verdict(refused("no-verdict", sampler + [dict(sampler[r1], rollout=9)], "no verdict and no fault line"),
        "labels refuse a case the report gives neither a verdict nor a fault line")
capped = Path(tmp.name) / "capped"
shutil.copytree(d, capped)
r2_name = RL.case_name("ta", "$C", 1, 2)
(capped / "report.txt").write_text("".join(
    l + "\n" for l in (d / "report.txt").read_text().splitlines() if not l.startswith(f"ta {r2_name}: ended"))
    + f"ta {r2_name}: the replay's cap of 10000 model steps stops the solver's streams at this one\n")
r2 = next(l for l in RL.labels(d / "sampler.jsonl", capped) if l["case"] == r2_name)
verdict(r2["consistency"] is None and r2["fault"].startswith(f"ta {r2_name}: the replay's cap")
        and not E.value_solving(r2), "a case past the export's step cap: no consistency, its fault line, not solving")

print("== records (encoder.load_rollouts)")
members, skipped = E.load_rollouts(d, tasks_dir=tasks_dir, strict=False)
mem = lambda m, case="$C", b=1, task="ta": members[(task, RL.case_name(task, case, b, m))]
flags = lambda m, **k: [(r["position"], r["empty"], r["unseen"], r["faulted"]) for r in mem(m, **k)["records"]]
verdict(not skipped and len(members) == len(labels), f"{len(members)} members, none skipped")
verdict(mem("gold")["group"] == ("ta", "$C", 5) and mem("gold")["records"][0]["member"] == "gold"
        and mem(2, b=3)["records"][0]["member"] == 2 and mem(0, case="$D $E", b=0)["group"] == ("ta", "$D $E", 0),
        "groups and members")
clean = lambda ps: [(p, False, False, False) for p in ps]
verdict(flags("gold") == clean([-3, -2, -1, 0, 1]) and flags(0, case="$D $E", b=0) == clean([-2, -1, 0, 1]),
        f"positions: gold {[f[0] for f in flags('gold')]}, $D {[f[0] for f in flags(0, case='$D $E', b=0)]}")
verdict(flags(3)[3] == (0, True, False, False) and flags(4)[3] == (0, False, False, True)
        and flags(3)[4] == flags(4)[4] == (1, False, False, False), "r3 empty and r4 faulted at position 0 alone")
verdict(mem("gold")["solving"] and mem(0)["solving"] and not any(mem(m)["solving"] for m in (1, 2, 3, 4))
        and mem(1)["rate"] == 2 / 6 and mem(0, case="$D $E", b=0)["rate"] == 0,
        "solving members and rates; r4, faulted, is not solving though the sampler and the verdict mark it solved")
want = lambda case, m: [None if p < 0 else
                        (VERDICT[RULES[(case, m)][p]] == "Consistent" if p < len(RULES[(case, m)]) else None)
                        for p in [r["position"] for r in mem(m, case=case, b=1 if case == "$C" else 0)["records"]]]
got = lambda case, m: [None if r["consistent"] is None else bool(r["consistent"])
                       for r in mem(m, case=case, b=1 if case == "$C" else 0)["records"]]
verdict(all(got(c, m) == want(c, m) for c, m in RULES)
        and all(r["unjudged"] == (r["consistent"] is None) for ms in members.values() for r in ms["records"])
        and got("$C", 2)[4] is None and got("$C", 4)[4] is False,
        f"consistent labels follow each rule's verdict: gold {got('$C', 'gold')}, r2 {got('$C', 2)}, "
        f"r4 {got('$C', 4)}; r2's open clause and the prefix unjudged")
leaky = Path(tmp.name) / "leaky"
shutil.copytree(d, leaky)
(leaky / "labels.jsonl").write_text("".join(json.dumps(dict(l, sampler_fold=f"{fold_of('ta', 2)}/2")
                                                        if l["sampler_fold"] else l) + "\n" for l in labels.values()))
try:
    E.load_rollouts(leaky, tasks_dir=tasks_dir)
    leaked = None
except E.DataFault as e:
    leaked = str(e)
verdict(leaked is not None and leaked.startswith("ta "), f"a case sampled by an LM whose fold holds its task: {leaked}")
held_fold = Path(tmp.name) / "held-fold"
shutil.copytree(d, held_fold)
(held_fold / "labels.jsonl").write_text("".join(json.dumps(dict(l, sampler_fold=f"{fold_of('tb', 2)}/2")
                                                           if l["sampler_fold"] and l["task"] == "tb" else l) + "\n"
                                                for l in labels.values()))
try:
    E.load_rollouts(held_fold, tasks_dir=tasks_dir)
    raised = None
except E.DataFault as e:
    raised = str(e)
verdict(raised is None, f"a held-out task sampled by the LM of the fold its hash falls in loads: {raised}")

print("== lists and losses")
group = [mem(m) for m in ("gold", 0, 1, 2, 3, 4)] + [mem(m, case="$D $E", b=0) for m in (0, 1, 2)]
gen = torch.Generator().manual_seed(0)
logits = [torch.randn(len(m["tables"]), generator=gen) for m in group]
lists = E.value_lists(group, logits, label="solving")
c_list = next(l for l in lists if l["group"] == ("ta", "$C", 5))
verdict(len(lists) == 2 and c_list["labels"].tolist() == [True, True, False, False] and c_list["ranked"]
        and not next(l for l in lists if l["group"][1] == "$D $E")["ranked"],
        "one list per branch point: $C's gold, r0, r1, r2, ranked; the one of $D not ranked")
moved = [z.clone() for z in logits]
moved[4][3] += 7.0; moved[5][3] -= 5.0
same = all(torch.equal(E.value_loss(k, lists), E.value_loss(k, E.value_lists(group, moved, label="solving"))) for k in ("ranking", "binary"))
verdict(same, "the excluded tables' logits move neither loss")
alone = E.value_lists(group[:6], logits, label="solving")
verdict(torch.equal(E.value_loss("ranking", lists), E.value_loss("ranking", alone))
        and E.value_pairs(lists) == E.value_pairs(alone) and E.value_pairs(lists)[1] == 4
        and E.value_pairs(lists, sampled=True)[1] == 2,
        "the list of $D adds nothing to the ranking loss or to the 4 pairs, 2 of them without the gold one")
s = torch.stack([logits[i][3] for i in range(4)])
want = -(torch.tensor([0.5, 0.5, 0, 0]) * torch.log_softmax(s, 0)).sum()
z = torch.cat([logits[i][3:4] for i in range(4)] + [logits[i][2:3] for i in range(6, 9)])
want_b = nn.functional.binary_cross_entropy_with_logits(z, torch.tensor([1.0, 1.0] + [0.0] * 5))
verdict(torch.allclose(E.value_loss("ranking", alone), want) and torch.allclose(E.value_loss("binary", lists), want_b),
        "the ranking loss is the listwise softmax cross-entropy, the binary loss takes each member's own label")
swapped = [z.clone() for z in logits]
swapped[1][3], swapped[2][3] = logits[2][3], logits[1][3]
verdict(not torch.allclose(E.value_loss("binary", lists), E.value_loss("binary", E.value_lists(group, swapped, label="solving"))),
        "the binary loss changes when r0's and r1's scores swap")

print("== the consistent label")
cl = E.value_lists(group, logits, 2, label="consistent")
at = lambda ls, p: next(l for l in ls if l["group"] == ("ta", "$C", 5) and l["position"] == p)
sl = E.value_lists(group, logits, 2, label="solving")
verdict(at(cl, 0)["labels"].tolist() == [True, False, True, False] and at(sl, 0)["labels"].tolist() == [True, True, False, False]
        and at(cl, 1)["labels"].tolist() == [False, True, False, True, False] and len(at(sl, 1)["labels"]) == 6,
        "the flag selects the label: position 0 consistent gold, r1 against solving gold, r0; position 1 the gold's "
        "own verdict, r2's unjudged table left out")
verdict(E.value_pairs([at(cl, 0)])[1] == 4 and E.value_pairs([at(cl, 1)])[1] == 6
        and E.value_pairs([at(cl, 0)], sampled=True)[1] == 2 and E.value_pairs([at(cl, 1)], sampled=True)[1] == 4,
        "consistent pairs 4 and 6, of sampled continuations alone 2 and 4")
unjudged = [z.clone() for z in logits]
unjudged[3][4] += 9.0   # r2's second table after the branch, of its open clause
verdict(all(torch.equal(E.value_loss(k, cl), E.value_loss(k, E.value_lists(group, unjudged, 2, label="consistent")))
            for k in ("ranking", "binary"))
        and not torch.equal(E.value_loss("binary", sl), E.value_loss("binary", E.value_lists(group, unjudged, 2,
                                                                                               label="solving"))),
        "r2's unjudged table moves neither consistent loss, and moves the solving binary loss")

print("== AUC (pretrain.py, value_metrics)")
one = lambda solving, score, gold: dict(labels=torch.tensor(solving), scores=torch.full((4,), score),
                                        gold=torch.tensor(gold), ranked=True)
two = [one([True, True, True, False], 2.0, [True, False, False, False]),
       one([True, False, False, False], 0.0, [False] * 4)]
got = P.value_metrics(two)
pooled = E.auc([float(x) for l in two for x in l["scores"]], [bool(y) for l in two for y in l["labels"]])
verdict(got["value_auc"] == 0.5 and got["value_auc_sampled"] == 0.5 and pooled != 0.5,
        f"two lists of rates 0.75 and 0.25, a constant score within each: value_auc {got['value_auc']}, "
        f"value_auc_sampled {got['value_auc_sampled']} (pooled across lists {pooled:.3f})")

print("== the two evaluation paths (pretrain.py's held-out log, value_eval.py's report)")
noise = [torch.randn(len(m["tables"]), generator=gen) for m in group]
draws = [[z + e for z, e in zip(logits, noise)], [z - e for z, e in zip(logits, noise)], [z.clone() for z in logits]]
held = P.value_heldout_metrics(group, draws, 2, "solving")
shown = VE.report("  value_eval.py's report", group, [[z.numpy() for z in d] for d in draws], 2, "solving")
verdict({k[len("value_"):]: v for k, v in held.items()} == shown and set(shown) >= set(E.value_metrics([])),
        "identical scores give pretrain.py's held-out entries and value_eval.py's report identical metrics")
each = [E.value_metrics(E.value_lists(group, d, 2, label="solving")) for d in draws]
mean = E.value_metrics(E.value_lists(group, logits, 2, label="solving"))
verdict(all(shown[k] == mean[k] for k in mean) and shown["draws"] == 3
        and all(shown[f"{k}_min"] == min(e[k] for e in each) and shown[f"{k}_max"] == max(e[k] for e in each)
                for k in ("pair_acc", "auc")),
        f"the metrics of the draws' mean score, and each draw's range: pair_acc {shown['pair_acc']:.3f}, each draw "
        f"{shown['pair_acc_min']:.3f} to {shown['pair_acc_max']:.3f}")

print("== the probe of the head's input (value_probe.py)")
t1 = time.time()
enc, head = encoder()
enc.eval()
xs, zs, _ = VP.encode(enc, head, group, 2, 1, 16, torch.Generator().manual_seed(4))
with torch.no_grad():
    g4 = torch.Generator().manual_seed(4)   # drawn from in turn, member by member, as the probe draws
    direct = [E.value_scores(enc, head, [m], g4, 16)[0] if VP.listed(m, 2) else None for m in group]
x, _, y, _, counts = VP.stack(group, 2, xs)
listed = E.value_lists(group, logits, 2, label="solving")
verdict(len(y) == sum(len(l["labels"]) for l in listed)
        and all(np.allclose(z, d[VP.listed(m, 2)].numpy(), atol=1e-5) for m, z, d in zip(group, zs, direct) if z is not None),
        f"the probe takes the {len(y)} tables of the lists ({sum(len(l['labels']) for l in listed)}), and the head's logit of its vectors is value_scores' (largest difference {max(float(np.abs(z - d[VP.listed(m, 2)].numpy()).max()) for m, z, d in zip(group, zs, direct) if z is not None):.2e})")
rng = np.random.default_rng(3)
xr = rng.normal(size=(300, 6)) * [1, 10, 0.1, 1, 1, 1]
yr = xr @ rng.normal(size=6) + 0.01 * rng.normal(size=300)
pred, _ = VP.ridge(xr[:200], yr[:200], [i % 20 for i in range(200)], 0)
verdict(VP.r2(pred(xr[200:]), yr[200:]) > 0.99, f"the ridge probe recovers a linear target: held-out R2 "
        f"{VP.r2(pred(xr[200:]), yr[200:]):.4f} ({time.time() - t1:.1f} s)")
print(f"  {time.time() - t0:.1f} s")

print("== learning: 100 steps of the ranking loss, two ta branch points a step, pairwise ranking accuracy on tb")


def learn(shuffle):
    import pretrain as P
    groups = {}   # per branch point: the fixture gives every branch point of a corpus case one prefix_tokens, one group
    for m in members.values():
        k = (*m["group"], labels[m["key"]]["branch"])
        groups.setdefault(k, []).append(dict(m, group=k))
    train = [g for k, g in groups.items() if k[0] == "ta"]
    held = [g for k, g in groups.items() if k[0] == "tb"]
    r = np.random.default_rng(5)

    def permuted(g):   # the labels permuted among the branch point's members that the lists take, drawn afresh
        g = [dict(m) for m in g]
        idx = [i for i, m in enumerate(g) if not any(E.value_excluded(x) for x in m["records"] if x["position"] == 0)]
        for i, y in zip(idx, r.permutation([g[i]["solving"] for i in idx])):
            g[i]["solving"] = bool(y)
            g[i]["records"] = [dict(x, solving=bool(y)) for x in g[i]["records"]]
        return g
    enc, head = encoder()
    params = [p for p in enc.parameters() if p.requires_grad] + list(head.parameters())
    opt = torch.optim.AdamW(params, lr=LR, weight_decay=0.0)
    sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda i: min(1.0, (i + 1) / 10))
    rng, gen, curve, hist = np.random.default_rng(1), torch.Generator().manual_seed(0), [], []
    for step in range(1, 101):
        drawn = [m for i in rng.choice(len(train), 2, replace=False) for m in (permuted(train[i]) if shuffle else train[i])]
        loss, _ = P.value_step(enc, head, drawn, gen, "ranking", 1, 16, "solving")
        opt.zero_grad(); loss.backward()
        torch.nn.utils.clip_grad_norm_(params, 1.0)
        opt.step(); sched.step()
        hist.append(loss.item())
        if step % 25 == 0:
            with torch.no_grad():
                ls = [l for g in held for l in P.value_step(enc, head, g, torch.Generator().manual_seed(1), "ranking",
                                                            1, 16, "solving")[1]]
            curve.append((P.value_metrics(ls)["value_pair_acc"], float(np.mean(hist[-25:]))))
    return curve


if LEARN:
    for shuffle in (False, True):
        t1 = time.time()
        curve = learn(shuffle)
        acc, loss = curve[-1]
        ok = acc > 0.9 and loss < UNIFORM - 0.3 if not shuffle else loss > UNIFORM - 0.1
        verdict(ok, f"{'permuted labels' if shuffle else 'true labels'}: at steps 25, 50, 75, 100, held-out accuracy "
                    f"{', '.join(f'{x:.2f}' for x, _ in curve)}, training loss "
                    f"{', '.join(f'{l:.3f}' for _, l in curve)} ({time.time() - t1:.0f} s)")
else:
    print("  skipped: run with --learn")
tmp.cleanup()
print(f"FAIL: {failed}" if failed else "all checks passed")
sys.exit(1 if failed else 0)
