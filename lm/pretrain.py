"""Pretrain the feature encoder alone on the masked table loss (encoder.py, `masked_loss`), before the language
model's fine-tune.

Each step takes training programs in a random order, up to `--programs` of them, while their summed cost
(`step_cost`) stays within `--step-rows`, and at least one; it encodes every table of each, in the program's order,
so the earlier tables' vectors that a later table reads are trained too. Each program's step is a program
step, an output step or a prior step (`--mask-kind`): a program step hides a fraction of the computed fields, an
output step a fraction of the computed fields of `ex_output` alone, and a prior step a fraction of the inferrable
fields (encoder.py, `draw_masks`), and the encoder predicts them. The loss is the program part, over the computed
fields of the program and output steps, plus `--prior-weight` times the prior part. The held-out programs, those the data marks held out, are
evaluated every `--eval-every` steps with fixed masks and identifiers, on a sample of `--eval-limit` of them drawn once with `--seed` (0: all); the log (JSON lines, as train.py writes)
gives the masked loss, each part's loss, and per part the loss and the accuracy per column type, with the fields of
`ex_output` under "ex_output/<type>", and where the export gives depths, the program part per depth bucket of the
derived tables (`by_depth`: 1, 2, 3, 4+); a Box or Position field is right when all four margins are, and its type also
gives the edge accuracy, of single margins.

The encoder's state, without the language model's embedding that it shares, goes to <out>/encoder.pt at the
lowest held-out loss, for `train.py --encoder-init`. The embedding is built as train.py builds it, from `--base`,
and stays fixed here.

    work/lm/.venv/bin/python -u lm/pretrain.py --base HuggingFaceTB/SmolLM2-135M --data lm/data-dev \
        --tables work/tables/dev --out lm/runs/pretrain-dev --steps 40
"""
import argparse, json, random, re, time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from transformers import AutoModelForCausalLM, AutoTokenizer

import encoder as E
import train as T


PARTS = ("program", "prior")

# A program's cost in a step, in rows: the device memory that its encoding keeps for the backward pass with
# --enc-checkpoint is about that of its rows (every table's, the evidence tables' too), plus TABLE_COST rows per table,
# plus PAIR_COST rows per pair of its tables, for the earlier tables' pooled vectors that a table reads. Measured on
# the CPU under bf16 autocast at c 64, 4 layers, 8 heads, K 4: about 106 KB per row, 1.5 MB per table and 65 KB per
# pair. A table's evidence rows cost no memory per table that reads them, since the Block call builds them again in
# the backward pass.
TABLE_COST, PAIR_COST = 15, 0.6


def step_cost(tables):
    n = len(tables)
    return sum(t.n for t in tables) + TABLE_COST * n + PAIR_COST * n * (n - 1) / 2


def draw(train, programs, cap):
    """The step's programs: a random order of up to `programs` of `train`, cut before the first whose cost would
    take the sum past `cap`, and at least the first; and their summed cost."""
    out, cost = [], 0.0
    for c in random.sample(train, min(programs, len(train))):
        if out and cost + c["cost"] > cap:
            break
        out.append(c); cost += c["cost"]
    return out, cost


DEPTHS = ("1", "2", "3", "4+")


def depth_bucket(depth):
    """The `by_depth` bucket of a derived table's depth, or None for a table without one."""
    return None if depth is None or depth < 1 else DEPTHS[min(depth, 4) - 1]


def summarize(records, by=None):
    """Per part, per label, over the records of masked_loss: [loss sum, fields right, fields, margins right], the
    last for a Box or Position, of four per field; and under "depth", the same per depth bucket (`depth_bucket`)
    over the program part's fields of the derived tables that give a depth; added to `by` where it is given."""
    by = {**{p: {} for p in PARTS}, "depth": {}} if by is None else by
    for _, _, r in records:
        bucket = depth_bucket(r.get("depth")) if r["part"] == "program" else None
        for lab, l, ok, e in zip(r["label"], r["loss"].tolist(), r["correct"].tolist(), r["edges"].tolist()):
            for x in [by[r["part"]].setdefault(lab, [0.0, 0, 0, 0])] + (
                    [by["depth"].setdefault(bucket, [0.0, 0, 0, 0])] if bucket else []):
                x[0] += l; x[1] += ok; x[2] += 1; x[3] += max(e, 0)
    return by


def by_type(by):
    """The per-label table of the log: loss and accuracy (a Box or Position: all four margins right), and for a
    Box or Position, the edge accuracy (a margin right)."""
    return {k: {"loss": x[0] / x[2], "accuracy": x[1] / x[2], "fields": x[2],
                **({"edge_accuracy": x[3] / (4 * x[2])} if k.split("/")[-1] in ("Box", "Position") else {})}
            for k, x in sorted(by.items())}


def losses(by, prior_weight):
    """The log's loss entries of `summarize`'s result: the loss, each part's mean loss, and the fields of each part,
    with the parts per label, and where the tables give depths, the program part per depth bucket (`by_depth`:
    loss, accuracy and fields)."""
    mean = {p: sum(x[0] for x in by[p].values()) / max(sum(x[2] for x in by[p].values()), 1) for p in PARTS}
    depth = {k: {"loss": by["depth"][k][0] / by["depth"][k][2], "accuracy": by["depth"][k][1] / by["depth"][k][2],
                 "fields": by["depth"][k][2]} for k in DEPTHS if k in by["depth"]}
    return {"loss": mean["program"] + prior_weight * mean["prior"], "program_loss": mean["program"],
            "prior_loss": mean["prior"], **{f"{p}_fields": sum(x[2] for x in by[p].values()) for p in PARTS},
            "by_type": {p: by_type(by[p]) for p in PARTS}, **({"by_depth": depth} if depth else {})}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="Qwen/Qwen3-0.6B", help="the language model whose embedding the encoder shares")
    ap.add_argument("--data", default="work/lm/data")
    ap.add_argument("--tables", required=True, help="a tables export (engine/arclog-py/tables_export.py)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--steps", type=int, default=1000)
    ap.add_argument("--minutes", type=float, default=0, help="stop after this long, if given")
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--warmup", type=int, default=20, help="steps of linear warmup")
    ap.add_argument("--programs", type=int, default=4, help="the most programs per step")
    ap.add_argument("--step-rows", type=int, default=450_000,
                    help="the most summed cost of a step's programs, in rows (step_cost); a program over it runs alone. "
                         "The default keeps about 48 GB for the backward pass at c 64, 4 layers, 8 heads, K 4")
    ap.add_argument("--eval-every", type=int, default=10, help="steps")
    ap.add_argument("--eval-limit", type=int, default=64,
                    help="evaluate on a fixed sample of this many held-out programs, drawn once with --seed (0: all)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--mask-frac", type=float, default=0.15, help="the fraction of fields the masked loss hides per table")
    ap.add_argument("--mask-cap", type=int, default=512, help="the most fields hidden per table")
    ap.add_argument("--preflight", action=argparse.BooleanOptionalAction, default=True,
                    help="before the model loads, run the masked loss's data path on every program with no model "
                         "(encoder.preflight), which stops the run at the first program it cannot mask")
    ap.add_argument("--mask-kind", choices=["alternate", "program", "output", "prior"], default="alternate",
                    help="the step kind of each program: a program step hides computed fields, an output step the "
                         "computed fields of ex_output alone, a prior step inferrable fields, and alternate takes the "
                         "three by turns, by the step and the program's place in the step")
    ap.add_argument("--prior-weight", type=float, default=1.0,
                    help="the weight of the prior part of the masked loss beside its program part")
    ap.add_argument("--id-dim", type=int, default=64)
    ap.add_argument("--enc-k", type=int, default=4)
    ap.add_argument("--enc-layers", type=int, default=2)
    ap.add_argument("--enc-width", type=int, default=32)
    ap.add_argument("--enc-heads", type=int, default=4)
    ap.add_argument("--enc-mlp", type=int, default=2)
    ap.add_argument("--enc-gram", type=int, default=16)
    ap.add_argument("--enc-budget", type=int, default=10000)
    ap.add_argument("--enc-max-rows", type=int, default=4000,
                    help="a guard on device memory: a table of more rows than this, summed over its entries, is unseen")
    ap.add_argument("--autocast", action=argparse.BooleanOptionalAction, default=None,
                    help="run the encoder under bf16 autocast, with fp32 weights (default: on with cuda, off otherwise)")
    ap.add_argument("--enc-equality", choices=["codes", "random", "flex"], default="codes",
                    help="the means of the encoder's equality term: one-hot codes added to the attention's queries and "
                         "keys, random sign codes of fixed width, or flex_attention (cuda alone)")
    ap.add_argument("--enc-checkpoint", action=argparse.BooleanOptionalAction, default=None,
                    help="recompute the encoder's Block activations in the backward pass to save memory (default: on "
                         "with cuda, off otherwise); without it, each table keeps its evidence rows' keys and values "
                         "at every layer for the backward pass, which does not fit a step of full-data programs")
    ap.add_argument("--max-rows", type=int, default=0,
                    help="leave out each program with a table of more rows than this, summed over its entries (a CPU check)")
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu")
    a = ap.parse_args()
    assert a.enc_equality != "flex" or a.device == "cuda", "--enc-equality flex trains on cuda alone"
    if a.enc_checkpoint is None:
        a.enc_checkpoint = a.device == "cuda"
    torch.manual_seed(a.seed); random.seed(a.seed)
    t0 = time.time()

    cases, held_cases, names, kinds, mask_table = T.load(a.data)
    tables, skipped, _ = E.load_tables(a.tables, f"{a.data}/tables.pkl")
    if skipped:
        print(f"DATA FAULT: {len(skipped)} cases whose tables export cannot be read, left out: {skipped}")
    over = E.mark_over_budget(tables, a.enc_budget)
    for t, c, x, r, n in E.mark_over_rows(tables, a.enc_max_rows):
        print(f"unseen table, over --enc-max-rows {a.enc_max_rows}: {t} {c} table {x} relation {r}: {n} rows")
    unseen_t, unseen_e = E.unseen_counts(tables)
    print(f"{len(over)} entries over --enc-budget {a.enc_budget}; unseen tables {unseen_t}, unseen entries {unseen_e}")
    keep = lambda cs: [c for c in cs if (c["task"], c["case"]) in tables]
    train, held = keep(cases), keep(held_cases)
    if a.max_rows:
        big = lambda c: max(t.n for t in tables[(c["task"], c["case"])]) > a.max_rows
        left = sorted({(c["task"], c["case"]) for c in train + held if big(c)})
        print(f"--max-rows {a.max_rows}: {len(left)} programs left out: {left}")
        train, held = [c for c in train if not big(c)], [c for c in held if not big(c)]
    for c in train + held:
        c["tables"] = tables[(c["task"], c["case"])]
        c["cost"] = step_cost(c["tables"])
    assert train and held, "no training or held-out programs with tables"
    if a.preflight:
        t_pre = time.time()
        E.preflight([((c["task"], c["case"]), c["tables"]) for c in train + held], a.mask_frac, a.mask_cap)
        print(f"preflight: {len(train) + len(held)} programs, {time.time() - t_pre:.0f} s", flush=True)
    if 0 < a.eval_limit < len(held):
        held = random.Random(a.seed).sample(held, a.eval_limit)

    in_names, out_names, in_index, out_index = T.vocabularies(names, kinds)
    tok = AutoTokenizer.from_pretrained(a.base)
    base = AutoModelForCausalLM.from_pretrained(a.base, dtype=torch.float32)
    table = base.get_input_embeddings().weight.detach()
    embed = nn.Embedding(len(in_names), table.shape[1])
    embed.weight.data = torch.stack([T.name_vector(table, tok, n) for n in in_names])
    embed.requires_grad_(False)
    del base, table
    enc = E.FeatureEncoder(embed, in_index, a.id_dim, json.load(open(f"{a.tables}/orientations.json")), K=a.enc_k,
                           layers=a.enc_layers, c=a.enc_width, heads=a.enc_heads, mlp=a.enc_mlp, gram=a.enc_gram,
                           examples=E.max_example(tables) + 1, equality=a.enc_equality).to(a.device)
    rel_token = {int(n[2:]): i for i, n in enumerate(names) if re.fullmatch(r"&r\d+", n)}
    enc.checkpoint = a.enc_checkpoint
    use_autocast = a.device == "cuda" if a.autocast is None else a.autocast
    autocast = lambda: torch.autocast(torch.device(a.device).type, dtype=torch.bfloat16, enabled=use_autocast)
    params = [p for p in enc.parameters() if p.requires_grad]
    opt = torch.optim.AdamW(params, lr=a.lr, weight_decay=0.0)
    sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda i: min(1.0, (i + 1) / a.warmup))
    print(f"{len(train)} training programs, {len(held)} held-out; {sum(map(len, (c['tables'] for c in train)))} "
          f"training tables; encoder {sum(p.numel() for p in params) / 1e6:.2f}M parameters on {a.device}; "
          f"loaded in {time.time() - t0:.0f}s", flush=True)

    def program(c, gen):
        """The program's tables and the identifier of each table's relation, drawn from gen."""
        return T.table_relations(c, a.id_dim, 10 ** 7, gen, a.enc_k, rel_token)

    def evaluate():
        enc.eval()
        t_eval = time.time()
        print(f"evaluating {len(held)} held-out programs", flush=True)
        gen, mask_gen = torch.Generator().manual_seed(1), torch.Generator().manual_seed(2)
        records = []
        with torch.no_grad(), autocast():
            for i in range(0, len(held), a.programs):
                _, r = enc.masked_loss([program(c, gen) for c in held[i:i + a.programs]], gen, a.mask_frac,
                                       a.mask_cap, mask_gen, kind=a.mask_kind, prior_weight=a.prior_weight)
                records += r
                if (i // a.programs + 1) % 10 == 0:
                    print(f"  {min(i + a.programs, len(held))}/{len(held)} programs, {time.time() - t_eval:.0f} s", flush=True)
        enc.train()
        return losses(summarize(records), a.prior_weight)

    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    log = open(out / "log.jsonl", "a")
    config = dict(base=a.base, tables=a.tables, enc_k=a.enc_k, enc_layers=a.enc_layers, enc_width=a.enc_width,
                  enc_heads=a.enc_heads, enc_mlp=a.enc_mlp, enc_gram=a.enc_gram, enc_budget=a.enc_budget,
                  id_dim=a.id_dim, mask_frac=a.mask_frac, mask_cap=a.mask_cap, mask_kind=a.mask_kind,
                  prior_weight=a.prior_weight, in_names=in_names, enc_equality=a.enc_equality)
    gen, mask_gen = torch.Generator().manual_seed(10), torch.Generator().manual_seed(11)
    best, start, step_seconds, by = float("inf"), time.time(), [], None
    for step in range(1, a.steps + 1):
        t = time.time()
        drawn, cost = draw(train, a.programs, a.step_rows)
        with autocast():
            loss, records = enc.masked_loss([program(c, gen) for c in drawn],
                                            gen, a.mask_frac, a.mask_cap, mask_gen, kind=a.mask_kind, step=step,
                                            prior_weight=a.prior_weight)
        assert torch.isfinite(loss), f"step {step}: masked loss {loss.item()}"
        opt.zero_grad(); loss.backward()
        torch.nn.utils.clip_grad_norm_(params, 1.0)
        opt.step(); sched.step()
        step_seconds.append(time.time() - t)
        T.device_memory(a.device)
        by = summarize(records, by)
        if step <= 3 or step % 10 == 0:
            now = losses(summarize(records), a.prior_weight)
            print(f"step {step} masked loss {loss.item():.3f} (program {now['program_loss']:.3f} over "
                  f"{now['program_fields']} fields, prior {now['prior_loss']:.3f} over {now['prior_fields']} fields) "
                  f"{len(drawn)} programs, cost {cost:.0f} rows "
                  f"{np.mean(step_seconds[-10:]):.2f} s/step", flush=True)
        last = step == a.steps or (a.minutes and time.time() - t0 > a.minutes * 60)
        if step % a.eval_every == 0 or last:
            ev = evaluate()
            row = {"step": step, "seconds": round(time.time() - start), "seconds_per_step": float(np.mean(step_seconds)),
                   "device_gb": round(T.device_memory(a.device), 2),
                   "train_loss": loss.item(), "eval_programs": len(held),
                   "train": losses(by, a.prior_weight),
                   "heldout": ev}
            by = None
            log.write(json.dumps(row) + "\n"); log.flush()
            print(json.dumps(row), flush=True)
            if ev["loss"] < best:
                best = ev["loss"]
                state = {k: v for k, v in enc.state_dict().items() if not k.startswith("embed.")}
                torch.save({"config": {**config, "step": step, "heldout_loss": best}, "state": state}, out / "encoder.pt")
        if last:
            break


if __name__ == "__main__":
    main()
