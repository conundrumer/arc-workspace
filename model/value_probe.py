"""Probe the value head's input, the encoder's frame-free readout of a table (encoder.py, `value_input`), by linear
regressions fitted on the training branch points of a rollout export and scored on the held-out ones.

    work/lm/.venv/bin/python model/value_probe.py --value-tables <rollout export> --data <data> [--encoder <encoder.pt>]
        [--positions 4] [--draws 2] [--groups N] [--seed 0] [--device cpu]

Without `--encoder`, the encoder is a random initialization of pretrain.py's default shape. The members, the split
and the encoder come from value_eval.py (`load`, `build_encoder`), so the tables cache is
`<data>/<export name>.tables.cache`, as value_eval.py's is. The probed tables are those of the lists of encoder.py's
`value_lists` under the solving label: the tables at the positions below `--positions` after the branch, the empty,
unseen and faulted ones left out. Each member is encoded whole, `--draws` times under fresh identifiers, and a table's
vector is its readout's mean over the draws. The encoding's time grows with the tables of the encoded members, and a
few branch points hold most of them, so two flags cut the input for a quick run: `--max-group-tables N` keeps the
branch points whose members with a listed table hold N tables or fewer in all, and `--groups N` then keeps N training
and N held-out branch points, drawn with `--seed`.

A ridge regression, on the readout with each column standardized over the training tables, has its penalty chosen by
5-fold cross-validation over the training branch points. The probe targets, each one row of the printed table:

- the solving label, scored by the pairwise ranking accuracy and the AUC within a list (encoder.py, `value_metrics`),
  from the readout, from the readout after the head's LayerNorm without its affine part (each table's vector
  normalized by its own mean and spread), from the trivial features of value_eval.py (`features`), and from the
  readout and the trivial features together, the trivial features scaled by 30 so that the penalty on them is
  1/900 of that on a readout column;
- each trivial feature, from the readout and from the LayerNorm's output, scored by the held-out R^2 (a feature of
  two values by the AUC, and one constant over the training tables is reported as constant);
- value_eval.py's logistic regression on the trivial features (`logistic`), and the same without the position and
  the step index;
- with `--encoder`, the trained value head's own logit, the mean over the draws.

The time of the encoding is reported per 1,000 tables encoded under one draw.
"""
import argparse, random, time

import numpy as np
import torch

import encoder as E
import pretrain as P
import train as T
import value_eval as VE

LABEL = "solving"
BOOST = 30.0   # the scale of the trivial features beside the readout


def listed(m, positions):
    """The indices of the tables of member m that the lists of `value_lists` take at the positions below `positions`."""
    return [i for i, r in enumerate(m["records"]) if 0 <= r["position"] < positions and not E.value_excluded(r)]


def encode(enc, head, members, positions, draws, id_dim, gen):
    """Per member, the mean readout over `draws` draws of its listed tables [n_listed, w], and the head's mean logit
    of them (None without `head`); the tables encoded."""
    xs, zs, n = [], [], 0
    with torch.no_grad():
        for m in members:
            idx = listed(m, positions)
            if not idx:
                xs.append(None); zs.append(None)
                continue
            got = [E.value_inputs(enc, [m], gen, id_dim)[0][idx].float() for _ in range(draws)]
            n += draws * len(m["tables"])
            xs.append(torch.stack(got).mean(0).cpu().numpy())
            zs.append(None if head is None else torch.stack([head.score(x) for x in got]).mean(0).cpu().numpy())
    return xs, zs, n


def layer_norm(x):
    """The head's LayerNorm without its affine part, per row."""
    return (x - x.mean(1, keepdims=True)) / np.sqrt(x.var(1, keepdims=True) + 1e-5)


def ridge(x, y, groups, seed, folds=5, lams=(1e-3, 1e-2, 1e-1, 1, 10, 100, 1e3, 1e4)):
    """A ridge regression of y on x, its penalty lam times the mean of the kernel's diagonal chosen by `folds`-fold
    cross-validation over the groups: (predict, the chosen lam)."""
    mu, sd = x.mean(0), x.std(0)
    sd = np.where(sd > 1e-8, sd, np.inf)

    def fit(xs, ys):
        xc, yc = (xs - mu) / sd, ys - ys.mean()
        xm = xc.mean(0)
        xc = xc - xm
        s, u = np.linalg.eigh(xc @ xc.T)
        s, scale = np.clip(s, 0, None), max(np.trace(xc @ xc.T) / len(xc), 1e-12)
        uy = u.T @ yc
        return lambda lam: (xc.T @ (u @ (uy / (s + lam * scale))), xm, ys.mean())

    def predict(model, xs):
        w, xm, b = model
        return ((xs - mu) / sd - xm) @ w + b

    keys = sorted(set(groups))
    random.Random(seed).shuffle(keys)
    fold = {g: k % folds for k, g in enumerate(keys)}
    f = np.array([fold[g] for g in groups])
    err = np.zeros(len(lams))
    for k in range(folds):
        tr, va = f != k, f == k
        if not va.any() or not tr.any():
            continue
        solve = fit(x[tr], y[tr])
        for j, lam in enumerate(lams):
            err[j] += ((predict(solve(lam), x[va]) - y[va]) ** 2).sum()
    lam = lams[int(np.argmin(err))]
    model = fit(x, y)(lam)
    return (lambda xs: predict(model, xs)), lam


def full_scores(members, positions, per_listed):
    """Per member, a score per table: the listed tables' from `per_listed` (an array per member, or None), 0 elsewhere."""
    out = []
    for m, z in zip(members, per_listed):
        s = np.zeros(len(m["tables"]), np.float32)
        if z is not None:
            s[listed(m, positions)] = z
        out.append(s)
    return out


def label_metrics(members, positions, scores):
    return E.value_metrics(E.value_lists(members, [torch.as_tensor(s) for s in scores], positions, label=LABEL))


def stack(members, positions, xs):
    """The rows of the listed tables of `members` with their per-member arrays `xs`: (x, trivial features, labels,
    groups, the count of rows per member)."""
    x, f, y, g, counts = [], [], [], [], []
    for m, a in zip(members, xs):
        idx = listed(m, positions)
        counts.append(len(idx))
        if not idx:
            continue
        x.append(a)
        f += [VE.features(m["tables"][i], m["records"][i]) for i in idx]
        y += [float(m["records"][i][LABEL]) for i in idx]
        g += [m["group"]] * len(idx)
    return np.concatenate(x), np.array(f, float), np.array(y), g, counts


def split_rows(z, counts):
    out, at = [], 0
    for c in counts:
        out.append(z[at:at + c] if c else None)
        at += c
    return out


def r2(pred, y):
    sst = ((y - y.mean()) ** 2).sum()
    return None if sst == 0 else float(1 - ((pred - y) ** 2).sum() / sst)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--encoder", help="an encoder.pt that pretrain.py saved; default: a random initialization")
    ap.add_argument("--base", default="HuggingFaceTB/SmolLM2-135M", help="the base LM of a random-init encoder; ignored with --encoder")
    ap.add_argument("--value-tables", required=True, help="a rollout export with its labels.jsonl")
    ap.add_argument("--data", default="work/lm/data", help="the data whose held-out tasks give the split")
    ap.add_argument("--positions", type=int, default=4)
    ap.add_argument("--draws", type=int, default=2)
    ap.add_argument("--max-group-tables", type=int, default=0,
                    help="keep the branch points whose encoded members hold this many tables or fewer (0: all)")
    ap.add_argument("--groups", type=int, default=0, help="keep this many training and held-out branch points (0: all)")
    ap.add_argument("--lr-steps", type=int, default=300, help="the logistic regression's steps")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--device", default="cpu")
    a = ap.parse_args()
    start = time.time()
    torch.manual_seed(a.seed); random.seed(a.seed)
    ck = torch.load(a.encoder, map_location=a.device) if a.encoder else None
    cfg = dict(ck["config"]) if ck else P.run_config(P.parser().parse_args(["--tables", "", "--out", "", "--base", a.base]), None)
    members, train_m, held_m, (names, kinds) = VE.load(a.value_tables, a.data, cfg)
    if cfg["in_names"] is None:
        cfg["in_names"] = T.vocabularies(names, kinds)[0]
    if a.max_group_tables:
        def small(ms):
            size = {}
            for m in ms:
                size[m["group"]] = size.get(m["group"], 0) + (len(m["tables"]) if listed(m, a.positions) else 0)
            return [m for m in ms if size[m["group"]] <= a.max_group_tables]
        train_m, held_m = small(train_m), small(held_m)
        print(f"--max-group-tables {a.max_group_tables}: {len(train_m)} training continuations at "
              f"{len({m['group'] for m in train_m})} branch points and {len(held_m)} held-out at "
              f"{len({m['group'] for m in held_m})}")
    if a.groups:
        def keep(ms):
            gs = sorted({m["group"] for m in ms})
            gs = set(random.Random(a.seed).sample(gs, min(a.groups, len(gs))))
            return [m for m in ms if m["group"] in gs]
        train_m, held_m = keep(train_m), keep(held_m)
        print(f"--groups {a.groups}: {len(train_m)} training and {len(held_m)} held-out continuations")
    enc = VE.build_encoder(cfg, a.value_tables, members, a.device, ck["state"] if ck else None)
    head = None
    if ck and "value_head" in ck:
        head = E.ValueHead(cfg["enc_width"], cfg["enc_gram"], cfg["enc_k"]).to(a.device)
        head.load_state_dict(ck["value_head"])
        head.eval()
    print(f"loaded in {time.time() - start:.1f} s", flush=True)

    gen = torch.Generator().manual_seed(1)
    t0 = time.time()
    xs_tr, _, n_tr = encode(enc, None, train_m, a.positions, a.draws, cfg["id_dim"], gen)
    xs_he, zs_he, n_he = encode(enc, head, held_m, a.positions, a.draws, cfg["id_dim"], gen)
    dt = time.time() - t0
    x_tr, f_tr, y_tr, g_tr, c_tr = stack(train_m, a.positions, xs_tr)
    x_he, f_he, y_he, _, c_he = stack(held_m, a.positions, xs_he)
    print(f"encoded {n_tr + n_he} tables (all tables of each member with a listed table, times {a.draws} draws) in "
          f"{dt:.1f} s, {1000 * dt / max(n_tr + n_he, 1):.2f} s per 1,000 tables; probed {len(y_tr)} training and "
          f"{len(y_he)} held-out tables, readout width {x_tr.shape[1]}", flush=True)

    show = lambda v: "none" if v is None else f"{v:.3f}"
    ranked = lambda r: f"pair acc {show(r['pair_acc'])}, AUC {show(r['auc'])}"
    inputs = {"readout": (x_tr, x_he), "LayerNorm(readout)": (layer_norm(x_tr), layer_norm(x_he))}
    rows = [("probe target", "input", "held-out", "training")]

    def label_row(target, inp, xtr, xhe):
        pred, lam = ridge(xtr, y_tr, g_tr, a.seed)
        held = label_metrics(held_m, a.positions, full_scores(held_m, a.positions, split_rows(pred(xhe), c_he)))
        train = label_metrics(train_m, a.positions, full_scores(train_m, a.positions, split_rows(pred(xtr), c_tr)))
        rows.append((target, inp, f"{ranked(held)} over {held['pairs']} pairs",
                     f"{ranked(train)} over {train['pairs']} pairs, lam {lam:g}"))

    for name, (xtr, xhe) in inputs.items():
        label_row("(a) label, ridge", name, xtr, xhe)
    label_row("(a) label, ridge", "trivial features", f_tr, f_he)
    scale = BOOST / f_tr.std(0).clip(1e-8)
    label_row("(d) label, ridge", "readout + trivial features", np.hstack([x_tr, scale * f_tr]),
              np.hstack([x_he, scale * f_he]))
    constant = []
    for k, feat in enumerate(VE.FEATURES):
        ytr, yhe = f_tr[:, k], f_he[:, k]
        if ytr.std() == 0:
            constant.append(f"{feat} {ytr[0]:g}")
            continue
        for name, (xtr, xhe) in inputs.items():
            pred, lam = ridge(xtr, ytr, g_tr, a.seed)
            if len(set(ytr) | set(yhe)) == 2:
                rows.append((f"(b) {feat}", name, f"AUC {show(E.auc(pred(xhe), yhe == ytr.max()))}",
                             f"AUC {show(E.auc(pred(xtr), ytr == ytr.max()))}, lam {lam:g}"))
            else:
                rows.append((f"(b) {feat}", name, f"R2 {show(r2(pred(xhe), yhe))}",
                             f"R2 {show(r2(pred(xtr), ytr))}, lam {lam:g}"))
    pos, step = VE.FEATURES.index("position"), VE.FEATURES.index("log step index")
    others = lambda *drop: [i for i in range(len(VE.FEATURES)) if i not in drop]
    for inp, cols in (("trivial features", None), ("without position and step index", others(pos, step)),
                      ("without position", others(pos)), ("without step index", others(step)),
                      ("position and step index alone", [pos, step])):
        r = label_metrics(held_m, a.positions, VE.logistic(train_m, held_m, a.positions, a.lr_steps, a.seed, LABEL, cols))
        rows.append(("(c) label, logistic", inp, f"{ranked(r)} over {r['pairs']} pairs", ""))
    if head is not None:
        r = label_metrics(held_m, a.positions, full_scores(held_m, a.positions, zs_he))
        rows.append(("label, value head", "its logit", f"{ranked(r)} over {r['pairs']} pairs", ""))

    wide = [max(len(r[i]) for r in rows) for i in range(3)]
    print()
    for r in rows:
        print(f"{r[0]:<{wide[0]}}  {r[1]:<{wide[1]}}  {r[2]:<{wide[2]}}  {r[3]}")
    if constant:
        print(f"constant over the training tables, not probed: {', '.join(constant)}")
    print(f"total {time.time() - start:.1f} s")


if __name__ == "__main__":
    main()
