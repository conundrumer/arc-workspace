"""Measure a pretrained value head (pretrain.py --value) on a rollout export, against two baselines.

    work/lm/.venv/bin/python lm/value_eval.py --encoder <run>/encoder.pt --value-tables work/tables/rollouts-afc44b43 \
        [--data work/lm/data] [--positions P] [--value-label solving|consistent] [--draws 4] [--device cpu]

The branch points are split as pretrain.py splits them: a branch point is held out where the data (`--data`, its
cases.npz) marks its task held out, and is a training one where its task is a training task. On the held-out branch
points, each score below is measured over the lists of encoder.py's `value_lists` (the tables at the positions below
`--positions` after the branch, the empty, unseen and faulted ones left out, with each table's label as
`--value-label` selects it, pretrain.py's flag), as the pairwise ranking accuracy (over each list's pairs of a member
of label 1 and one of label 0, a tie one half) and the AUC (within each list that holds members of both labels, and
the mean over those lists), and both once more over the sampled continuations alone, without the gold one, whose
author differs:

- the value head: its logit, the mean over `--draws` draws of the random identifiers of the table's relations and
  values (encoder.py, `value_scores`), since the logit depends on that draw; beside the metrics of the mean, the
  report gives each metric's least and greatest value over the draws taken one at a time;
- a logistic regression on trivial features of a table, trained by full-batch Adam for `--lr-steps` steps on the
  training branch points' listed tables with each table's label: the log of its row count, whether it is
  empty, whether it is unseen, its depth, the log of its step index, its position after the branch, and the count of
  its columns of each type;
- compressibility: minus the encoder's masked loss per hidden field of the table, over one program step and one prior
  step's mask (`masked_loss`), under one draw of identifiers, on which it depends as the value head's logit does; a
  table with no hidden field takes the mean score.

The metrics come from encoder.py's `value_draw_metrics`, which pretrain.py's held-out log takes too.
"""
import argparse, json, random
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn

import encoder as E
import train as T


FEATURES = ["log rows", "empty", "unseen", "depth", "log step index", "position"] + [f"{n} columns" for n in E.TYPE_NAMES]


def features(t, r):
    """The trivial features of table t with its value record r."""
    bag = [sum(E.feature_type(ty) == name for ty in t.types) for name in E.TYPE_NAMES]
    return [np.log1p(int((~t.marker).sum())), float(r["empty"]), float(r["unseen"]), float(t.depth or 0),
            np.log1p(t.step), float(r["position"])] + bag


def report(name, members, draws, positions, label):
    """encoder.value_draw_metrics of per-table scores `draws` (per draw, one array per member) over the lists, which
    pretrain.py's held-out log gives under "value_" and the same names."""
    r = E.value_draw_metrics(members, draws, positions, label=label)
    show = lambda x: "none" if x is None else f"{x:.3f}"
    spread = lambda k: (f" (each draw alone {show(r[k + '_min'])} to {show(r[k + '_max'])})" if r["draws"] > 1 else "")
    mean = f"of the mean score over {r['draws']} draws of identifiers " if r["draws"] > 1 else ""
    print(f"{name}: pairwise ranking accuracy {mean}{show(r['pair_acc'])}{spread('pair_acc')} over {r['pairs']} pairs "
          f"of {r['ranked_lists']} ranked lists ({show(r['pair_acc_sampled'])} over the {r['pairs_sampled']} pairs of "
          f"sampled continuations alone), AUC within a list {show(r['auc'])}{spread('auc')} "
          f"({show(r['auc_sampled'])} over sampled continuations alone), the mean over the ranked lists of "
          f"{r['lists']} lists", flush=True)
    return r


def logistic(train_members, held_members, positions, steps, seed, label, columns=None):
    """Per-table scores of the held-out members from a logistic regression on `features`, on those of the indices
    `columns` where given."""
    pick = (lambda f: f) if columns is None else (lambda f: [f[i] for i in columns])
    def rows(ms):
        x, y = [], []
        for m in ms:
            for t, r in zip(m["tables"], m["records"]):
                if 0 <= r["position"] < positions and not E.value_excluded(r) and (label == "solving" or not r["unjudged"]):
                    x.append(pick(features(t, r))); y.append(float(r[label]))
        return torch.tensor(x, dtype=torch.float32), torch.tensor(y)
    x, y = rows(train_members)
    mu, sd = x.mean(0), x.std(0).clamp_min(1e-6)
    torch.manual_seed(seed)
    lin = nn.Linear(x.shape[1], 1)
    opt = torch.optim.Adam(lin.parameters(), lr=0.05)
    for _ in range(steps):
        loss = nn.functional.binary_cross_entropy_with_logits(lin((x - mu) / sd).squeeze(-1), y)
        opt.zero_grad(); loss.backward(); opt.step()
    print(f"logistic regression: {len(y)} training tables, final training loss {loss.item():.3f}")
    with torch.no_grad():
        return [lin((torch.tensor([pick(features(t, r)) for t, r in zip(m["tables"], m["records"])], dtype=torch.float32)
                     - mu) / sd).squeeze(-1).numpy() for m in held_members]


def load(value_tables, data, cfg, allow_violations=False):
    """The members of the rollout export (encoder.load_rollouts, with the tables cache at `<data>/<export
    name>.tables.cache` and the budgets of the run's `cfg`, strict unless `allow_violations`), those of training tasks
    and those of held-out tasks as the data marks them, and the data's (names, kinds)."""
    members, skipped = E.load_rollouts(value_tables, f"{data}/{Path(value_tables).resolve().name}.tables.cache",
                                       cfg["enc_budget"], cfg.get("enc_max_rows", 4000), strict=not allow_violations,
                                       allow_violations=allow_violations)
    if skipped:
        print(f"DATA FAULT: {len(skipped)} rollout cases whose tables export cannot be read, left out: {skipped}")
    cases, held_cases, names, kinds, _ = T.load(data)
    train_tasks, held_tasks = {c["task"] for c in cases}, {c["task"] for c in held_cases}
    train_m = [m for m in members.values() if m["group"][0] in train_tasks]
    held_m = [m for m in members.values() if m["group"][0] in held_tasks]
    print(f"{len(members)} continuations; {len(train_m)} of training tasks at {len({m['group'] for m in train_m})} "
          f"branch points, {len(held_m)} of held-out tasks at {len({m['group'] for m in held_m})} branch points")
    assert held_m, "no continuation of a held-out task"
    return members, train_m, held_m, (names, kinds)


def build_encoder(cfg, value_tables, members, device, state=None):
    """The encoder of the run's `cfg` for the rollout export, its embedding built from `cfg["base"]` as train.py
    builds it, with the encoder's `state` where given and its random initialization otherwise; in eval mode."""
    from transformers import AutoModelForCausalLM, AutoTokenizer
    in_names = cfg["in_names"]
    tok = AutoTokenizer.from_pretrained(cfg["base"])
    base = AutoModelForCausalLM.from_pretrained(cfg["base"], dtype=torch.float32)
    table = base.get_input_embeddings().weight.detach()
    embed = nn.Embedding(len(in_names), table.shape[1])
    embed.weight.data = torch.stack([T.name_vector(table, tok, n) for n in in_names])
    del base, table
    enc = E.FeatureEncoder(embed, {n: i for i, n in enumerate(in_names)}, cfg["id_dim"],
                           json.load(open(f"{value_tables}/orientations.json")), K=cfg["enc_k"],
                           layers=cfg["enc_layers"], c=cfg["enc_width"], heads=cfg["enc_heads"], mlp=cfg["enc_mlp"],
                           gram=cfg["enc_gram"], examples=E.max_example({m["key"]: m["tables"] for m in members.values()}) + 1,
                           equality=cfg["enc_equality"], source_rows=cfg["enc_source_rows"],
                           ptr_equality=cfg["enc_ptr_equality"],
                           parent_bias=cfg.get("enc_parent_bias", 0.0)).to(device)
    if state is not None:
        missing, unexpected = enc.load_state_dict(state, strict=False)
        assert not unexpected and all(k.startswith("embed.") for k in missing), (missing, unexpected)
    return enc.eval()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--encoder", required=True, help="an encoder.pt that pretrain.py --value saved")
    ap.add_argument("--value-tables", required=True, help="a rollout export with its labels.jsonl")
    ap.add_argument("--data", default="work/lm/data", help="the data whose held-out tasks give the split")
    ap.add_argument("--positions", type=int, default=None, help="default: the run's --value-positions")
    ap.add_argument("--value-label", choices=E.VALUE_LABELS, default="solving", help="pretrain.py's flag")
    ap.add_argument("--lr-steps", type=int, default=300, help="the logistic regression's steps")
    ap.add_argument("--draws", type=int, default=4,
                    help="the draws of identifiers that the value head's score of a table is the mean over")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--allow-check-violations", action="store_true",
                    help="read a rollout export whose checks.txt reports violations, and one whose copy flows break "
                         "their join (encoder.load_tables, strict and allow_violations); off by default")
    a = ap.parse_args()
    ck = torch.load(a.encoder, map_location=a.device)
    cfg = ck["config"]
    assert "value_head" in ck, f"{a.encoder} holds no value head"
    positions = a.positions or cfg.get("value_positions", 1)
    torch.manual_seed(a.seed); random.seed(a.seed)

    members, train_m, held_m, _ = load(a.value_tables, a.data, cfg, a.allow_check_violations)
    enc = build_encoder(cfg, a.value_tables, members, a.device, ck["state"])
    head = E.ValueHead(cfg["enc_width"], cfg["enc_gram"], cfg["enc_k"]).to(a.device)
    head.load_state_dict(ck["value_head"])
    enc.eval(); head.eval()

    value, compress = [[] for _ in range(a.draws)], []
    gen, cgen = torch.Generator().manual_seed(1), torch.Generator().manual_seed(1)
    with torch.no_grad():
        for m in held_m:
            for d in value:
                d.append(E.value_scores(enc, head, [m], gen, cfg["id_dim"])[0].cpu().numpy())
            decls = E.value_relations(m["tables"], cfg["id_dim"], cgen)
            loss_sum, fields = np.zeros(len(m["tables"])), np.zeros(len(m["tables"]))
            for kind in ("program", "prior"):
                _, recs = enc.masked_loss([(m["tables"], decls)], cgen, cfg["mask_frac"], cfg["mask_cap"],
                                          torch.Generator().manual_seed(2), kind=kind)
                for _, t, r in recs:
                    loss_sum[t] += r["loss"].sum().item(); fields[t] += len(r["loss"])
            compress.append(np.where(fields > 0, -loss_sum / np.maximum(fields, 1), np.nan))
    listed = [x for m, c in zip(held_m, compress) for x, r in zip(c, m["records"])
              if 0 <= r["position"] < positions and not E.value_excluded(r)]
    mean = float(np.nanmean(listed)) if listed and not np.isnan(listed).all() else 0.0
    print(f"compressibility: {int(np.isnan(listed).sum())} of {len(listed)} listed tables have no hidden field and "
          f"take the mean score")
    compress = [np.nan_to_num(c, nan=mean) for c in compress]
    lab = a.value_label
    out = {"value_head": report("value head", held_m, value, positions, lab),
           "logistic": report("logistic regression on trivial features", held_m,
                              [logistic(train_m, held_m, positions, a.lr_steps, a.seed, lab)], positions, lab),
           "compressibility": report("compressibility", held_m, [compress], positions, lab)}
    print(json.dumps(out))


if __name__ == "__main__":
    main()
