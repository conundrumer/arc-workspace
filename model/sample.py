"""Sample programs from a fine-tuned program LM under the engine's token mask.

For each task, the sampler writes `--n` programs token by token. At each step it reads the decoder's mask and
turns it into the head's choices as train.py's loss does: the class distribution is over the out tokens the mask
admits, REF_<kind> being admitted where the mask admits an identifier of that kind that the stream has declared,
and the pointer distribution is over the declarations of that kind whose identifier the mask admits and that are
the latest declaration of it. The sampler draws a class, and for REF_<kind> a declaration, from those
distributions at `--temperature` (or takes the argmax with `--greedy`), steps the decoder by the token's id, and
feeds the token and the ids the engine emits after it to the model. A program stops when the decode ends at an
`OUT` form that solves the train pairs, at `--max-steps` model-written tokens, at `--max-tokens` positions of context, at
`--max-seconds` of wall time for its task, where the mask admits no token ("empty-mask"), where it admits no token
the head can write ("stuck": only identifiers that the stream has not declared), or where the engine panics at its
token ("panic": `arclog.step_batch` gives an `arclog.Fault` in the place of that decoder). The `--max-seconds`
deadline counts from the task's start and covers the prefix replays; a program whose prefix replay has not
finished at it is dropped: it gets no line, and the summary counts it as "deadline".

A "panic" program keeps the token it panicked at in its stream; the other programs of the batch step as they would
without the panic. Each "panic" program also gets `<out dir>/panic-<task>-<index>.json`: task, ids, model, end,
panic, settings, world and its record, for a replay of the stream.

Two caps count model-written tokens. A clause is one top-level form of the program (a RULE, DET, INIT, CHOOSE,
RIGID_DET or OUT form): it opens at the form's keyword token, which the model writes, and it holds the model-written tokens
up to the next form keyword. `--max-clause <n>` ends a program ("max-clause") when its current clause holds more than n
model-written tokens, a prefix's tokens of that clause included. Without the flag, n is 1.5 times the most
model-written tokens that one clause of any case in `--data`'s cases.npz holds, computed at start and printed;
`--max-clause 0` turns the cap off. `--max-steps-factor <f>` (default 0, off) lowers a program's `--max-steps`
to f times the model-written tokens of its source case in prefix mode, and from nothing to f times the median
of those counts over the task's cases in `--data`; the task's line prints the cap. Both count the tokens that the
sampler writes after the prefix, as `--max-steps` does, except that `--max-clause` counts the prefix's tokens of
the clause the prefix ends in. `--max-cont-factor <f>` (default 0, off) ends a prefix-mode program ("max-cont") at
ceil(f x G) sampled tokens, G being the model-written tokens of its source case after the prefix; with no prefix it has no effect.

Each declaration takes a random identifier, as in training. The identifiers and the draws of each program come
from a generator seeded by `--seed`, the task and the program's index, so a program's draws do not depend on
`--batch`. With `--batch b`, b programs of one task step in lockstep: the decoders are forks of one decoder,
`arclog.step_batch` steps them, and one forward pass over a key-value cache reads the new tokens of all of them,
padded to the longest, with the pad positions masked from every later position.

With `--prefix`, each program starts from a prefix of a corpus program of its task: a case's stream as the data
export's cases.npz holds it (`--data`, `--prefix-cases`). The sampler steps the decoder through the prefix's
model-written tokens, asserts that each is admissible and that the engine emits the stream's next ids after it, and
samples the rest. The prefix ends at a token boundary, after a model-written token and the ids the engine emits
after it. `--prefix random` takes a rule boundary at random, uniformly: the end of a RULE clause, where the decode has
not ended; a case with none gives the empty prefix.
`--prefix random-token` takes any token boundary at which the decode has not ended, uniformly. `--prefix <f>`, a
number, takes the last such token boundary at or before the fraction f of the stream's tokens; 0, the default, is
the empty prefix.

`--rule-tests` sets the decode setting `rule_tests` of every session, so that the END of each RULE clause gives the
verdict of the test of its relation, which the lines' `rules` hold; without it `rules` is empty. The verdict ends no
program, and changes no mask.

`--out` gets, on its first line, {"settings": the fields of arclog.DecodeSettings that every session took (the
engine's defaults, and `rule_tests` as the flag gives it), "world", "args": the run's flags, "model_meta"}, so `arclog.DecodeSettings(**settings)` replays
the streams under the same settings. Then one JSON line per program:
  task               the task id
  case               the corpus case that gave the prefix, or null
  branch             the RULE ends in the prefix, which is the branch point's rule index; 0 without a prefix
  rollout            the program's index among the task's programs, or "gold" for the case's own stream, written
                     once for each branch point that a sampled program of the task took; the sampler does not
                     replay a gold line, so its ended, consistency, solved_test, attempts and program_form are null
  ids, model         the stream's token ids as the engine saw them, in order, the engine's emitted ids included,
                     and for each a 1 where the decoder was stepped by it and a 0 where step() emitted it
  prefix_tokens      the stream's first prefix_tokens ids are the prefix
  prefix_rules       the RULE ends in the prefix
  ended              whether the decode ended at an OUT form that solves the train pairs
  consistency        the consistency that the last step gave, which only the END of an OUT form gives, or null
  solved_test        for an ended decode, whether the attempts on every test input hold its test output; else null
  attempts           for an ended decode, the count of attempt grids over the test inputs; else null
  tokens             len(ids)
  program_form       program_form() of the decode where it stopped: the finished clauses, a whole program where
                     ended; null where the engine panics in program_form(), and the line then gets
                     program_form_panic, the panic's message, and keeps its end
  end               "ended", "max-steps", "max-clause", "max-cont", "max-tokens", "max-seconds", "empty-mask", "stuck",
                     "refused", "panic", or "gold" for the gold line
  panic              the engine's panic message for "panic"; else null
  max_steps_used     the program's cap on sampled tokens: `--max-steps` or its lower value under
                     `--max-steps-factor`
  max_cont_used      the program's cap on sampled tokens under `--max-cont-factor`; 0 for none
  max_clause_used    the program's cap on the model-written tokens of a clause; 0 for none
  rules              under `--rule-tests`, the verdict kind of the rule test at each sampled RULE clause's END, in
                     order; for a gold line, that of each RULE clause of the case's stream after the prefix, from
                     the one replay of the whole stream that finds the case's rule boundaries; empty without it
  model_steps        the sampled tokens
  refusals, seconds
The run's summary is printed as one JSON line at the end. The sampler does not run the feature encoder; a run
directory whose model.json gives `enc_k` above 0 is refused.

    work/lm/.venv/bin/python model/sample.py --model work/lm/runs/base-135m-a100 --tasks 007bbfb7 --n 3 \\
        --out model/runs/sample-check/samples.jsonl --device cpu
"""
import argparse, json, math, random, time
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F

import arclog
from rollout_labels import FORM_KEYWORDS
from train import BOS, KINDS, KIND_OF, Masks, Model, vocabularies
from transformers import AutoConfig, AutoModelForCausalLM, AutoTokenizer, DynamicCache

MAX_TOKENS = 4096   # train.py's default --max-len
MAX_STEPS = 10_000  # the export's step cap
SETTINGS = ("proposer_tokens", "type_domain_proposers", "relations", "columns", "labels", "mutation_node_cap",
            "projection_cap", "table_work_cap", "request_work_cap", "request_byte_cap", "assignment_byte_cap", "candidate_byte_cap", "spill_resident_bytes", "rule_tests")   # the fields of arclog.DecodeSettings


def load_model(run, device):
    """The Model of a run directory of train.py, its metadata, and its dtype."""
    meta = json.load(open(f"{run}/model.json"))
    assert not meta.get("enc_k"), f"{run}: a model with the feature encoder (enc_k {meta['enc_k']}); the sampler does not run it"
    dtype = torch.bfloat16 if meta.get("pure_bf16") else torch.float32
    tok = AutoTokenizer.from_pretrained(meta["base"])
    base = AutoModelForCausalLM.from_config(AutoConfig.from_pretrained(meta["base"]), dtype=dtype)
    model = Model(base, tok, meta["in_names"], meta["out_names"], meta["id_dim"])
    model.load_state_dict(torch.load(f"{run}/model.pt", map_location="cpu"))
    return model.to(device, dtype).eval(), meta, dtype


def forward(model, tokens, ids, attention, positions, cache):
    """Model.forward over new positions with a key-value cache: logits, queries and keys at the new positions."""
    x = model.embed(tokens) + model.id_in(ids)
    h = model.base(inputs_embeds=x, attention_mask=attention, position_ids=positions, past_key_values=cache,
                   use_cache=True).last_hidden_state
    return model.head(h), model.query(h), model.key(h)


def consistency_json(c):
    if c is None:
        return None
    return {"kind": kind_name(c), "assignments": c.assignments,
            "stop": None if c.stop is None else str(c.stop).split(".")[-1], "message": c.message}


class Program:
    """One program in progress: its decoder, its stream, its declarations, and the inputs not yet fed."""
    def __init__(self, task, index, decoder, seed, id_dim, in_index):
        self.task, self.index, self.decoder = task, index, decoder
        self.gen = torch.Generator().manual_seed(hash_seed(seed, task, index))
        self.id_dim, self.in_index = id_dim, in_index
        self.ids, self.model = [], []
        self.latest = {}                          # for each identifier, (kind, index within kind) of its latest declaration
        self.decl_ids = {k: [] for k in KINDS}    # the identifier of each declaration of each kind
        self.decl_vecs = {k: [] for k in KINDS}
        self.keys = {k: [] for k in KINDS}        # the key at each declaration's position
        self.pending = [(in_index[BOS], torch.zeros(id_dim), None)]   # (input index, identifier vector, kind of a declaration)
        self.fed = 0
        self.consistency, self.rules, self.end, self.steps, self.refusals = None, [], None, 0, 0
        self.opened = None                        # the keyword of the form in progress, as the model wrote it
        self.clause = 0                           # the model-written tokens of the current clause
        self.max_steps = self.max_clause = self.max_cont = 0
        self.logits = self.query = None
        self.prefix_case, self.prefix_tokens, self.prefix_rules = None, 0, 0
        self.panic = None                         # the message of an engine panic at the program's last step

    def push(self, i, by_model, names, kind):
        """Append the token with id i to the stream and to the inputs to feed."""
        self.ids.append(i); self.model.append(int(by_model))
        k = kind[i]
        if by_model:
            if names[i] in FORM_KEYWORDS:
                self.clause = 0
            self.clause += 1
        if k and not by_model:   # the engine declares a relation or a label
            v = torch.randn(self.id_dim, generator=self.gen) / math.sqrt(self.id_dim)
            self.latest[i] = (k, len(self.decl_ids[k]))
            self.decl_ids[k].append(i); self.decl_vecs[k].append(v)
            self.pending.append((self.in_index["DECL_" + k], v, k))
        elif k:                  # the model reads the latest declaration of the identifier
            k, j = self.latest[i]
            self.pending.append((self.in_index["REF_" + k], self.decl_vecs[k][j], None))
        else:
            self.pending.append((self.in_index[names[i]], torch.zeros(self.id_dim), None))


def hash_seed(seed, task, index):
    return (seed * 1_000_003 + int.from_bytes(task.encode(), "little") % 1_000_000_007 * 1009 + index) % (2 ** 63)


class Sampler:
    def __init__(self, model, meta, dtype, vocab, device, temperature, greedy, max_steps, max_tokens, seed,
                 max_clause=0, steps_factor=0.0):
        self.model, self.dtype, self.device = model, dtype, device
        self.names = [vocab.name(i) for i in range(len(vocab))]
        self.kinds = [vocab.kind(i) for i in range(len(vocab))]
        self.kind = [KIND_OF.get(k) for k in self.kinds]
        in_names, out_names, self.in_index, self.out_index = vocabularies(self.names, self.kinds)
        assert in_names == meta["in_names"] and out_names == meta["out_names"], \
            "the engine's vocabulary differs from the model's: the arclog wheel does not match the checkpoint"
        self.out_id = [self.names.index(n) if n in self.names else None for n in out_names]   # REF_* have none
        self.ref = {self.out_index["REF_" + k]: k for k in KINDS}
        self.mask_rows, self.mask_table = {}, []
        self.masks = Masks(self.mask_table, self.names, self.kinds, self.out_index)
        self.id_dim = meta["id_dim"]
        self.temperature, self.greedy = temperature, greedy
        self.max_steps, self.max_tokens, self.seed = max_steps, max_tokens, seed
        self.max_clause, self.steps_factor, self.median = max_clause, steps_factor, None
        self.cont_factor = 0.0   # median: the task's, for the factor
        self.progress, self.tests = 0, None
        self.time = {"model": 0.0, "admissible": 0.0, "mask": 0.0, "engine": 0.0}
        self.n_vocab = len(self.names)

    def admitted(self, mask):
        """train.py's Masks.admitted of the mask bytes: the admitted out indices other than REF_*, and the
        admitted identifiers of each kind."""
        row = self.mask_rows.get(mask)
        if row is None:
            row = self.mask_rows[mask] = len(self.mask_table)
            self.mask_table.append(np.frombuffer(mask, np.uint8))
        return self.masks.admitted(row)

    def draw(self, logits, gen):
        if self.greedy:
            return int(logits.argmax())
        p = F.softmax(logits / self.temperature, -1)
        return int(torch.multinomial(p, 1, generator=gen))

    def choose(self, p, mask):
        """The token id that program p writes next under the mask, or None where the head can write none."""
        outs, ident = self.admitted(mask)
        cands = {k: np.array(sorted({p.latest[i][1] for i in ident[k] if i in p.latest}), dtype=np.int64) for k in KINDS}
        outs = np.concatenate([outs, [self.out_index["REF_" + k] for k in KINDS if len(cands[k])]]).astype(np.int64)
        if not len(outs):
            return None
        logits = p.logits.float().cpu()   # the draws take a CPU generator; .cpu() is a no-op on the CPU
        admit = torch.zeros_like(logits, dtype=torch.bool); admit[torch.from_numpy(outs)] = True
        cls = self.draw(logits.masked_fill(~admit, float("-inf")), p.gen)
        if cls in self.ref:
            k = self.ref[cls]
            keys = torch.stack(p.keys[k]).float()
            pl = (p.query.float() @ keys.T / math.sqrt(keys.shape[1])).cpu()
            cand = torch.zeros(len(keys), dtype=torch.bool); cand[torch.from_numpy(cands[k])] = True
            j = self.draw(pl.masked_fill(~cand, float("-inf")), p.gen)
            return p.decl_ids[k][j]
        return self.out_id[cls]

    def feed(self, progs, cache, attention):
        """Feed each program's pending inputs in one forward pass; gives the cache's attention mask after it."""
        n = max(len(p.pending) for p in progs)
        B = len(progs)
        tokens = torch.zeros(B, n, dtype=torch.long)
        ids = torch.zeros(B, n, self.id_dim)
        new = torch.zeros(B, n, dtype=torch.long)
        positions = torch.zeros(B, n, dtype=torch.long)
        for b, p in enumerate(progs):
            m = len(p.pending)
            for t, (x, v, _) in enumerate(p.pending):
                tokens[b, t], ids[b, t] = x, v
            new[b, :m] = 1
            positions[b, :m] = torch.arange(p.fed, p.fed + m)
            positions[b, m:] = p.fed + m - 1 if m else max(p.fed - 1, 0)
        attention = new if attention is None else torch.cat([attention, new], 1)
        d = self.device
        logits, query, key = forward(self.model, tokens.to(d), ids.to(d, self.dtype), attention.to(d), positions.to(d), cache)
        for b, p in enumerate(progs):
            m = len(p.pending)
            for t, (_, _, k) in enumerate(p.pending):
                if k:
                    p.keys[k].append(key[b, t])
            if m:
                p.logits, p.query = logits[b, m - 1], query[b, m - 1]
            p.fed += m; p.pending = []
        return attention

    def boundaries(self, decoder, ids, model, deadline=None):
        """Step a fork of the decoder through a case's stream: the token boundaries and the rule boundaries at
        which the decode has not ended, as counts of the stream's tokens before them, and the verdict kind of the rule
        test at each RULE clause's END, in order, where the decoder runs the rule tests; None where the time passes
        the deadline first."""
        d = decoder.fork()
        tokens, rules, kinds = [0], [], []
        opened = None
        for j, (i, w) in enumerate(zip(ids, model)):
            if not w:
                continue
            if deadline and time.time() > deadline:
                return None
            opened, rule_end = self.after_step(opened, i)
            forced, _, rule_test = d.step(i)
            rule_end = rule_end and any(self.kinds[f] == "relation" for f in forced)
            if rule_end:
                opened = None
            if rule_test is not None:
                kinds.append(kind_name(rule_test))
            end = j + 1 + len(forced)
            if d.ended or end >= len(ids):
                break
            tokens.append(end)
            if rule_end:
                rules.append(end)
        return tokens, rules, kinds

    def after_step(self, opened, i):
        """The keyword of the form in progress after the model writes token i, given that before it, and whether the
        token can end a RULE clause: a RULE clause ends at the END that the engine answers with a relation's id."""
        keyword = self.names[i] if self.names[i] in FORM_KEYWORDS else opened
        return keyword, keyword == "RULE" and self.names[i] == "END"

    def replay(self, p, case, ids, model, m, deadline=None):
        """Step program p's decoder through the first m tokens of a case's stream, and feed them; False where the
        time passes the deadline first."""
        p.prefix_case, p.prefix_tokens = case, m
        j = 0
        while j < m:
            if deadline and time.time() > deadline:
                return False
            i = ids[j]
            assert model[j], f"{p.task} {case}: the prefix's token {j} is the engine's"
            mask = p.decoder.admissible()
            assert mask[i // 8] >> (i % 8) & 1, f"{p.task} {case}: the prefix's token {j} is outside the mask"
            p.opened, rule_end = self.after_step(p.opened, i)
            forced, cons, _ = p.decoder.step(i)
            assert list(forced) == list(ids[j + 1:j + 1 + len(forced)]), \
                f"{p.task} {case}: the engine emits other ids after the prefix's token {j} than the stream holds"
            p.push(i, True, self.names, self.kind)
            for f in forced:
                p.push(f, False, self.names, self.kind)
            p.consistency = cons
            if rule_end and any(self.kinds[f] == "relation" for f in forced):
                p.opened = None
                p.prefix_rules += 1
            j += 1 + len(forced)
        assert j == m and not p.decoder.ended
        return True

    def run(self, task, root, indices, prefixes=None, deadline=None):
        """Sample one program from each of the indices on a fork of the task's root decoder, in lockstep; prefixes
        gives, for each, None or (case, ids, model, m), the first m tokens of a case's stream to replay first. A
        program whose replay passes the deadline ends "deadline"; the lockstep sampling ends "max-seconds" at it."""
        progs = [Program(task, i, root.fork(), self.seed, self.id_dim, self.in_index) for i in indices]
        for p, pre in zip(progs, prefixes or [None] * len(progs)):
            p.max_clause = self.max_clause
            p.max_steps = self.max_steps
            if self.steps_factor:
                source = sum(pre[2]) if pre is not None else self.median
                p.max_steps = min(self.max_steps, max(1, math.ceil(self.steps_factor * source)))
            if self.cont_factor and pre is not None:   # G: the model-written tokens of the case after the prefix
                p.max_cont = max(1, math.ceil(self.cont_factor * sum(pre[2][pre[3]:])))
            if pre is not None:   # an empty prefix keeps its case, as branch point 0 of that case
                p.prefix_case = pre[0]
            if pre is not None and pre[3] and not self.replay(p, *pre, deadline=deadline):
                p.end = "deadline"
        active = [p for p in progs if p.end is None]
        cache, attention = DynamicCache(), None
        rounds, slowest = 0, (0.0, None)
        while active:
            for p in active:
                if p.fed + len(p.pending) > self.max_tokens:
                    p.end = "max-tokens"
                elif deadline and time.time() > deadline:
                    p.end = "max-seconds"
            keep = [b for b, p in enumerate(active) if p.end is None]
            if len(keep) < len(active) and keep and attention is not None:
                cache.batch_select_indices(torch.tensor(keep, device=self.device))
                attention = attention[keep]
            active = [active[b] for b in keep]
            if not active:
                break
            t = time.time()
            attention = self.feed(active, cache, attention)
            self.time["model"] += time.time() - t
            rounds += 1
            if self.progress and rounds % self.progress == 0:
                print(f"  {task}: round {rounds}, tokens {[len(p.ids) for p in active]}, seconds {self.time}, "
                      f"slowest engine step {slowest[0]:.2f} s at {slowest[1]}", flush=True)
            t = time.time()
            chosen = []
            for p in active:
                tm = time.time(); mask = p.decoder.admissible(); self.time["admissible"] += time.time() - tm
                i = self.choose(p, mask)
                if i is None:
                    p.end = "stuck" if any(mask) else "empty-mask"; continue
                assert mask[i // 8] >> (i % 8) & 1, f"{task}: the sampled id {i} is outside the mask"
                chosen.append((p, i))
            if chosen:
                self.time["mask"] += time.time() - t
                t = time.time()
                results = arclog.step_batch([p.decoder for p, _ in chosen], [i for _, i in chosen])
                dt = time.time() - t
                self.time["engine"] += dt
                if dt > slowest[0]:
                    slowest = (dt, f"token {len(chosen[0][0].ids)} ({self.names[chosen[0][1]]})")
                for (p, i), r in zip(chosen, results):
                    if isinstance(r, arclog.Fault):   # the step panicked; the decoder keeps its state before it
                        p.end, p.panic = "panic", str(r)
                        p.push(i, True, self.names, self.kind)
                        continue
                    if isinstance(r, Exception):
                        p.refusals += 1; p.end = "refused"; continue
                    forced, cons, rule_test = r
                    p.steps += 1
                    p.opened, rule_end = self.after_step(p.opened, i)
                    p.push(i, True, self.names, self.kind)
                    for f in forced:
                        p.push(f, False, self.names, self.kind)
                    p.consistency = cons
                    if rule_end and any(self.kinds[f] == "relation" for f in forced):
                        p.opened = None
                    if rule_test is not None:
                        p.rules.append(kind_name(rule_test))
                    if p.decoder.ended:
                        p.end = "ended"
                    elif p.max_clause and p.clause > p.max_clause:
                        p.end = "max-clause"
                    elif p.max_cont and p.steps >= p.max_cont and p.max_cont < p.max_steps:
                        p.end = "max-cont"
                    elif p.steps >= p.max_steps:
                        p.end = "max-steps"
            keep = [b for b, p in enumerate(active) if p.end is None]
            if len(keep) < len(active) and keep:
                cache.batch_select_indices(torch.tensor(keep, device=self.device))
                attention = attention[keep]
            active = [active[b] for b in keep]
        return [{"task": p.task, "rollout": p.index, "end": p.end} if p.end == "deadline" else
                record(p.task, p.prefix_case, p.prefix_rules, p.index, p.ids, p.model, p.prefix_tokens,
                       p.decoder, p.consistency, self.tests, end=p.end, rules=p.rules, model_steps=p.steps,
                       refusals=p.refusals, max_steps_used=p.max_steps, max_cont_used=p.max_cont,
                       max_clause_used=p.max_clause, panic=p.panic)
                for p in progs]


def kind_name(c):
    return str(c.kind).split(".")[-1]


def gold(task, case, ids, model, prefix_tokens, prefix_rules, rules):
    """The line of a case's own stream, from the corpus without a replay: the fields of a decode are null; `rules`
    are the consistency kinds of its RULE clauses after the prefix."""
    return {"task": task, "case": case, "branch": prefix_rules, "rollout": "gold", "ids": list(ids),
            "model": list(model), "prefix_tokens": prefix_tokens, "prefix_rules": prefix_rules, "ended": None,
            "consistency": None, "solved_test": None, "attempts": None, "tokens": len(ids), "program_form": None,
            "end": "gold", "rules": rules, "model_steps": 0, "refusals": 0, "max_steps_used": None,
            "max_cont_used": None, "max_clause_used": None, "panic": None}


def record(task, case, branch, rollout, ids, model, prefix_tokens, decoder, consistency, tests, **rest):
    """One output line; tests are the task's test outputs, None where the task file has none."""
    ended = decoder.ended
    solved = n_attempts = None
    if ended:
        attempts = decoder.attempts() or []
        n_attempts = sum(len(a) for a in attempts)
        if tests is not None:
            solved = len(attempts) == len(tests) and all(t in [[list(r) for r in g] for g in a] for a, t in zip(attempts, tests))
    return {"task": task, "case": case, "branch": branch, "rollout": rollout, "ids": ids, "model": model,
            "prefix_tokens": prefix_tokens, "prefix_rules": branch, "ended": ended,
            "consistency": consistency_json(consistency), "solved_test": solved, "attempts": n_attempts,
            "tokens": len(ids), **program_form(decoder), **rest}


def program_form(decoder):
    """{"program_form": decoder.program_form()}, or {"program_form": None, "program_form_panic": the message} where
    the engine panics in it."""
    try:
        return {"program_form": decoder.program_form()}
    except BaseException as e:   # pyo3's PanicException derives from BaseException and no module exports it
        if type(e).__name__ != "PanicException":
            raise
        return {"program_form": None, "program_form_panic": str(e)}


def corpus_cases(data, names):
    """The streams of each task's cases in a data export, as {task: [(case, ids, model)]}, in file order."""
    vocab = json.load(open(f"{data}/vocab.json"))
    assert (vocab["names"] if isinstance(vocab, dict) else vocab) == names, f"{data}: the export's vocabulary differs from the engine's"
    z = np.load(f"{data}/cases.npz")
    ids, model, off = z["ids"], z["model"], z["offsets"]
    cases = {}
    for c, (task, case) in enumerate(zip(z["task"].tolist(), z["case"].tolist())):
        cases.setdefault(task, []).append((str(case), ids[off[c]:off[c + 1]].tolist(), model[off[c]:off[c + 1]].tolist()))
    return cases


def corpus_stats(data, names):
    """From a data export's cases.npz: the most model-written tokens that one clause of any case holds, and for each
    task the median model-written token count of its cases."""
    vocab = json.load(open(f"{data}/vocab.json"))
    assert (vocab["names"] if isinstance(vocab, dict) else vocab) == names, f"{data}: the export's vocabulary differs from the engine's"
    z = np.load(f"{data}/cases.npz")
    ids, model, off = z["ids"], z["model"].astype(bool), z["offsets"]
    keyword = np.array([n in FORM_KEYWORDS for n in names])
    most, counts = 0, {}
    for c, task in enumerate(z["task"].tolist()):
        i, m = ids[off[c]:off[c + 1]], model[off[c]:off[c + 1]]
        clause = np.cumsum(m & keyword[i])   # the clause index of each position: a form keyword the model writes opens one
        per = np.bincount(clause[m]) if m.any() else np.zeros(1, int)
        most = max(most, int(per.max()))
        counts.setdefault(task, []).append(int(m.sum()))
    return most, {t: float(np.median(v)) for t, v in counts.items()}


def prefix_length(mode, rng, tokens, rules, n):
    """The prefix length in tokens under --prefix mode, from a case's token and rule boundaries and its length n."""
    if mode == "random":
        return rng.choice(rules) if rules else 0
    if mode == "random-token":
        return rng.choice(tokens)
    return max(t for t in tokens if t <= float(mode) * n)


def task_ids(arg):
    path = Path(arg)
    if path.is_file():
        return [t for line in open(path) for t in line.split() if not t.startswith("#")]
    return [t for t in arg.replace(",", " ").split() if t]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, help="a run directory of train.py, with model.pt and model.json")
    ap.add_argument("--tasks", required=True, help="task ids, separated by commas or spaces, or a file of them")
    ap.add_argument("--task-dir", default="data/tasks")
    ap.add_argument("--world", choices=["Closed", "Open"], default="Closed")
    ap.add_argument("--n", type=int, default=1, help="programs per task")
    ap.add_argument("--temperature", type=float, default=1.0)
    ap.add_argument("--greedy", action="store_true", help="take the argmax at each choice")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--max-steps", type=int, default=MAX_STEPS, help="the most model-written tokens of a program")
    ap.add_argument("--max-clause", type=int, default=None,
                    help="the most model-written tokens inside one clause; default 1.5 times the most that one clause "
                         "of a case in --data holds; 0 for none")
    ap.add_argument("--max-steps-factor", type=float, default=0.0,
                    help="lowers --max-steps to this times the source case's model-written tokens (prefix mode), or "
                         "the median of the task's cases in --data; 0 for off")
    ap.add_argument("--max-cont-factor", type=float, default=0.0,
                    help="ends a program at this times the model-written tokens that its source case has after the "
                         "prefix (prefix mode); no effect with --prefix 0; 0 for off")
    ap.add_argument("--max-tokens", type=int, default=MAX_TOKENS, help="the most context positions, the start token included")
    ap.add_argument("--max-seconds", type=float, default=0.0,
                    help="the most wall seconds of a task, its prefix replays included; 0 for none")
    ap.add_argument("--batch", type=int, default=1, help="programs of one task sampled in lockstep")
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--progress", type=int, default=0, help="print a progress line every n lockstep rounds; 0 for none")
    ap.add_argument("--prefix", default="0",
                    help="random (a rule boundary), random-token (a token boundary), or a fraction of the stream's "
                         "tokens: the prefix of a corpus program to replay before sampling; 0 for none")
    ap.add_argument("--prefix-cases", default="first",
                    help="the cases whose streams give the prefixes, by turns over the programs: first (the task's "
                         "first case in the export), all, or case names separated by commas")
    ap.add_argument("--data", default="work/lm/data", help="the data export whose cases.npz gives the prefixes")
    ap.add_argument("--rule-tests", action="store_true",
                    help="run the decode setting rule_tests: the END of each RULE clause gives the verdict of the test of "
                         "its relation, which the lines' `rules` hold; the verdict ends no program")
    ap.add_argument("--out", required=True, help="the JSON lines file of the programs")
    a = ap.parse_args()
    assert a.temperature > 0 or a.greedy
    assert a.prefix in ("random", "random-token") or 0 <= float(a.prefix) <= 1, "--prefix: random, random-token or a fraction"

    model, meta, dtype = load_model(a.model, a.device)
    use_autocast = a.device == "cuda" and dtype == torch.float32
    out = Path(a.out); out.parent.mkdir(parents=True, exist_ok=True)
    sampler, records, dropped, t0, corpus = None, [], {}, time.time(), None
    with open(out, "w") as f, torch.no_grad(), torch.autocast("cuda", dtype=torch.bfloat16, enabled=use_autocast):
        for task in task_ids(a.tasks):
            session = arclog.Session(arclog.Task.from_json(open(f"{a.task_dir}/{task}.json").read(), getattr(arclog.World, a.world)),
                                     arclog.DecodeSettings(rule_tests=a.rule_tests))
            if sampler is None:
                sampler = Sampler(model, meta, dtype, session.vocabulary, a.device, a.temperature, a.greedy,
                                  a.max_steps, a.max_tokens, a.seed)
                if a.max_clause is None or a.max_steps_factor:
                    most, medians = corpus_stats(a.data, sampler.names)
                sampler.steps_factor = a.max_steps_factor
                sampler.cont_factor = a.max_cont_factor
                if a.max_clause is None:
                    sampler.max_clause = math.ceil(1.5 * most)
                    print(f"max-clause {sampler.max_clause}: 1.5 times {most}, the most model-written tokens of one "
                          f"clause in {a.data}", flush=True)
                else:
                    sampler.max_clause = a.max_clause
                sampler.progress = a.progress
                s = session.settings
                settings = {k: getattr(s, k) for k in SETTINGS}
                f.write(json.dumps({"settings": settings, "world": a.world, "args": vars(a),
                                    "max_clause": sampler.max_clause,
                                    "model_meta": {k: v for k, v in meta.items() if not k.endswith("_names")}}) + "\n")
            task_json = json.load(open(f"{a.task_dir}/{task}.json"))
            tests = [t["output"] for t in task_json["test"]] if all("output" in t for t in task_json["test"]) else None
            sampler.tests = tests
            if a.max_steps_factor:
                assert task in medians, f"{task}: no case in {a.data}"
                sampler.median = medians[task]
                cap = min(a.max_steps, max(1, math.ceil(a.max_steps_factor * medians[task])))
                print(f"{task}: median {medians[task]:g} model-written tokens; max-steps {cap} from nothing"
                      + (", and from a prefix, the factor times the source case's" if a.prefix != "0" else ""), flush=True)
            deadline = time.time() + a.max_seconds if a.max_seconds else None
            root = session.decoder()
            golds, bounds = set(), {}
            prefix_of = lambda i: None
            if a.prefix != "0":
                if corpus is None:
                    corpus = corpus_cases(a.data, sampler.names)
                cases = corpus.get(task, [])
                if a.prefix_cases == "first":
                    cases = cases[:1]
                elif a.prefix_cases != "all":
                    names = a.prefix_cases.split(",")
                    cases = [c for c in cases if c[0] in names]
                assert cases, f"{task}: no case of {a.data} gives a prefix"
                for c in cases:
                    bounds[c[0]] = sampler.boundaries(root, c[1], c[2], deadline)
                    if bounds[c[0]] is None:
                        break

                def prefix_of(i):
                    case, ids, model = cases[i % len(cases)]
                    rng = random.Random(hash_seed(a.seed, task, i) + 1)
                    return case, ids, model, prefix_length(a.prefix, rng, *bounds[case][:2], len(ids))
            for start in range(0, a.n, a.batch):
                idx = list(range(start, min(a.n, start + a.batch)))
                t = time.time()
                if None in bounds.values():   # the deadline passed before the prefixes' boundaries were found
                    for i in idx:
                        dropped[f"{task} #{i}"] = "deadline"
                    print(f"{task} #{idx[0]}-{idx[-1]}: dropped, the prefixes' boundaries passed the deadline", flush=True)
                    continue
                for r in sampler.run(task, root, idx, [prefix_of(i) for i in idx], deadline):
                    if r["end"] == "deadline":
                        dropped[f"{task} #{r['rollout']}"] = "deadline"
                        print(f"{task} #{r['rollout']}: dropped, its prefix replay passed the deadline", flush=True)
                        continue
                    if r["case"] is not None and (r["case"], r["prefix_tokens"]) not in golds:   # once per branch point
                        golds.add((r["case"], r["prefix_tokens"]))
                        c = next(c for c in cases if c[0] == r["case"])
                        f.write(json.dumps(gold(task, c[0], c[1], c[2], r["prefix_tokens"], r["prefix_rules"],
                                                bounds[c[0]][2][r["prefix_rules"]:])) + "\n")
                    r["seconds"] = round(time.time() - t, 2)
                    records.append(r); f.write(json.dumps(r) + "\n"); f.flush()
                    print(f"{task} #{r['rollout']}: {r['end']}, {r['tokens']} tokens, {r['model_steps']} model steps (cap {r['max_steps_used']}), "
                          f"rules {r['rules']}, solved_test {r['solved_test']}, prefix {r['prefix_tokens']} tokens "
                          f"({r['prefix_rules']} rules) of {r['case']}"
                          + (f", panic: {r['panic']}" if r["panic"] else ""), flush=True)
                    if r["end"] == "panic":
                        repro = out.parent / f"panic-{task}-{r['rollout']}.json"
                        repro.write_text(json.dumps({
                            "note": f"sampler repro, {task}, checkpoint {Path(a.model).name}, T={a.temperature:g}, "
                                    f"seed {a.seed}, rollout {r['rollout']}, panic",
                            "task": task, "ids": r["ids"], "model": r["model"], "end": "panic", "panic": r["panic"],
                            "settings": settings, "world": a.world, "record": r}))
                        print(f"{task} #{r['rollout']}: repro {repro}", flush=True)
    seconds = time.time() - t0
    tokens = sum(len(r["ids"]) for r in records)
    by_cons = {}
    for r in records:
        k = r["consistency"]["kind"] if r["consistency"] else None
        by_cons[str(k)] = by_cons.get(str(k), 0) + 1
    by_end = {}
    for e in [r["end"] for r in records] + list(dropped.values()):
        by_end[e] = by_end.get(e, 0) + 1
    print(json.dumps({"programs": len(records), "ended": by_end.get("ended", 0), "by_end": by_end,
                      "by_consistency": by_cons, "mean_tokens": tokens / max(1, len(records)),
                      "seconds_per_token": seconds / max(1, tokens),
                      "seconds_per_model_step": seconds / max(1, sum(r["model_steps"] for r in records)),
                      "refusals": sum(r["refusals"] for r in records), "seconds": round(seconds, 1),
                      "solved_test": sum(bool(r["solved_test"]) for r in records),
                      "seconds_by_part": {k: round(v, 1) for k, v in (sampler.time if sampler else {}).items()}}))


if __name__ == "__main__":
    main()
