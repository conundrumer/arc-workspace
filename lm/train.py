"""Fine-tune a pretrained decoder on the exported gold streams.

The model reads every step of a stream and is trained on the steps the model
emits. Vocabulary tokens get new embeddings, initialized from the base model's
embeddings of their names. Each declaration of a relation or a label takes a
random identifier, drawn fresh for each example, and each read of it takes the
same identifier. A read is predicted in two parts: the class REF_rel or
REF_label, then a pointer distribution over the declarations of that kind made
so far, whose logits are the dot products of a query from the current hidden
state with a key from the hidden state at each declaration.

The loss counts the choices the solver's decode makes. At each model-written
step the engine's mask admits some tokens. The class distribution is a
log-softmax over the out tokens the mask admits, REF_<kind> being admitted where
the mask admits an identifier of that kind that the stream has declared. The
pointer distribution is a log-softmax over the declarations of that kind whose
identifier the mask admits and that are the latest declaration of it. A step
whose admitted out tokens other than REF_*, plus the admitted declarations of
each admitted REF_<kind>, number one is no choice: it adds nothing to the loss,
the count or the stats.

With `--tables <dir>`, the feature encoder (encoder.py) reads the relation tables of each case from that tables
export, and each table's K vectors enter the sequence right after the token whose step gives the table (the
evidence tables right after the start token). They take no target and no identifier, and count in the attention
mask. An entry the encoder cannot see (undefined, a fault, no rows, or more rows than `--enc-budget`) enters as
one marker row; a table it cannot see (it faults, its projection search stopped, or every entry is unseen) enters
with no rows, as an unseen table. `--encoder-init` loads an encoder that pretrain.py trained on the masked table
loss, and `--aux-masked <weight>` adds that loss, over the tables of each batch's programs, to the training loss.

A run with the encoder and one without it see the same targets and the same batches in the same order, for the
same seed: `--max-len` bounds the steps alone, a sequence whose vectors would take it past twice `--max-len` drops
its latest tables, the batches are grouped by steps alone, and a group whose vectors take it past the budget is
split, with the splits counted in the log. A case that the export lacks, or whose export cannot be read, is left
out of every set; `--enc-k 0` with `--tables` leaves out the same cases and builds no encoder, for the baseline.

    work/lm/.venv/bin/python -u lm/train.py --base Qwen/Qwen3-0.6B --minutes 5 --out lm/runs/smoke
"""
import argparse, json, math, random, re, time
T_START = time.time()
from pathlib import Path

import numpy as np

import torch
import torch.nn as nn
import torch.nn.functional as F
from transformers import AutoModelForCausalLM, AutoTokenizer

KINDS = ["rel", "label"]
KIND_OF = {"relation": "rel", "label": "label"}   # the engine's token kind, as KINDS names it


BOS = "<bos>"


def families(solvers):
    """The family of each task that has one, by the solvers' `@representative` headers: a sibling and its
    representative share the representative's id. A task with no family is its own."""
    fam = {}
    for path in sorted(Path(solvers).glob("*.dl")):
        for line in open(path):
            if not line.startswith("//"):
                break
            m = re.match(r"// @representative: (\w+)", line)
            if m:
                assert fam.get(m.group(1), m.group(1)) == m.group(1), f"{m.group(1)} is a representative and a sibling"
                fam[path.stem] = m.group(1); fam[m.group(1)] = m.group(1)
    assert fam, f"no @representative headers under {solvers}"
    return lambda task: fam.get(task, task)


def split(train, held, family, n_indist, seed):
    """Three disjoint sets of cases by task: training, in-distribution held-out (n_indist tasks drawn at random
    from the training tasks, whole families together) and the evaluation tasks whose family has no training task."""
    rng = random.Random(seed)
    train_fams = sorted({family(c["task"]) for c in train})
    rng.shuffle(train_fams)
    indist_fams, n = set(), 0
    for f in train_fams:
        if n >= n_indist:
            break
        indist_fams.add(f); n += len({c["task"] for c in train if family(c["task"]) == f})
    indist = [c for c in train if family(c["task"]) in indist_fams]
    train = [c for c in train if family(c["task"]) not in indist_fams]
    kept_fams = {family(c["task"]) for c in train} | indist_fams
    dropped = sorted({c["task"] for c in held if family(c["task"]) in kept_fams})
    held = [c for c in held if c["task"] not in dropped]
    tasks = lambda cs: {c["task"] for c in cs}
    assert not (tasks(train) & tasks(indist)) and not (tasks(train) & tasks(held)) and not (tasks(indist) & tasks(held))
    assert not ({family(t) for t in tasks(indist)} & {family(t) for t in tasks(train)})
    assert train and indist and held, "empty split"
    return train, indist, held, dropped


CLASS_OF_KIND = {"control": "structure", "lib relation": "lib relation", "relation macro": "lib relation",
                 "component": "component", "proposer": "proposer", "fact relation": "fact", "column": "column"}


def token_classes(names, kinds):
    """The class of each vocabulary name, from the engine's kind of the token. The tokens of kind
    relation and label have no class."""
    classes = {n: CLASS_OF_KIND[k] for n, k in zip(names, kinds) if k in CLASS_OF_KIND}
    classes.update({"REF_rel": "read:rel", "REF_label": "read:label"})
    return classes


class Case(dict):
    """A case of the export: "task", "concept", "masks" (the row of the mask table for each model-written
    step, in order), and "steps" in the form encode reads, built on first use.

    A step is ["tok", name, who], ["eng", name, who], ["decl", kind, id, who] or ["ref", kind, i, id, who],
    where id is the token id of the identifier and a read refers to the latest declaration of the same
    name, i its index among all declarations.
    """
    def __missing__(self, key):
        assert key == "steps"
        names, kind, ids, model = self.pop("src")
        steps, n_decl, latest = [], 0, {}
        for i, w in zip(ids.tolist(), model.tolist()):
            who = "model" if w else "engine"
            if kind[i] and not w:
                latest[i] = n_decl; n_decl += 1
                steps.append(["decl", kind[i], i, who])
            elif kind[i]:
                steps.append(["ref", kind[i], latest[i], i, who])
            else:
                steps.append(["tok" if w else "eng", names[i], who])
        self["steps"] = steps
        return steps


def load(data):
    """The training and held-out cases of the export, the vocabulary's token names and kinds, and the mask table."""
    vocab = json.load(open(f"{data}/vocab.json"))
    names, kinds = vocab["names"], vocab["kinds"]
    kind = [KIND_OF.get(k) for k in kinds]
    z = np.load(f"{data}/cases.npz")
    ids, model, off = z["ids"], z["model"], z["offsets"]
    mask_index = z["mask_index"]
    first = np.concatenate([[0], np.cumsum(model)])[off]   # the first model-written step of each case
    train, held = [], []
    for c, (task, concept, h) in enumerate(zip(z["task"].tolist(), z["concept"].tolist(), z["heldout"].tolist())):
        case = Case(task=task, case=str(z["case"][c]), concept=concept, masks=mask_index[first[c]:first[c + 1]],
                    src=(names, kind, ids[off[c]:off[c + 1]], model[off[c]:off[c + 1]]))
        (held if h else train).append(case)
    return train, held, names, kinds, z["mask_table"]


class Masks:
    """The engine's masks over the vocabulary, as the out classes and the identifiers they admit.

    `admitted(row)` gives, for a row of the mask table, the out indices of the admitted tokens that are
    neither relations nor labels, and the admitted identifiers of each kind.
    """
    def __init__(self, table, names, kinds, out_index):
        self.table, self.n = table, len(names)
        self.out = np.array([out_index.get(n, -1) if k not in KIND_OF else -1 for n, k in zip(names, kinds)])
        self.kind = [KIND_OF.get(k) for k in kinds]
        self.cache = {}

    def admitted(self, row):
        if row not in self.cache:
            ids = np.flatnonzero(np.unpackbits(self.table[row], bitorder="little")[:self.n])
            outs = self.out[ids]
            self.cache[row] = (outs[outs >= 0], {k: [i for i in ids.tolist() if self.kind[i] == k] for k in KINDS})
        return self.cache[row]


class Target:
    """A choice of the decode: the output position that predicts it, its class, and for a read its kind and
    its index among the declarations of that kind; `outs` are the admitted out classes and `cands` the
    admitted declarations of each kind, by index among the declarations of that kind."""
    def __init__(self, pos, cls, kind, ptr, outs, cands):
        self.pos, self.cls, self.kind, self.ptr, self.outs, self.cands = pos, cls, kind, ptr, outs, cands


def by_task(cases):
    """The cases of each task."""
    tasks = {}
    for c in cases:
        tasks.setdefault(c["task"], []).append(c)
    return list(tasks.values())


def name_vector(table, tokenizer, name):
    """The initial embedding of a vocabulary name: the mean of the base model's embeddings of its text."""
    text = {"DECL_rel": "declare relation", "DECL_label": "declare variable",
            "REF_rel": "relation", "REF_label": "variable", BOS: "program"}.get(name, name)
    ids = tokenizer(text, add_special_tokens=False)["input_ids"]
    return table[ids].float().mean(0)


def vocabularies(names, kinds):
    """The input and output names of the language model, and their indices."""
    names_in = {n for n, k in zip(names, kinds) if k not in ("relation", "label")}
    in_names = sorted(names_in) + [BOS] + [f"{p}_{k}" for p in ("DECL", "REF") for k in KINDS]
    out_names = sorted(names_in) + [f"REF_{k}" for k in KINDS]
    return in_names, out_names, {n: i for i, n in enumerate(in_names)}, {n: i for i, n in enumerate(out_names)}


class Model(nn.Module):
    def __init__(self, base, tokenizer, in_names, out_names, id_dim):
        super().__init__()
        self.base = base.model  # the decoder stack, without its embedding lookup and head
        self.base.embed_tokens.requires_grad_(False)  # unused: inputs come from self.embed
        hidden = base.config.hidden_size
        table = base.get_input_embeddings().weight.detach()

        name_vec = lambda name: name_vector(table, tokenizer, name)
        self.embed = nn.Embedding(len(in_names), hidden)
        self.embed.weight.data = torch.stack([name_vec(n) for n in in_names]).to(self.embed.weight.dtype)
        self.head = nn.Linear(hidden, len(out_names), bias=False)
        self.head.weight.data = torch.stack([name_vec(n) for n in out_names]).to(self.head.weight.dtype)
        self.id_in = nn.Linear(id_dim, hidden, bias=False)
        self.query = nn.Linear(hidden, id_dim, bias=False)
        self.key = nn.Linear(hidden, id_dim, bias=False)
        self.id_dim = id_dim

    def forward(self, tokens, ids, mask, feats=None, feat_mask=None):
        x = self.embed(tokens) + self.id_in(ids)
        if feats is not None:   # the encoder's vectors, at the positions feat_mask marks
            x = torch.where(feat_mask[..., None], feats.to(x.dtype), x)
        h = self.base(inputs_embeds=x, attention_mask=mask).last_hidden_state
        return self.head(h), self.query(h), self.key(h)


def layout(prog, max_len, K):
    """The count of the program's steps kept, at most max_len - 1 after the start token, and its tables kept, in
    order: those whose step is kept, less the latest ones while the sequence would exceed 2 max_len."""
    m = min(len(prog["steps"]), max_len - 1)
    if not K:
        return m, []
    tables = [t for t in prog["tables"] if t.step <= m]   # in stream order, each after step index `step`
    n = max(0, min(len(tables), (2 * max_len - 1 - m) // K))
    return m, tables[:n]


def seq_len(prog, max_len, K):
    m, tables = layout(prog, max_len, K)
    return m + 1 + K * len(tables)


def relation_declaration(decls, step):
    """Of the declarations [(step, identifier)] of a table's relation, the one the table gives: the first after
    its step, since the engine declares a relation after the step that ends its clause, or else the latest at or
    before it. Gives the identifier and which rule chose it ("after", "before" or "none")."""
    after = [v for st, v in decls if st > step]
    if after:
        return after[0], "after"
    before = [v for st, v in decls if st <= step]
    return (before[-1], "before") if before else (None, "none")


def encode(prog, in_index, out_index, id_dim, max_len, masks, gen=None, K=0, rel_token=None):
    """Inputs, identifiers and targets of one program, truncated to max_len steps, after a start token.
    The targets are the steps at which the mask leaves more than one choice. With K, each kept table's K vectors
    follow its step; the extra item gives the tables, their vectors' positions, and the identifier of each
    table's relation, from its latest declaration at or before the table's step, or else its first after."""
    m, tables = layout(prog, max_len, K)
    steps = [["eng", BOS, "engine"]] + prog["steps"][:m]
    P = list(range(len(steps)))   # the position of each step in the sequence
    feat_pos = []
    if tables:
        after = np.bincount([t.step for t in tables], minlength=len(steps))
        P = (np.arange(len(steps)) + K * np.concatenate([[0], np.cumsum(after)[:-1]])).tolist()
        seen = {}
        for t in tables:
            k = seen.get(t.step, 0); seen[t.step] = k + 1
            feat_pos.append([P[t.step] + 1 + K * k + j for j in range(K)])
    n = len(steps) + K * len(tables)
    tokens = torch.zeros(n, dtype=torch.long)
    ids = torch.zeros(n, id_dim)
    decls_of = {}                        # for each relation token, (step, identifier) of each declaration
    decl_vecs = {k: [] for k in KINDS}   # identifier of each declaration, per kind
    decl_pos = {k: [] for k in KINDS}    # step index of each declaration, per kind
    order = []                           # for each declaration: (kind, index within kind)
    targets = []                         # the Targets
    latest = {}                          # for each identifier, the index among all declarations of its latest declaration
    n_model = 0
    for t, s in enumerate(steps):
        if s[0] == "decl":
            k = s[1]
            v = torch.randn(id_dim, generator=gen) / math.sqrt(id_dim)
            latest[s[2]] = len(order)
            order.append((k, len(decl_vecs[k])))
            decl_vecs[k].append(v); decl_pos[k].append(P[t])
            tokens[P[t]] = in_index["DECL_" + k]; ids[P[t]] = v
            if tables:
                decls_of.setdefault(s[2], []).append((t, v))
        elif s[0] == "ref":
            k, j = order[s[2]]
            tokens[P[t]] = in_index["REF_" + k]; ids[P[t]] = decl_vecs[k][j]
        else:
            tokens[P[t]] = in_index[s[1]]
        if s[-1] == "model":
            outs, admitted = masks.admitted(prog["masks"][n_model]); n_model += 1
            cands = {k: np.array(sorted({order[latest[i]][1] for i in admitted[k] if i in latest}), dtype=np.int64) for k in KINDS}
            outs = np.concatenate([outs, [out_index["REF_" + k] for k in KINDS if len(cands[k])]]).astype(np.int64)
            if s[0] == "ref":
                k, j = order[s[2]]
                target = Target(P[t] - 1, out_index["REF_" + k], k, j, outs, cands)
                assert j in cands[k], f"the mask does not admit the read at step {t} of {prog['task']}"
            else:
                target = Target(P[t] - 1, out_index[s[1]], None, None, outs, cands)
            assert target.cls in outs, f"the mask does not admit the token at step {t} of {prog['task']}"
            reads = [k for k in KINDS if len(cands[k])]   # the kinds whose REF class is admitted
            if len(outs) - len(reads) + sum(len(cands[k]) for k in reads) > 1:   # the options: out tokens other than REF_*, and declarations
                targets.append(target)
    assert n_model == len(prog["masks"]) or len(steps) - 1 < len(prog["steps"]), f"{prog['task']}: masks and model-written steps differ"
    rel, rules = [], []
    for t in tables:
        if isinstance(t.relation, str):   # an evidence table: its fact relation's token
            rel.append(None); rules.append("fact"); continue
        v, rule = relation_declaration(decls_of.get(rel_token.get(t.relation), []), t.step)
        rel.append(v); rules.append(rule)
    return tokens, ids, targets, decl_pos, n, (tables, feat_pos, rel, rules)


def table_relations(prog, id_dim, max_len, gen, K, rel_token):
    """The tables and the relation identifiers of the last item of `encode`, drawn from gen as encode draws them,
    one per declaration in step order, without building the sequence."""
    m, tables = layout(prog, max_len, K)
    decls_of = {}
    for t, s in enumerate(prog["steps"][:m], start=1):   # step t of the sequence, after the start token
        if s[0] == "decl":
            v = torch.randn(id_dim, generator=gen) / math.sqrt(id_dim)
            decls_of.setdefault(s[2], []).append((t, v))
    rel = [None if isinstance(t.relation, str) else
           relation_declaration(decls_of.get(rel_token.get(t.relation), []), t.step)[0] for t in tables]
    return tables, rel


def batches(progs, budget, max_len, shuffle, K=0, counts=None):
    """Groups of programs whose padded steps fit the budget; a longer program alone. The groups and their order
    depend on the steps alone, so they are the same with and without the encoder. With K, a group whose padded
    sequence, vectors included, exceeds the budget is split in turn, and `counts` counts the groups and the
    splits."""
    length = lambda i: seq_len(progs[i], max_len, 0)
    order = sorted(range(len(progs)), key=length)
    groups, cur, longest = [], [], 0
    for i in order:
        longest2 = max(longest, length(i))
        if cur and longest2 * (len(cur) + 1) > budget:
            groups.append(cur); cur, longest2 = [], length(i)
        cur.append(i); longest = longest2
    if cur:
        groups.append(cur)
    if shuffle:
        random.shuffle(groups)
    if K:
        full = lambda i: seq_len(progs[i], max_len, K)
        split = []
        for g in groups:
            cur = []
            for i in g:
                if cur and max(map(full, cur + [i])) * (len(cur) + 1) > budget:
                    split.append(cur); cur = []
                cur.append(i)
            split.append(cur)
        if counts is not None:
            counts["groups"] = counts.get("groups", 0) + len(groups)
            counts["splits"] = counts.get("splits", 0) + len(split) - len(groups)
        groups = split
    return groups


def grad_norm(params):
    """The global 2-norm of the gradients, by the formula of torch.nn.utils.clip_grad_norm_: the 2-norm of the
    per-tensor 2-norms."""
    norms = [torch.linalg.vector_norm(p.grad.detach().float()) for p in params if p.grad is not None]
    return torch.linalg.vector_norm(torch.stack(norms)).item() if norms else 0.0


def run_batch(model, progs, group, enc_args, device, stats=None, gen=None, K=0, enc_gen=None, aux=None):
    """The mean loss of a group of programs, and the count of its targets. `gen` draws the identifiers of the
    language model, and `enc_gen` the encoder's (by default the model's own generator), so that the language
    model's draws are the same with and without the encoder. With `aux`, a dict of "weight", "frac", "cap", "kind",
    "prior_weight" and "step" (masked_loss's arguments), the loss adds weight times the masked table loss over the
    tables of the group's programs, from a second encoder pass whose masks and identifiers come from
    model.mask_gen, and aux gains "loss", the masked loss, and "program" and "prior", the mean loss of each part.
    aux gains "lm", the language model loss alone, as a tensor. Where aux has "measure" set, aux gains
    "norm_masked", the global gradient norm right after the masked loss's backward. Where aux has "clip" set, the
    gradients scale after that backward so that their global norm is at most "clip" (the formula of
    torch.nn.utils.clip_grad_norm_), and where "measure" is set and the scaling applied, aux gains
    "norm_masked_clipped", the norm after the scaling.
    Where gradients are on, that pass runs first and its backward runs at once, so that its graph is freed before
    the clean pass builds its own: the gradients add to those of the returned loss's backward, so the caller zeroes
    the gradients before the call."""
    encs = [encode(progs[i], *enc_args, gen=gen, K=K, rel_token=getattr(model, "rel_token", None)) for i in group]
    L = max(e[4] for e in encs)
    B = len(encs)
    tokens = torch.zeros(B, L, dtype=torch.long)
    ids = torch.zeros(B, L, encs[0][1].shape[1])
    mask = torch.zeros(B, L, dtype=torch.long)
    for b, (tk, idv, _, _, n, _) in enumerate(encs):
        tokens[b, :n], ids[b, :n], mask[b, :n] = tk, idv, 1
    dtype = next(model.parameters()).dtype
    feats = feat_mask = masked = None
    if aux is not None and aux["weight"]:
        masked, records = model.encoder.masked_loss([(e[5][0], e[5][2]) for e in encs], model.mask_gen, aux["frac"],
                                                    aux["cap"], model.mask_gen, backward=aux["weight"], kind=aux["kind"],
                                                    step=aux["step"], prior_weight=aux["prior_weight"])
        aux["loss"] = masked.item()
        if aux.get("measure"):
            aux["norm_masked"] = grad_norm(model.parameters())
        if aux.get("clip"):
            before = torch.nn.utils.clip_grad_norm_(model.parameters(), aux["clip"])
            if aux.get("measure") and before.item() > aux["clip"]:
                aux["norm_masked_clipped"] = grad_norm(model.parameters())
        for part in ("program", "prior"):
            ls = [r["loss"] for _, _, r in records if r["part"] == part]
            aux[part] = torch.cat(ls).mean().item() if ls else 0.0
    if K:
        out = model.encoder([(e[5][0], e[5][2]) for e in encs], enc_gen or model.enc_gen)
        feats = torch.zeros(B, L, model.embed.weight.shape[1], device=device)
        feat_mask = torch.zeros(B, L, dtype=torch.bool, device=device)
        for b, (e, f) in enumerate(zip(encs, out)):
            if f is not None:
                pos = torch.tensor(e[5][1], device=device)          # [tables, K]
                feats[b, pos] = f.to(feats.dtype); feat_mask[b, pos] = True
    logits, query, key = model(tokens.to(device), ids.to(device, dtype), mask.to(device), feats, feat_mask)
    total, count = logits.sum() * 0.0, 0
    for b, (_, _, targets, decl_pos, n, _) in enumerate(encs):
        if not targets:
            continue
        pos = torch.tensor([t.pos for t in targets], device=device)
        cls = torch.tensor([t.cls for t in targets], device=device)
        admitted = np.zeros((len(targets), logits.shape[-1]), bool)
        for r, t in enumerate(targets):
            admitted[r, t.outs] = True
        lp = F.log_softmax(logits[b, pos].float().masked_fill(~torch.from_numpy(admitted).to(device), float("-inf")), -1)
        nll = -lp.gather(1, cls[:, None])[:, 0]
        for k in KINDS:
            rows = [r for r, t in enumerate(targets) if t.kind == k]
            if not rows:
                continue
            keys = key[b, torch.tensor(decl_pos[k], device=device)].float()
            rows_t = torch.tensor(rows, device=device)
            j = torch.tensor([targets[r].ptr for r in rows], device=device)
            candidate = np.zeros((len(rows), keys.shape[0]), bool)
            for i, r in enumerate(rows):
                candidate[i, targets[r].cands[k]] = True
            pl = query[b, pos[rows_t]].float() @ keys.T / math.sqrt(keys.shape[1])  # logits over every declaration of kind k
            pl = pl.masked_fill(~torch.from_numpy(candidate).to(device), float("-inf"))
            pl = F.log_softmax(pl.float(), -1)
            nll = nll.index_add(0, rows_t, -pl.gather(1, j[:, None])[:, 0])
            if stats is not None:
                stats["ptr_n"] += len(rows); stats["ptr_correct"] += int((pl.argmax(1) == j).sum().item())
        total = total + nll.sum(); count += len(targets)
        if stats is not None:
            for t, v in zip(targets, nll.tolist()):
                tc = stats["classes"][stats["out_names"][t.cls]]
                stats["cls"].setdefault(tc, [0.0, 0]); stats["cls"][tc][0] += v; stats["cls"][tc][1] += 1
                bin_ = "len<200" if n < 200 else "len<600" if n < 600 else "len>=600"
                stats["len"].setdefault(bin_, [0.0, 0]); stats["len"][bin_][0] += v; stats["len"][bin_][1] += 1
    loss = total / max(count, 1)
    if aux is not None:
        aux["lm"] = loss.detach()
    if masked is not None:
        loss = loss + aux["weight"] * masked
    return loss, count


def evaluate(model, progs, enc_args, device, budget, out_names, classes, autocast, K=0):
    stats = {"cls": {}, "len": {}, "ptr_n": 0, "ptr_correct": 0, "out_names": out_names, "classes": classes}
    model.eval()
    tot, cnt = 0.0, 0
    gen = torch.Generator().manual_seed(1)  # the same identifiers at every evaluation
    enc_gen = torch.Generator().manual_seed(2)
    with torch.no_grad(), autocast():
        for g in batches(progs, budget, enc_args[3], False, K):
            loss, c = run_batch(model, progs, g, enc_args, device, stats, gen, K, enc_gen)
            tot += loss.item() * c; cnt += c
    model.train()
    return {"loss": tot / max(cnt, 1),
            "by_class": {k: v[0] / v[1] for k, v in sorted(stats["cls"].items())},
            "by_length": {k: v[0] / v[1] for k, v in sorted(stats["len"].items())},
            "pointer_accuracy": stats["ptr_correct"] / max(1, stats["ptr_n"])}


MPS_PEAK = [0.0]


def device_memory(device):
    """Peak memory the device has given this process, in GB. On mps, the driver gives the current amount alone, so
    the peak is the most of every call; call it after each step."""
    if device == "cuda":
        return torch.cuda.max_memory_allocated() / 1e9
    if device == "mps":
        MPS_PEAK[0] = max(MPS_PEAK[0], torch.mps.driver_allocated_memory() / 1e9)
        return MPS_PEAK[0]
    return 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="Qwen/Qwen3-0.6B")
    ap.add_argument("--data", default="work/lm/data")
    ap.add_argument("--out", required=True)
    ap.add_argument("--minutes", type=float, required=True)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--budget", type=int, default=4096, help="padded steps per batch")
    ap.add_argument("--max-len", type=int, default=4096)
    ap.add_argument("--warmup", type=int, default=20, help="steps of linear warmup")
    ap.add_argument("--train-limit", type=int, default=0, help="train on the first n tasks only")
    ap.add_argument("--concept-only", action="store_true", help="train on each task's concept case only")
    ap.add_argument("--eval-train", action="store_true", help="evaluate on the training programs (overfit check)")
    ap.add_argument("--eval-limit", type=int, default=0, help="evaluate on the first n held-out programs only")
    ap.add_argument("--indist", type=int, default=80, help="training tasks held out as the in-distribution split")
    ap.add_argument("--solvers", default="programs/solvers", help="the solvers, for their family headers")
    ap.add_argument("--max-steps", type=int, default=0, help="stop after n steps")
    ap.add_argument("--pure-bf16", action="store_true", help="keep the weights and optimizer state in bf16 (no fp32 copy)")
    ap.add_argument("--grad-ckpt", action="store_true", help="recompute activations in the backward pass to save memory")
    ap.add_argument("--id-dim", type=int, default=64)
    ap.add_argument("--eval-every", type=float, default=2.0, help="minutes")
    ap.add_argument("--tables", help="a tables export (engine/arclog-py/tables_export.py): train with the feature encoder on it")
    ap.add_argument("--enc-k", type=int, default=4, help="the encoder's vectors per table")
    ap.add_argument("--enc-layers", type=int, default=2)
    ap.add_argument("--enc-width", type=int, default=32, help="the encoder's channels c per position")
    ap.add_argument("--enc-heads", type=int, default=4)
    ap.add_argument("--enc-mlp", type=int, default=2, help="the encoder's feed-forward width, in multiples of --enc-width")
    ap.add_argument("--enc-gram", type=int, default=16, help="the channels each Gram matrix of the crossing projects to")
    ap.add_argument("--enc-budget", type=int, default=10000,
                    help="the encoder's context length: the most rows of one entry (an example at an assignment), or of "
                         "one projection at an entry; a table over it is unseen, and each is listed at load")
    ap.add_argument("--enc-max-rows", type=int, default=4000,
                    help="a guard on device memory: a table of more rows than this, summed over its entries, is unseen")
    ap.add_argument("--enc-group", type=int, default=0,
                    help="the programs of a batch that each encoder call takes, 0 for all")
    ap.add_argument("--enc-equality", choices=["codes", "random", "flex"], default="codes",
                    help="the means of the encoder's equality term: one-hot codes added to the attention's queries and "
                         "keys, random sign codes of fixed width, or flex_attention (cuda alone)")
    ap.add_argument("--enc-checkpoint", action=argparse.BooleanOptionalAction, default=None,
                    help="recompute the encoder's Block activations in the backward pass to save memory (default: on "
                         "with cuda, off otherwise); without it, each table keeps its evidence rows' keys and values "
                         "at every layer for the backward pass, which does not fit a step of full-data programs")
    ap.add_argument("--encoder-init", help="an encoder state that pretrain.py saved, loaded before the fine-tune")
    ap.add_argument("--aux-masked", type=float, default=0.0, help="the weight of the masked table loss beside the LM loss")
    ap.add_argument("--aux-clip", type=float, default=1.0,
                    help="the most the global gradient norm of the masked table loss may be, scaled down to it before "
                         "the LM loss's backward adds its gradient; the clip at 1.0 over the sum still follows")
    ap.add_argument("--mask-frac", type=float, default=0.15, help="the fraction of fields the masked loss hides per table")
    ap.add_argument("--mask-cap", type=int, default=512, help="the most fields the masked loss hides per table")
    ap.add_argument("--preflight", action=argparse.BooleanOptionalAction, default=True,
                    help="before the model loads, run the masked loss's data path on every program with no model "
                         "(encoder.preflight), which stops the run at the first program it cannot mask")
    ap.add_argument("--mask-kind", choices=["alternate", "program", "output", "prior"], default="alternate",
                    help="the masked loss's step kind of each program: a program step hides computed fields, an "
                         "output step the computed fields of ex_output alone, a prior step inferrable fields, and "
                         "alternate takes the three by turns, by the step and the program's place in the batch")
    ap.add_argument("--prior-weight", type=float, default=1.0,
                    help="the weight of the prior part of the masked loss beside its program part")
    ap.add_argument("--tiny-base", action="store_true",
                    help="a 2-layer, 64-wide model of --base's architecture and tokenizer, initialized at random, for the regression check")
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu")
    a = ap.parse_args()
    if a.enc_checkpoint is None:
        a.enc_checkpoint = a.device == "cuda"
    torch.manual_seed(0); random.seed(0)

    t0 = time.time()
    stage = lambda what: print(f"[{time.time() - T_START:.0f}s] {what}", flush=True)
    stage(f"imported; torch threads {torch.get_num_threads()}")
    train, held, names, kinds, mask_table = load(a.data)
    stage("data loaded")
    # train: each epoch draws one case per task; held-out: each task's concept case, on the in-distribution
    # split (which selects the checkpoint) and on the evaluation tasks
    if a.concept_only:
        train = [c for c in train if c["concept"]]
    train, indist, held, dropped = split(train, held, families(a.solvers), a.indist, seed=0)
    print(f"evaluation tasks dropped as family siblings of training tasks: {dropped}")
    train_tasks = by_task(train)
    indist = [c for c in indist if c["concept"]]
    held = [c for c in held if c["concept"]]
    if a.train_limit:
        train_tasks = train_tasks[:a.train_limit]
    # --eval-train: the training programs are a third evaluation set, logged under "train"
    eval_train = [cs[0] for cs in train_tasks] if a.eval_train else []
    K = a.enc_k if a.tables else 0
    assert a.max_len >= 1 + 2 * K, "--max-len must be at least 1 + 2 K"
    assert not K or a.enc_equality != "flex" or a.device == "cuda", "--enc-equality flex trains on cuda alone"
    if a.tables:   # each case takes its tables; a case without readable tables leaves every set
        import encoder
        tables, skipped, tstats = encoder.load_tables(a.tables, f"{a.data}/tables.pkl")
        if skipped:
            print(f"DATA FAULT: {len(skipped)} cases whose tables export cannot be read, left out: {skipped}")
        over = encoder.mark_over_budget(tables, a.enc_budget)
        for t, c, x, r, e, n in over:
            print(f"unseen entry, over --enc-budget {a.enc_budget}: {t} {c} table {x} relation {r} entry {e}: {n} rows")
        for t, c, x, r, n in encoder.mark_over_rows(tables, a.enc_max_rows):
            print(f"unseen table, over --enc-max-rows {a.enc_max_rows}: {t} {c} table {x} relation {r}: {n} rows")
        unseen_t, unseen_e = encoder.unseen_counts(tables)
        tstats = {**tstats, "unseen tables": unseen_t, "unseen entries": unseen_e,
                  "tables": sum(map(len, tables.values()))}
        before = sum(map(len, train_tasks)) + len(indist) + len(held)
        keep = lambda cs: [c for c in cs if (c["task"], c["case"]) in tables]
        train_tasks = [cs for cs in map(keep, train_tasks) if cs]
        indist, held = keep(indist), keep(held)
        for c in [c for cs in train_tasks for c in cs] + indist + held:
            c["tables"] = tables[(c["task"], c["case"])]
        eval_train = [cs[0] for cs in train_tasks] if a.eval_train else []
        print(f"tables: {before - sum(map(len, train_tasks)) - len(indist) - len(held)} of {before} cases left out "
              f"(not in the export, or a data fault); {tstats}")
        if a.preflight:
            t_pre = time.time()
            encoder.preflight([((c["task"], c["case"]), c["tables"]) for c in [c for cs in train_tasks for c in cs]
                               + indist + held], a.mask_frac, a.mask_cap)
            print(f"preflight: {sum(map(len, train_tasks)) + len(indist) + len(held)} programs, "
                  f"{time.time() - t_pre:.0f} s", flush=True)
    if a.eval_limit:
        indist, held, eval_train = indist[:a.eval_limit], held[:a.eval_limit], eval_train[:a.eval_limit]
    assert train_tasks and indist and held, "empty split"
    classes = token_classes(names, kinds)
    in_names, out_names, in_index, out_index = vocabularies(names, kinds)

    tok = AutoTokenizer.from_pretrained(a.base)
    stage("tokenizer loaded")
    # fp32 weights and optimizer state; the forward pass runs under bf16 autocast on CUDA
    dtype = torch.bfloat16 if a.pure_bf16 else torch.float32
    use_autocast = a.device == "cuda" and not a.pure_bf16
    autocast = lambda: torch.autocast("cuda", dtype=torch.bfloat16, enabled=use_autocast)
    if a.tiny_base:
        from transformers import AutoConfig
        cfg = AutoConfig.from_pretrained(a.base, num_hidden_layers=2, hidden_size=64, intermediate_size=128,
                                         num_attention_heads=4, num_key_value_heads=2, head_dim=16)
        base = AutoModelForCausalLM.from_config(cfg, dtype=dtype)
    else:
        base = AutoModelForCausalLM.from_pretrained(a.base, dtype=dtype)
    stage("base model loaded")
    if a.grad_ckpt:
        base.gradient_checkpointing_enable()
    model = Model(base, tok, in_names, out_names, a.id_dim).to(a.device, dtype)
    del base
    if K:
        model.encoder = encoder.FeatureEncoder(model.embed, in_index, a.id_dim, json.load(open(f"{a.tables}/orientations.json")),
                                               K=K, layers=a.enc_layers, c=a.enc_width, heads=a.enc_heads, mlp=a.enc_mlp, gram=a.enc_gram,
                                               examples=encoder.max_example(tables) + 1, equality=a.enc_equality).to(a.device, dtype)
        model.enc_gen = torch.Generator().manual_seed(0)   # the encoder's identifiers, apart from the model's
        model.encoder.checkpoint = a.enc_checkpoint
        model.encoder.group = a.enc_group
        model.rel_token = {int(n[2:]): i for i, n in enumerate(names) if re.fullmatch(r"&r\d+", n)}
        print(f"encoder: {sum(p.numel() for p in model.encoder.parameters() if p is not model.embed.weight) / 1e6:.2f}M parameters")
        if a.encoder_init:
            init = torch.load(a.encoder_init, map_location=a.device)
            mine = dict(enc_k=K, enc_layers=a.enc_layers, enc_width=a.enc_width, enc_heads=a.enc_heads, enc_mlp=a.enc_mlp,
                        enc_gram=a.enc_gram, in_names=in_names)
            assert all(init["config"][k] == v for k, v in mine.items()), f"--encoder-init {a.encoder_init}: another encoder shape"
            missing, unexpected = model.encoder.load_state_dict(init["state"], strict=False)
            assert not unexpected and all(k.startswith("embed.") for k in missing), (missing, unexpected)
            print(f"encoder loaded from {a.encoder_init} (pretrained {init['config'].get('step')} steps)")
        if a.aux_masked:
            model.mask_gen = torch.Generator().manual_seed(3)   # the masked loss's masks and identifiers
    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=a.lr, weight_decay=0.0)
    sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda i: min(1.0, (i + 1) / a.warmup))
    enc_args = (in_index, out_index, a.id_dim, a.max_len, Masks(mask_table, names, kinds, out_index))

    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    log = open(out / "log.jsonl", "a")
    print(f"{len(train_tasks)} train tasks ({sum(map(len, train_tasks))} cases), {len(indist)} in-distribution held-out, "
          f"{len(held)} evaluation held-out; vocab in {len(in_names)}, out {len(out_names)}; "
          f"{sum(p.numel() for p in model.parameters()) / 1e6:.0f}M parameters on {a.device}")

    # --minutes bounds the whole process, loading included, so the final evaluation lands inside it
    best = float("inf")
    meta = {"base": a.base, "pure_bf16": a.pure_bf16, "in_names": in_names, "out_names": out_names, "id_dim": a.id_dim}
    if a.tables:
        meta.update(tables=a.tables, enc_k=K, enc_layers=a.enc_layers, enc_width=a.enc_width, enc_heads=a.enc_heads,
                    enc_mlp=a.enc_mlp, enc_gram=a.enc_gram, enc_budget=a.enc_budget, enc_max_rows=a.enc_max_rows,
                    enc_equality=a.enc_equality)
        if a.encoder_init or a.aux_masked:
            meta.update(encoder_init=a.encoder_init, aux_masked=a.aux_masked, mask_frac=a.mask_frac, mask_cap=a.mask_cap,
                        mask_kind=a.mask_kind, prior_weight=a.prior_weight)
    split_counts = {}
    if K:   # how each table's relation finds its declaration, and how many sequences drop tables at 2 max_len
        rules, dropped, cases = {}, 0, [c for cs in train_tasks for c in cs] + indist + held
        g0 = torch.Generator().manual_seed(0)
        for c in cases:
            r = encode(c, *enc_args, gen=g0, K=K, rel_token=model.rel_token)[5][3]
            for x in r:
                rules[x] = rules.get(x, 0) + 1
            m = min(len(c["steps"]), a.max_len - 1)
            dropped += len(layout(c, a.max_len, K)[1]) < sum(t.step <= m for t in c["tables"])
        print(f"tables by the rule that found their relation's declaration: {rules}; "
              f"{dropped} of {len(cases)} cases drop tables past 2 max-len")
    start, last_eval, step, epoch = time.time(), time.time(), 0, 0
    print(f"loaded in {start - t0:.0f}s", flush=True)
    deadline = t0 + a.minutes * 60 - 60
    done = False
    while not done:
        epoch += 1
        train = [random.choice(cs) for cs in train_tasks]
        for g in batches(train, a.budget, a.max_len, True, K, split_counts):
            logged = step + 1 <= 3 or (step + 1) % 10 == 0
            aux = (dict(weight=a.aux_masked, frac=a.mask_frac, cap=a.mask_cap, kind=a.mask_kind,
                        prior_weight=a.prior_weight, step=step, measure=logged, clip=a.aux_clip) if K and a.aux_masked else None)
            opt.zero_grad()
            with autocast():
                loss, _ = run_batch(model, train, g, enc_args, a.device, K=K, aux=aux)
            loss.backward()
            parts = {}
            if aux:
                parts = {"lm_loss": aux["lm"].item(), "masked_loss": aux["loss"]}
                if logged:
                    parts["grad_norm_masked"] = aux["norm_masked"]
                    parts["grad_norm_total"] = grad_norm(model.parameters())
                    if "norm_masked_clipped" in aux:
                        parts["grad_norm_masked_clipped"] = aux["norm_masked_clipped"]
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step(); sched.step(); step += 1
            device_memory(a.device)
            if logged:
                masked = (f" (lm loss {parts['lm_loss']:.3f}, masked table loss {aux['loss']:.3f}: program "
                          f"{aux['program']:.3f}, prior {aux['prior']:.3f}) grad norm masked "
                          f"{parts['grad_norm_masked']:.3f}, total {parts['grad_norm_total']:.3f}" if aux else "")
                if "grad_norm_masked_clipped" in parts:
                    masked += f", masked clipped {parts['grad_norm_masked_clipped']:.3f}"
                print(f"step {step} epoch {epoch} train loss {loss.item():.3f}{masked} {time.time() - start:.0f}s", flush=True)
            if a.max_steps and step >= a.max_steps:
                deadline = 0
            if time.time() - last_eval > a.eval_every * 60 or time.time() > deadline:
                ev_in = evaluate(model, indist, enc_args, a.device, a.budget, out_names, classes, autocast, K)
                ev = evaluate(model, held, enc_args, a.device, a.budget, out_names, classes, autocast, K)
                stage("evaluated")
                row = {"step": step, "epoch": epoch, "seconds": round(time.time() - start), "train_loss": loss.item(),
                       **parts, "device_gb": round(device_memory(a.device), 2), "indist": ev_in, "heldout": ev}
                if K:
                    row["batch_splits"] = dict(split_counts)
                if eval_train:
                    row["train"] = evaluate(model, eval_train, enc_args, a.device, a.budget, out_names, classes, autocast, K)
                log.write(json.dumps(row) + "\n"); log.flush()
                if ev_in["loss"] < best:  # keep the checkpoint of lowest in-distribution loss
                    best = ev_in["loss"]
                    torch.save(model.state_dict(), out / "model.pt")
                    stage("checkpoint saved")
                    json.dump({**meta, "step": step, "indist_loss": best, "heldout_loss": ev["loss"]}, open(out / "model.json", "w"))
                print(json.dumps(row), flush=True)
                last_eval = time.time()
            if time.time() > deadline:
                done = True
                break


if __name__ == "__main__":
    main()
