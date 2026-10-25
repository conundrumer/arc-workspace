"""Checks the value head's data path and loss on a synthetic rollout export written to a temporary directory.

The export holds two tasks, `ta` and `tb`, each with branch points of the corpus case `$C`, and the branch point of
the empty prefix of the corpus case `$D`, which has no gold line and whose continuations all fail. A branch point of
`$C` has six continuations: the gold one and r0, which solve, r1 and r2, which do not, r3, whose first table after the
branch is empty, and r4, whose first table after the branch faults and which the sampler and the report's verdict
mark solved. Every case holds the evidence tables, one prefix table (none for `$D`) and two tables after the branch,
each table (Number, Color) of 8 rows on each of two train examples; the first table after the branch of a solving
continuation has one Color on all its rows, and every other table random Colors. The labels file comes from
lm/rollout_labels.py, on sampler lines, whose settings line gives an LM of a fold that holds neither task, and a report
written beside the export.

- Labels: `prefix_tables` must be 3 for a `$C` case and 2 for `$D`, the consistency must be the report's, r4 must
  have its fault line, and a sampled case must give the sampler's run and fold. A case whose report gives a fault line
  and no verdict, as a stream past the export's step cap, must give no consistency. rollout_labels.py must refuse
  `--prefix random-token`, a line with no corpus case under `--prefix random`, two members of one branch point with
  different prefix_tokens, and a case the report gives neither a verdict nor a fault line.
- Records (`encoder.load_rollouts`): the group, the member, the positions (-3 to 1, and -2 to 2 for `$D`), and
  the flags: r3's first table after the branch empty, r4's faulted, and no other flag; r4 is not solving. The load
  must raise a DataFault where a sampled case's LM has a fold that holds its task.
- Lists and losses: a list of a `$C` branch point holds the gold continuation, r0, r1 and r2; a change to the logits
  of the excluded tables must leave the ranking and the binary loss unchanged; the list of `$D` is not ranked,
  and the ranking loss and the pairwise ranking accuracy must be the same without its members; a list of `$C` must
  give 4 pairs, 2 of them of sampled continuations alone; the ranking loss must equal its formula on one list, and
  the binary loss must take each member's own label as its target, so that it changes when r0's and r1's scores
  swap.
- AUC (pretrain.py's `value_metrics`): two lists with 3 of 4 and 1 of 4 solving and a constant score within each
  must give `value_auc` and `value_auc_sampled` 0.5.
- With --learn: 100 steps of the ranking loss alone (AdamW, lr 5e-4 or --lr=<lr>, warmup 10, clip 1.0), two `ta`
  branch points a step, at c 32 in float32, through pretrain.py's `value_step`; every 25 steps, the pairwise
  ranking accuracy on the `tb` branch points and the mean training loss of the last 25 steps. The run passes where
  its last accuracy is over 0.9 and its last loss is more than 0.3 under ln 4, the loss of equal scores on a list
  of 4 with 2 solving. A run whose labels are permuted among each drawn `ta` branch point's listed continuations,
  afresh at each draw, passes where its last loss is within 0.1 of ln 4: no score vector has an expected loss under
  ln 4 on such labels. Its held-out accuracy is printed and not judged: every solving table of the fixture differs
  from the others along one direction, so a head that has learned nothing still ranks them all one way or all the
  other. The two runs take about 30 s together.

    work/lm/.venv/bin/python lm/value_check.py [--learn] [--lr=<lr>]
"""
import json, shutil, sys, tempfile, time
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn

sys.path.insert(0, str(Path(__file__).parent))
import encoder as E
import pretrain as P
import rollout_labels as RL
from train import fold_of

FOLD = next(k for k in range(4) if k not in {fold_of("ta", 4), fold_of("tb", 4)})   # a fold of 4 with neither task
LEARN = "--learn" in sys.argv[1:]
ORIENT = [tuple(x) for x in json.load(open("work/tables/dev/orientations.json"))]
N_ROWS, BRANCHES = 8, 16
LR = float(next((x.split("=")[1] for x in sys.argv if x.startswith("--lr=")), 5e-4))
UNIFORM = float(np.log(4))   # the ranking loss of equal scores on a list of 4 with 2 solving
failed = []


def verdict(ok, what):
    print(f"  {what} {'PASS' if ok else 'FAIL'}")
    if not ok:
        failed.append(what)


def write_export(d, rng, tasks=("ta", "tb"), branches=BRANCHES, tasks_dir=None):
    """A rollout export in `d`, its sampler lines at `d/sampler.jsonl` and, where `tasks_dir` is given, a task file
    per task there (2 by 2 grids, two train pairs, one test pair)."""
    if tasks_dir is not None:
        for task in tasks:
            g = lambda: rng.integers(0, 10, (2, 2)).tolist()
            json.dump({"train": [{"input": g(), "output": g()} for _ in range(2)], "test": [{"input": g()}]},
                      open(Path(tasks_dir) / f"{task}.json", "w"))
    grid = dict(point=2, relation=-1, column_types=["Example", "Box", "Color"], width=6, det_relations=[],
                det_widths=[], token=0, fault=None)
    rel = lambda r, token, fault=None: dict(point=0, relation=r, column_types=["Number", "Color"], width=2,
                                            det_relations=[], det_widths=[], token=token, fault=fault)
    random_rows = lambda: [[i, int(rng.integers(0, 10))] for i in range(N_ROWS)]
    settings = {"settings": {}, "args": {"model": "runs/synthetic", "prefix": "random"},
                "model_meta": {"fold": f"{FOLD}/4"}}
    tables, index, sampler, report = [], [], [settings], []
    for task in tasks:
        (d / "values" / task).mkdir(parents=True)
        members = [(("$C", b), m) for b in range(1, branches + 1) for m in ("gold", 0, 1, 2, 3, 4)]
        members += [(("$D", 0), m) for m in (0, 1, 2)]
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
            sampler.append(dict(task=task, case=case, branch=b, rollout=m, ids=[], model=[],
                                prefix_tokens=5 if case == "$C" else 0, prefix_rules=b, ended=True,
                                consistency={"kind": "Consistent", "assignments": 1, "stop": None, "message": None},
                                solved_test=None if m == "gold" else solving or m == 4, attempts=1, tokens=30,
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
d, tasks_dir = Path(tmp.name) / "rollouts", Path(tmp.name) / "tasks"
d.mkdir(); tasks_dir.mkdir()
write_export(d, np.random.default_rng(0), tasks_dir=tasks_dir)
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
verdict(refused("two-prefixes", sampler[:r1] + [dict(sampler[r1], prefix_tokens=6)] + sampler[r1 + 1:],
                "do not share one prefix"), "labels refuse two members of one branch point with different prefix_tokens")
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
members, skipped = E.load_rollouts(d, tasks_dir=tasks_dir)
mem = lambda m, case="$C", b=1, task="ta": members[(task, RL.case_name(task, case, b, m))]
flags = lambda m, **k: [(r["position"], r["empty"], r["unseen"], r["faulted"]) for r in mem(m, **k)["records"]]
verdict(not skipped and len(members) == len(labels), f"{len(members)} members, none skipped")
verdict(mem("gold")["group"] == ("ta", "$C", 5) and mem("gold")["records"][0]["member"] == "gold"
        and mem(2, b=3)["records"][0]["member"] == 2 and mem(0, case="$D", b=0)["group"] == ("ta", "$D", 0),
        "groups and members")
clean = lambda ps: [(p, False, False, False) for p in ps]
verdict(flags("gold") == clean([-3, -2, -1, 0, 1]) and flags(0, case="$D", b=0) == clean([-2, -1, 0, 1]),
        f"positions: gold {[f[0] for f in flags('gold')]}, $D {[f[0] for f in flags(0, case='$D', b=0)]}")
verdict(flags(3)[3] == (0, True, False, False) and flags(4)[3] == (0, False, False, True)
        and flags(3)[4] == flags(4)[4] == (1, False, False, False), "r3 empty and r4 faulted at position 0 alone")
verdict(mem("gold")["solving"] and mem(0)["solving"] and not any(mem(m)["solving"] for m in (1, 2, 3, 4))
        and mem(1)["rate"] == 2 / 6 and mem(0, case="$D", b=0)["rate"] == 0,
        "solving members and rates; r4, faulted, is not solving though the sampler and the verdict mark it solved")
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

print("== lists and losses")
group = [mem(m) for m in ("gold", 0, 1, 2, 3, 4)] + [mem(m, case="$D", b=0) for m in (0, 1, 2)]
gen = torch.Generator().manual_seed(0)
logits = [torch.randn(len(m["tables"]), generator=gen) for m in group]
lists = E.value_lists(group, logits)
c_list = next(l for l in lists if l["group"] == ("ta", "$C", 5))
verdict(len(lists) == 2 and c_list["labels"].tolist() == [True, True, False, False] and c_list["ranked"]
        and not next(l for l in lists if l["group"][1] == "$D")["ranked"],
        "one list per branch point: $C's gold, r0, r1, r2, ranked; the one of $D not ranked")
moved = [z.clone() for z in logits]
moved[4][3] += 7.0; moved[5][3] -= 5.0
same = all(torch.equal(E.value_loss(k, lists), E.value_loss(k, E.value_lists(group, moved))) for k in ("ranking", "binary"))
verdict(same, "the excluded tables' logits move neither loss")
alone = E.value_lists(group[:6], logits)
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
verdict(not torch.allclose(E.value_loss("binary", lists), E.value_loss("binary", E.value_lists(group, swapped))),
        "the binary loss changes when r0's and r1's scores swap")

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
print(f"  {time.time() - t0:.1f} s")

print("== learning: 100 steps of the ranking loss, two ta branch points a step, pairwise ranking accuracy on tb")


def learn(shuffle):
    import pretrain as P
    groups = {}
    for m in members.values():
        groups.setdefault(m["group"], []).append(m)
    train = [g for k, g in groups.items() if k[0] == "ta"]
    held = [g for k, g in groups.items() if k[0] == "tb"]
    r = np.random.default_rng(5)

    def permuted(g):   # the labels permuted among the branch point's members that the lists take, drawn afresh
        g = [dict(m) for m in g]
        idx = [i for i, m in enumerate(g) if not any(E.value_excluded(x) for x in m["records"] if x["position"] == 0)]
        for i, y in zip(idx, r.permutation([g[i]["solving"] for i in idx])):
            g[i]["solving"] = bool(y)
        return g
    enc, head = encoder()
    params = [p for p in enc.parameters() if p.requires_grad] + list(head.parameters())
    opt = torch.optim.AdamW(params, lr=LR, weight_decay=0.0)
    sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda i: min(1.0, (i + 1) / 10))
    rng, gen, curve, hist = np.random.default_rng(1), torch.Generator().manual_seed(0), [], []
    for step in range(1, 101):
        drawn = [m for i in rng.choice(len(train), 2, replace=False) for m in (permuted(train[i]) if shuffle else train[i])]
        loss, _ = P.value_step(enc, head, drawn, gen, "ranking", 1, 16)
        opt.zero_grad(); loss.backward()
        torch.nn.utils.clip_grad_norm_(params, 1.0)
        opt.step(); sched.step()
        hist.append(loss.item())
        if step % 25 == 0:
            with torch.no_grad():
                ls = [l for g in held for l in P.value_step(enc, head, g, torch.Generator().manual_seed(1), "ranking",
                                                            1, 16)[1]]
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
