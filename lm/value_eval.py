"""Measure a pretrained value head (pretrain.py --value) on a rollout export, against two baselines.

    work/lm/.venv/bin/python lm/value_eval.py --encoder <run>/encoder.pt --value-tables work/tables/rollouts-afc44b43 \
        [--data work/lm/data] [--positions P] [--device cpu]

The branch points are split as pretrain.py splits them: a branch point is held out where the data (`--data`, its
cases.npz) marks its task held out, and is a training one where its task is a training task. On the held-out branch
points, each score below is measured over the lists of encoder.py's `value_lists` (the tables at the positions below
`--positions` after the branch, the empty, unseen and faulted ones left out), as the pairwise ranking accuracy (over
each list's pairs of a solving and a non-solving continuation, a tie one half) and the AUC (over every listed
continuation's score, across lists), and the pairwise ranking accuracy once more over the sampled continuations
alone, without the gold one, whose author differs:

- the value head: its logit;
- a logistic regression on trivial features of a table, trained by full-batch Adam for `--lr-steps` steps on the
  training branch points' listed tables with each continuation's label: the log of its row count, whether it is
  empty, whether it is unseen, its depth, the log of its step index, its position after the branch, and the count of
  its columns of each type;
- compressibility: minus the encoder's masked loss per hidden field of the table, over one program step and one prior
  step's mask (`masked_loss`); a table with no hidden field takes the mean score.
"""
import argparse, json, random
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn

import encoder as E
import train as T


def features(t, r):
    """The trivial features of table t with its value record r."""
    bag = [sum(ty == name for ty in t.types) for name in E.TYPE_NAMES]
    return [np.log1p(int((~t.marker).sum())), float(r["empty"]), float(r["unseen"]), float(t.depth or 0),
            np.log1p(t.step), float(r["position"])] + bag


def report(name, members, scores, positions):
    """The pairwise ranking accuracy and the AUC of per-table `scores` (one array per member) over the lists."""
    lists = E.value_lists(members, [torch.as_tensor(s, dtype=torch.float32) for s in scores], positions)
    right, pairs = E.value_pairs(lists)
    right_s, pairs_s = E.value_pairs(lists, sampled=True)
    auc = E.auc([float(x) for l in lists for x in l["scores"]], [bool(y) for l in lists for y in l["labels"]])
    acc = f"{right / pairs:.3f}" if pairs else "none"
    acc_s = f"{right_s / pairs_s:.3f}" if pairs_s else "none"
    print(f"{name}: pairwise ranking accuracy {acc} over {pairs} pairs of {sum(l['ranked'] for l in lists)} ranked "
          f"lists ({acc_s} over the {pairs_s} pairs of sampled continuations alone), AUC "
          f"{'none' if auc is None else f'{auc:.3f}'} over {sum(len(l['labels']) for l in lists)} continuations of "
          f"{len(lists)} lists", flush=True)
    return dict(pair_acc=right / pairs if pairs else None, pair_acc_sampled=right_s / pairs_s if pairs_s else None,
                auc=auc, pairs=pairs, lists=len(lists))


def logistic(train_members, held_members, positions, steps, seed):
    """Per-table scores of the held-out members from a logistic regression on `features`."""
    def rows(ms):
        x, y = [], []
        for m in ms:
            for t, r in zip(m["tables"], m["records"]):
                if 0 <= r["position"] < positions and not E.value_excluded(r):
                    x.append(features(t, r)); y.append(float(m["solving"]))
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
        return [lin((torch.tensor([features(t, r) for t, r in zip(m["tables"], m["records"])], dtype=torch.float32)
                     - mu) / sd).squeeze(-1).numpy() for m in held_members]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--encoder", required=True, help="an encoder.pt that pretrain.py --value saved")
    ap.add_argument("--value-tables", required=True, help="a rollout export with its labels.jsonl")
    ap.add_argument("--data", default="work/lm/data", help="the data whose held-out tasks give the split")
    ap.add_argument("--positions", type=int, default=None, help="default: the run's --value-positions")
    ap.add_argument("--lr-steps", type=int, default=300, help="the logistic regression's steps")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--device", default="cpu")
    a = ap.parse_args()
    ck = torch.load(a.encoder, map_location=a.device)
    cfg = ck["config"]
    assert "value_head" in ck, f"{a.encoder} holds no value head"
    positions = a.positions or cfg.get("value_positions", 1)
    torch.manual_seed(a.seed); random.seed(a.seed)

    members, skipped = E.load_rollouts(a.value_tables, f"{a.data}/{Path(a.value_tables).resolve().name}.tables.pkl",
                                       cfg["enc_budget"], cfg.get("enc_max_rows", 4000))
    if skipped:
        print(f"DATA FAULT: {len(skipped)} rollout cases whose tables export cannot be read, left out: {skipped}")
    cases, held_cases, names, kinds, _ = T.load(a.data)
    train_tasks, held_tasks = {c["task"] for c in cases}, {c["task"] for c in held_cases}
    train_m = [m for m in members.values() if m["group"][0] in train_tasks]
    held_m = [m for m in members.values() if m["group"][0] in held_tasks]
    print(f"{len(members)} continuations; {len(train_m)} of training tasks, {len(held_m)} of held-out tasks, at "
          f"{len({m['group'] for m in held_m})} held-out branch points")
    assert held_m, "no continuation of a held-out task"

    from transformers import AutoModelForCausalLM, AutoTokenizer
    in_names = cfg["in_names"]
    tok = AutoTokenizer.from_pretrained(cfg["base"])
    base = AutoModelForCausalLM.from_pretrained(cfg["base"], dtype=torch.float32)
    table = base.get_input_embeddings().weight.detach()
    embed = nn.Embedding(len(in_names), table.shape[1])
    embed.weight.data = torch.stack([T.name_vector(table, tok, n) for n in in_names])
    del base, table
    enc = E.FeatureEncoder(embed, {n: i for i, n in enumerate(in_names)}, cfg["id_dim"],
                           json.load(open(f"{a.value_tables}/orientations.json")), K=cfg["enc_k"],
                           layers=cfg["enc_layers"], c=cfg["enc_width"], heads=cfg["enc_heads"], mlp=cfg["enc_mlp"],
                           gram=cfg["enc_gram"], examples=E.max_example({m["key"]: m["tables"] for m in members.values()}) + 1,
                           equality=cfg["enc_equality"], source_rows=cfg["enc_source_rows"],
                           ptr_equality=cfg["enc_ptr_equality"]).to(a.device)
    missing, unexpected = enc.load_state_dict(ck["state"], strict=False)
    assert not unexpected and all(k.startswith("embed.") for k in missing), (missing, unexpected)
    head = E.ValueHead(cfg["enc_width"], cfg["enc_gram"], cfg["enc_k"]).to(a.device)
    head.load_state_dict(ck["value_head"])
    enc.eval(); head.eval()

    gen = torch.Generator().manual_seed(1)
    value, compress = [], []
    with torch.no_grad():
        for m in held_m:
            decls = E.value_relations(m["tables"], cfg["id_dim"], gen)
            s = E.pooled_vectors(enc, [(m["tables"], decls)], gen)[0]
            value.append(head(enc.readout, s).float().cpu().numpy())
            loss_sum, fields = np.zeros(len(m["tables"])), np.zeros(len(m["tables"]))
            for kind in ("program", "prior"):
                _, recs = enc.masked_loss([(m["tables"], decls)], gen, cfg["mask_frac"], cfg["mask_cap"],
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
    out = {"value_head": report("value head", held_m, value, positions),
           "logistic": report("logistic regression on trivial features", held_m,
                              logistic(train_m, held_m, positions, a.lr_steps, a.seed), positions),
           "compressibility": report("compressibility", held_m, compress, positions)}
    print(json.dumps(out))


if __name__ == "__main__":
    main()
