"""Write written clauses as sampler lines: each is a clause drawn token by token under the engine's mask at a branch
point of a task, by a scorer fit on the corpus clauses of other tasks.

    work/lm/.venv/bin/python work/lm/data-study/writer.py sample [--tasks T ...] [--model ngram|trees|tables]
        [--temperature T] [--corpus DIR] [--tables DIR] [--per-point K] [--max-tries N] [--point-seconds S]
        [--seconds S] [--min-tokens N] [--length-low X] [--length-high X] [--seed S] [--data DIR] [--out DIR]
        [--world W] [--points all] [--stamps FILE] [--queue DIR] [--reject-empty]
        [--constraints gold98|gold95|normal|normal2|normal3]
    work/lm/.venv/bin/python work/lm/data-study/writer.py fit [--model ngram|trees|tables] [--corpus DIR] [--tables DIR]
        --out DIR
    work/lm/.venv/bin/python work/lm/data-study/writer.py eval [--model ngram|trees|tables ...] [--corpus DIR]
        [--tables DIR] [--out DIR] [--tasks T ...] [--data DIR] [--points N] [the options of sample]
    work/lm/.venv/bin/python work/lm/data-study/writer.py tables [--tables DIR] --out DIR
    work/lm/.venv/bin/python work/lm/data-study/writer.py constraints [--corpus DIR] [--constraints normal --tables DIR]

A clause of a stream is its model-written tokens from the stream's first model-written token, or the first one
after the engine declares a relation, up to and including the token after which the engine declares a relation;
clauses of every kind (RULE, INIT, DET, CHOOSE) count. Its index is its place among the stream's clauses, from 0. A
clause's skeleton is its tokens with each identifier (kinds relation and label) replaced by its kind, RELATION or
LABEL.

Corpus and folds. The corpus is `--corpus`'s cases.npz (default `--data`). Its clauses are taken once per task: of
the clauses of a task's cases with one skeleton, only the first in file order. A task's fold is the sha256 of its
name, modulo 5. The scorer of fold k is fit on the corpus clauses of the tasks of the other folds, and a task is
sampled by the scorer of its fold.

A step's candidates are the admitted out tokens (every token the mask admits that is not an identifier) and the
classes RELATION and LABEL, each where the mask admits an identifier of that kind that the stream has declared. In
the corpus, a step's mask is the stream's mask at that model-written token (cases.npz's mask_index and mask_table).

Scorers (`--model`), each giving a score per candidate; a draw takes the candidate from the softmax of the scores
over the candidates divided by `--temperature`:
- ngram: an interpolated Kneser-Ney model of order 3 (discount 0.75) over skeletons, each clause preceded by two
  start symbols; the score is the log of its probability. It reads only the clause's last two skeleton tokens.
- trees: sklearn's HistGradientBoostingClassifier, binary, on (context, candidate) rows: the label is whether the
  candidate is the corpus's next token. The context is the clause's last three skeleton tokens, the token's place
  in the clause, the clause's index and the counts of relations and labels the stream has declared; the candidate
  is its skeleton token. Each step of the training clauses gives its gold candidate and up to NEGATIVES of its other
  candidates, drawn uniformly; the steps are taken from the clauses in a random order up to ROWS rows. The score is
  the decision function (log odds). Settings: TREES. It needs scikit-learn on PYTHONPATH.
- tables: trees on other candidates and more features. The class RELATION is replaced by each declared relation
  that the mask admits, as a candidate of its own (`expand`); the class LABEL stays. A row gives the features of
  trees (a relation candidate as RELATION), then the relation features of the candidate's relation (missing for
  any other candidate), then those of the relation the clause has referred to last (missing where none). Each step
  of the training clauses gives its gold and up to NEGATIVES other candidates, drawn uniformly, so a step at which
  the gold is a relation also gives other relations as negatives.

Relation features (REL_FEATURES) of a declared relation `&r<k>` at a step: those of its table (TABLE_FEATURES, from
`--tables`, an export of engine/arclog-py/tables_export.py, read by TableSource), then age (the relations declared
after it), uses (its model-written tokens in the stream so far) and head (HEADS: the first token of the clause after
which the engine declares it). A table's features, with its rows at a train example taken over all its entries
there (every DET assignment and model; a task-wide entry's rows at the example its first Example column gives, or
at every train example where it has none), Example and Unit columns left out:
- seen: the case has a table of relation k (0: every value below missing); unseen: the table faults, its search
  for projections stopped, or an entry at a train example, or a task-wide entry, is not rows (undefined, stopped at
  the work cap, an example's fault, no entries), detectors.py's f_unseen;
- empty (detectors.py's f_empty), zero_some (0 rows at some train example) and log_rows (log of 1 + the mean over
  the train examples of the most rows of an entry there), each missing where unseen;
- width (int32 cells per row), columns, and the counts of its Box, Color, Number, Ident and orientation columns;
  example (it has an Example column); depth (tables.parquet's); det (its own DET: `slot <k>` among its
  det_relations); dets (the DETs its entries are assigned);
- from the rows, where every entry at a train example is a Rows entry of at most VALUE_ROWS rows (else missing):
  const_share (detectors.py's), restates (detectors.restates: at every train example its rows equal those of an
  earlier table of the case projected onto distinct columns of the same types; the earlier tables are the tables
  before it in the case with rows, ex_input included and ex_output left out), new_values (detectors.py's, against
  those earlier tables).
The training clause at index i of a case reads the tables of the relations the stream declares before it. A case
where some relation `&r<k>` of its stream has a table in `--tables` whose token is not the stream's last
model-written token before the declaration gives no table features (every value missing). In the corpus export,
the relations with no table are each declared after an INIT clause.
The fits of each fold are kept in `<out>/models/`, named by the scorer, the fold and the sha256 of the corpus and
the code that fits them (and, for tables, of `--tables`' tables.parquet and index.parquet); `fit` writes the five of
a scorer, and `sample` and `eval` fit any one they miss. The relation features of the corpus cases that `fit` and
`eval` read are kept in `<out>/models/tables-<key>.pkl` (key: the sha256 of those two files and TABLES_VERSION), and
`tables` reads every case of `--tables` into it.

A written clause at a branch point (points.py: every rule boundary of each task's first case in `--data`) is drawn on
a fork of the task's decoder stepped through the prefix, as foreign.py steps it. At each step the scorer picks a
candidate; a class picks an identifier of its kind uniformly among the declared ones that the mask admits. The
clause ends where the engine declares a relation after a token. The decoder gives no rows of a declared relation,
so the scorer tables reads the relation features of the prefix's relations from the tables of the task's first
case (`gold_tables`): from `--tables` where `--corpus`'s cases.npz holds that case with the same stream and the
export's tables of its relations follow the stream's tokens, else from one replay of the case's stream by
tables_export (`export_streams`), kept in `<out>/tables/`.

Length. With g the model-written token count of the gold's clause after the prefix (or the median clause length of
the corpus where the gold has none), the clause is held to lo = max(--min-tokens, ceil(--length-low * g)) and
hi = max(lo + 2, floor(--length-high * g)) tokens: while it has fewer than lo tokens, each candidate that ended a
corpus clause (a closer) is stepped on a fork first and dropped where the engine would declare a relation after it;
a clause that reaches hi tokens without an end is dropped.

Constraints (`--constraints`, default none). `Shape` reads a clause's conjuncts as the clause is drawn, and
TESTS are tests of its structure, each of one conjunct as it closes or of the whole clause as it ends. A set of
CONSTRAINT_SETS gives the tests it applies to each clause head; gold98 (gold95) applies a test to a head where at
least 98% (95%) of the corpus clauses of that head meet it, among RULE, DET and INIT (`constraints` prints the shares), and nothing
to a clause of another head. normal applies the normal form to RULE, DET and INIT clauses: in each segment but an
INIT clause's key clause (its body gives the instances, one per row), the conjuncts with arguments are one component of the join graph (an edge where two share a label, directly or through a
comparison; a NOT conjunct joins as a positive one), or every component but one is one-row. A component is one-row
where it binds no label (each label it reads is bound outside the segment, such as a key label), since it then has
at most one row, or where each of its conjuncts is a positive read of a relation `&r<k>` of the prefix whose table, projected onto the
columns its sites read, has at most one distinct row at every input (the task input and each example) under each
DET assignment (each entry of the table on its own; a DET clause's lifted read with no site on the Example column
reads the union over the inputs of one assignment). The table is the prefix
case's (`gold_source`, as the scorer tables reads it), and `CaseRows` maps a read's column tokens to its columns: by
the registry's port columns for an instance's relation, in order for a proposer's, and for a clause with a body by
the copy flows of flows.parquet, to every column whose flows the sites of the token's label explain. A component with
a NOT conjunct, a lib or fact relation, or a relation with no table, or an entry with no rows to read, is not
one-row. normal2 applies to RULE, DET and INIT clauses the normal form and "no free domain argument": each label that a `*`
binds at a site of a lib relation (kinds lib relation and relation macro) on a column of a finite domain type is read
by another token of the clause, or is determined by the atom's other finite-domain columns whose labels the clause
reads (`determined`: from the engine's row counts of the relation, for a relation whose columns are all of such
types; a relation with a column of another type determines none). The finite domain types are the orientation types of `arclog.orientation_types`
(ORIENT_DOMAIN); `domain_columns` reads each lib relation's column types from engine/lib/registry.sexpr, and a
macro's from the sites of its variables in its body. normal3 adds to normal2, on the same clauses, "domain from
data": each label on a finite-domain column of a lib relation is restricted by the task's data. A label is restricted
where it is at a site of a derived or fact relation (under NOT as well), where it is in a `=` with a restricted label,
where it is in a constant input of an INIT clause (a component of a segment's join graph of lib relations that read no
label from outside it, such as a Ray's four Dirs), or where a lib relation fixes it from restricted labels: on a
relation whose columns are all of finite domain types, where the restricted labels of its other columns filter the
column (`filters`: from the engine's row counts, as `determined`); on another relation, where each other column has a
site with a restricted label, or each other column with a site does and one of them is `0` (a filter), or where the
atom is positive, one other column of a type that is not finite has a restricted label, not `0`, and another has a label
(an index: the label picks which value the atom gives from the data, such as `margin` of a box on each side). A `*`
label that only the first label of a `= *X` reads, where nothing reads X, is not restricted. So --constraints normal,
normal2 and normal3 need --tables (they have no default there), and `constraints` tests the normal form where --tables
is given; it prints each set's share beside the tests', and the shares for the output clause of every case, its last
RULE clause. The rejection is per conjunct: the writer keeps the state before each conjunct (the
decoder's fork, the tokens, the declared identifiers), and where a conjunct fails a conjunct test, or the ended
clause fails a clause test, it goes back to the state before that conjunct (for a clause test, the last one) and
draws again from there. After CONJUNCT_TRIES such draws in one clause, or where a clause test fails on a body with
no conjunct, the clause is given up as "no candidate". The counts give the draws again per branch point
("redrawn").

A drawn clause is completable where it ends with lo to hi tokens. It is otherwise counted by its reason: "fault"
(the engine panics or refuses a step), "ended" (the decode ends), "no candidate" (no candidate is left at a step),
"too short" (the engine declares a relation before lo tokens after a token that is not a closer), "too long" (hi
tokens without an end), and with `--reject-empty`, "empty": before the clause's last token, the engine's count of
the rows of the clause's body (`Decoder.counts`) is 0 at every example under every DET assignment
(`empty_counts`; a clause whose body the engine does not count, such as an INIT clause, is kept). A branch point stops at `--per-point` completable clauses, at `--max-tries` clauses drawn,
or at `--point-seconds` of wall time, whichever comes first: no clause is drawn after that, and the clauses in progress
end. A branch point's clauses are drawn together, up to `--per-point` less the completable ones at a time, and step
together, with one scorer call per step over the candidates of every clause in progress; a clause that ends or is
dropped leaves the group, and a clause drawn again from the state before a conjunct stays in it from that state. The
random choices of the i-th clause drawn at a branch point (from 0) come from a generator of its own, seeded by
`--seed`, the task, prefix_tokens and i, so they do not depend on the clauses drawn beside it. A task whose gold stream the engine refuses, faults or panics on, and a branch point whose prefix
replay raises, are logged and counted as in foreign.py.

`--out` (default work/lm/rollouts-writer) gets samples/<task>.jsonl for each task: a settings line, the gold lines
of points.py, and one line per written clause with the fields of model/sample.py's `record` (end "writer"; `rules`
gives the clause's consistency kind where it is a RULE clause), a rollout index counted per branch point from 0, and
`writer` {model, temperature, fold, tokens (its model-written token count)}. The settings line has the engine's
default settings and `--world`; its `args` give `model` null (no LM wrote the lines), `prefix` "random", `points`
"all", `data`, `corpus` and the writer's options; `model_meta` gives `fold` null. It also gets counts/<task>.json:
per branch point, the clauses drawn by outcome, the lines written, g, lo, hi and the seconds taken, and with
`--reject-empty` the completable clauses whose body the engine counts ("counted"; "counted empty" is 0, since an
empty clause is drawn again). A task stops starting branch points after `--seconds` from its start. `--stamps` and `--queue` are those of foreign.py.

`eval` prints, with the scorer tables, the counts of the relations that the corpus streams declare by their tables
in `--tables` (the export's `case` and `relation` k against the stream's case and `&r<k>`, its `token` against the
stream's last model-written token before the declaration); then, per fold and scorer, the mean log-likelihood per
step of the held-out fold's corpus clauses (at most --eval-clauses, drawn with the fold as seed) under the scorer's
softmax over the step's candidates (temperature 1): of the gold token, with a relation identifier a token of its own
(ngram and trees choose it uniformly within the class RELATION), and of its class (tables sums its relations), each
beside the uniform choice; and, for the tasks of `--tasks` (default: the first three of `--data`), at up to
`--points` branch points each, the share of clauses drawn that are completable, by reason, the completable ones
that `empty_counts` gives as empty, and the lengths of the completable ones against g. It writes no lines.
"""
from pathlib import Path as _StudyPath
import sys as _study_sys
_study_sys.path.insert(0, str(_StudyPath(__file__).resolve().parents[0]))
from study_paths import CODE_ROOT, DATA_ROOT, MAIN_ROOT, REPO_ROOT, data_path
import argparse, copy, hashlib, json, math, os, pickle, random, shutil, sys, time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

ROOT = MAIN_ROOT
GEN_VERSION = 2   # raise by hand on any change to how this script makes its lines; allpoints.py reads it into the stamp of a task's samples
FIT_VERSION = 1   # raise by hand on any change to how a scorer is fit; it names the fits in <out>/models
TABLES_VERSION = 1   # raise by hand on any change to the relation features; it names their cache in <out>/models
FOLDS = 5
DISCOUNT = 0.75
ROWS, NEGATIVES = 50000, 8
TREES = dict(max_iter=200, learning_rate=0.1, max_depth=6, min_samples_leaf=20, l2_regularization=1.0,
             early_stopping=False, random_state=0)
REASONS = ("fault", "ended", "no candidate", "too short", "too long", "empty")
TABLES = ROOT / "work/tables/full-4663b88a"
VALUE_ROWS = 2000   # the most rows of an entry whose values the relation features read
WHOLE_FILE = 64 << 20   # a case's values file up to this size is read whole, a larger one entry by entry
ORIENT = {"Dir", "DiagDir", "Dir8", "Axis", "DiagAxis", "Axis4", "D4", "C4", "Sym", "Sense", "Pose"}
ORIENT_DOMAIN = ORIENT - {"Pose"}   # the finite domain types: the names of `arclog.orientation_types()`
HEADS = {"RULE": 0, "DET": 1, "INIT": 2, "CHOOSE": 3, "RIGID_DET": 4}   # any other clause head: 5
TABLE_FEATURES = ["seen", "unseen", "empty", "zero_some", "log_rows", "width", "columns", "box", "color", "number",
                  "ident", "orient", "example", "depth", "det", "dets", "const_share", "restates", "new_values"]
REL_FEATURES = TABLE_FEATURES + ["age", "uses", "head"]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import pinned   # noqa: E402
pinned.use()   # the pinned model/ modules (pinned.py)


def fold_of(task):
    return int(hashlib.sha256(task.encode()).hexdigest(), 16) % FOLDS


def file_sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


# ------------------------------------------------------------------ the skeleton vocabulary

class Vocab:
    """The skeleton vocabulary of the engine's vocabulary: index 0 the start symbol, 1 RELATION, 2 LABEL, then each
    name that is not an identifier, in vocabulary order."""
    def __init__(self, names, kinds):
        self.names, self.kinds = names, kinds
        self.sk_names = ["<s>", "RELATION", "LABEL"]
        self.sk = np.zeros(len(names), dtype=np.int64)
        for i, (n, k) in enumerate(zip(names, kinds)):
            if k == "relation":
                self.sk[i] = 1
            elif k == "label":
                self.sk[i] = 2
            else:
                self.sk[i] = len(self.sk_names)
                self.sk_names.append(n)
        self.is_rel = np.array([k == "relation" for k in kinds])
        self.is_lab = np.array([k == "label" for k in kinds])
        self.is_out = ~(self.is_rel | self.is_lab)
        self.ident = self.is_rel | self.is_lab
        self.rel_k = np.array([int(n[2:]) if k == "relation" else -1 for n, k in zip(names, kinds)])
        self.head = np.array([HEADS.get(n, 5) for n in names])

    def candidates(self, admitted, declared):
        """(the skeleton indexes of the candidates, their vocabulary ids (-1 for a class)) of a step, from the bool
        array of admitted ids and the bool array of declared identifiers."""
        outs = np.flatnonzero(admitted & self.is_out)
        sk, ids = self.sk[outs].tolist(), outs.tolist()
        for c, kind in ((1, self.is_rel), (2, self.is_lab)):
            if (admitted & kind & declared).any():
                sk.append(c); ids.append(-1)
        return sk, ids


def unpack(mask, n):
    return np.unpackbits(np.frombuffer(bytes(mask), dtype=np.uint8), bitorder="little")[:n].astype(bool)


# ------------------------------------------------------------------ the corpus

class Corpus:
    """The clauses of a cases.npz, once per task: `clauses`, a list of dicts {task, case, fold, index (the clause's
    index in its case), toks (vocabulary ids), steps (the model step of each token, for its mask), declared (the
    stream's declared identifiers before the clause, as vocabulary ids), emitted (per token, the identifiers the engine
    declares after it), forced (per token, every token the engine emits after it), heads and uses (`stream_state` before the clause)}; `closers`, the vocabulary ids that end
    some clause; `outputs`, the last RULE clause of each case (its output clause), of every case; `median`, the
    median clause length; `decls`, (task, case, k, the index of the last model-written
    token before it) of each relation `&r<k>` a stream declares; `streams`, {(task, case): (ids, model)}."""
    def __init__(self, data, vocab):
        z = np.load(Path(data) / "cases.npz")
        ids, model, off = z["ids"], z["model"], z["offsets"]
        self.mask_index, self.mask_table = z["mask_index"], z["mask_table"]
        self.vocab = vocab
        kinds = vocab.kinds
        is_rel, ident = vocab.is_rel.tolist(), vocab.ident.tolist()
        steps0 = np.concatenate([[0], np.cumsum(model)])[off].tolist()
        seen = set()
        self.clauses, closers, lengths, self.decls, self.outputs = [], Counter(), [], [], []
        tasks, cases = z["task"].tolist(), z["case"].tolist()
        head_of, rel_k = vocab.head.tolist(), vocab.rel_k.tolist()
        for c, (task, case) in enumerate(zip(tasks, cases)):
            ii = ids[off[c]:off[c + 1]].tolist()
            mm = model[off[c]:off[c + 1]].tolist()
            step = steps0[c]
            declared, cur, idx, start_decl, last_rule = [], None, 0, [], None
            heads, uses, head, last_model, start = {}, Counter(), 5, -1, None
            for j, (i, m) in enumerate(zip(ii, mm)):
                if m:
                    if cur is None:
                        cur = dict(toks=[], steps=[], emitted=[], forced=[])
                        start_decl = list(declared)
                        start, head = (dict(heads), dict(uses)), head_of[i]
                    cur["toks"].append(i); cur["steps"].append(step); cur["emitted"].append([]); cur["forced"].append([])
                    step += 1
                    last_model = j
                    if is_rel[i]:
                        uses[i] += 1
                else:
                    if cur is not None:
                        cur["forced"][-1].append(i)
                    if ident[i]:
                        declared.append(i)
                        if cur is not None:
                            cur["emitted"][-1].append(i)
                    if is_rel[i]:
                        heads[i] = head
                        self.decls.append((task, case, rel_k[i], last_model))
                    if cur is not None and is_rel[i]:
                        key = (task, tuple(vocab.sk[cur["toks"]].tolist()))
                        lengths.append(len(cur["toks"]))
                        closers[cur["toks"][-1]] += 1
                        cur.update(task=task, case=case, fold=fold_of(task), index=idx, declared=start_decl,
                                   heads=start[0], uses=start[1])
                        if key not in seen:
                            seen.add(key)
                            self.clauses.append(cur)
                        if kinds[cur["toks"][0]] == "control" and vocab.names[cur["toks"][0]] == "RULE":
                            last_rule = cur
                        cur, idx = None, idx + 1
            if last_rule is not None:
                self.outputs.append(last_rule)
        self.closers = set(closers)
        self.median = int(np.median(lengths))
        self.lengths = lengths
        self.n_cases, self.n_tasks = len(tasks), len(set(tasks))

    def walk(self, cl, source=None):
        """Each step of clause cl: (its context, the candidate skeleton indexes, the gold's skeleton index, the gold's
        vocabulary id). A context is (history of skeleton tokens, k, the clause's index, n relations declared, n labels
        declared, `relation_context` with the relation features of `source` (a TableSource) for the clause's case,
        None without a source)."""
        v = self.vocab
        declared = np.zeros(len(v.names), dtype=bool)
        declared[cl["declared"]] = True
        feats = source.features(cl["task"], cl["case"]) if source is not None else None
        uses, last = cl["uses"], None
        hist = []
        for k, (tok, st, em) in enumerate(zip(cl["toks"], cl["steps"], cl["emitted"])):
            adm = np.unpackbits(self.mask_table[self.mask_index[st]], bitorder="little")[:len(v.names)].astype(bool)
            sk, _ = v.candidates(adm, declared)
            n_rel = int((declared & v.is_rel).sum())
            x = relation_context(v, adm, declared, feats, cl["heads"], uses, last, n_rel) if source is not None else None
            yield (hist, k, cl["index"], n_rel, int((declared & v.is_lab).sum()), x), sk, int(v.sk[tok]), tok
            hist = hist + [int(v.sk[tok])]
            if v.is_rel[tok]:
                uses, last = {**uses, tok: uses.get(tok, 0) + 1}, tok
            declared[em] = True


def relation_context(v, adm, declared, feats, heads, uses, last, n_rel):
    """What the scorer `tables` reads of a step beside the token context: rels (the declared relations the mask
    admits, as vocabulary ids), feats ({k: TableSource features} of the case's relations, or None), heads ({relation
    id: the head code of the clause that declares it}), uses ({relation id: its model-written references so far}),
    last (the relation the clause refers to last, or None) and n_rel."""
    return dict(rels=np.flatnonzero(adm & v.is_rel & declared).tolist(), feats=feats, heads=heads, uses=uses,
                last=last, n_rel=n_rel)


def stream_state(v, ids, model, n):
    """(heads, uses) of the first n tokens of a stream: heads {relation id: the head code (HEADS) of the clause
    after which the engine declares it}, uses {relation id: the count of its model-written tokens}."""
    heads, uses, head, new = {}, Counter(), 5, True
    for i, m in zip(ids[:n], model[:n]):
        if m:
            if new:
                head, new = int(v.head[i]), False
            if v.is_rel[i]:
                uses[i] += 1
        elif v.is_rel[i]:
            heads[i], new = head, True
    return heads, dict(uses)


# ------------------------------------------------------------------ the relation features

_N_TRAIN = {}


def n_train_of(task):
    if task not in _N_TRAIN:
        _N_TRAIN[task] = len(json.load(open(ROOT / "data/tasks" / f"{task}.json"))["train"])
    return _N_TRAIN[task]


def runs(df):
    """{(task, case): the row positions of the frame's rows of that case}: the runs of equal (task, case), where the
    frame holds each case in one run, as the export writes it; else pandas' groups."""
    t, c = df["task"].to_numpy(), df["case"].to_numpy()
    if not len(t):
        return {}
    b = np.flatnonzero((t[1:] != t[:-1]) | (c[1:] != c[:-1])) + 1
    starts, ends = np.concatenate([[0], b]), np.concatenate([b, [len(t)]])
    keys = list(zip(t[starts].tolist(), c[starts].tolist()))
    if len(set(keys)) < len(keys):
        return df.groupby(["task", "case"], sort=False).indices
    return {k: np.arange(a, z) for k, a, z in zip(keys, starts, ends)}


class TableSource:
    """The relation tables of the cases of a tables export (engine/arclog-py/tables_export.py's layout): `features`
    gives {k: [the values of TABLE_FEATURES]} of the tables of a case's relations `&r<k>`, each case read once.
    With `cache` (a file), the features of the cases read are kept there by `save` and read from it; with `task`,
    only that task's rows are read."""
    def __init__(self, d, cache=None, task=None):
        import pandas as pd
        self.d, self.cache_file, self.added, self.bad = Path(d), cache, 0, set()
        only = [("task", "==", task)] if task else None
        self.t = pd.read_parquet(self.d / "tables.parquet", filters=only, columns=[
            "task", "case", "table", "token", "point", "relation", "column_names", "column_types", "width", "depth",
            "det_relations", "fault", "projections"])
        self.t_at = runs(self.t)
        i = pd.read_parquet(self.d / "index.parquet", filters=only, columns=[
            "task", "case", "table", "example_kind", "example_index", "kind", "rows", "offset", "entry"])
        self.i = {c: i[c].to_numpy() for c in ["table", "example_kind", "example_index", "kind", "rows", "offset",
                                               "entry"]}
        self.i_at = runs(i)
        self.cache = pickle.loads(Path(cache).read_bytes()) if cache and Path(cache).exists() else {}
        self.only, self._flows, self._assigned = only, None, None

    def assignments(self, task, case):
        """{entry: the key of its DET assignment (its DETs' rows, as (det, rows, offset), equal values sharing an
        offset)} of a case, from assigned.parquet, read once."""
        if self._assigned is None:
            import pandas as pd
            f = pd.read_parquet(self.d / "assigned.parquet", filters=self.only,
                                columns=["task", "case", "entry", "det", "rows", "offset"])
            self._assigned = (f, runs(f))
        f, at = self._assigned
        out = defaultdict(set)
        ix = at.get((task, case), np.zeros(0, np.int64))
        for e, d, n, o in zip(*(f[c].to_numpy()[ix].tolist() for c in ["entry", "det", "rows", "offset"])):
            out[e].add((d, n, o))
        return {e: frozenset(x) for e, x in out.items()}

    def flows(self):
        """(the copy flows of flows.parquet, as arrays, {(task, case): their row positions}), read once."""
        if self._flows is None:
            import pandas as pd
            f = pd.read_parquet(self.d / "flows.parquet", filters=self.only, columns=[
                "task", "case", "table", "column", "kind", "source_table", "source_relation", "source_column", "det",
                "atom"])
            f = f[f["kind"] == 0].reset_index(drop=True)
            self._flows = ({c: f[c].to_numpy() for c in ["table", "column", "source_table", "source_relation",
                                                          "source_column", "det", "atom"]}, runs(f))
        return self._flows

    def save(self):
        """Write the features of the cases read to the cache file, with those another process wrote there."""
        if not self.cache_file or not self.added:
            return
        p = Path(self.cache_file)
        if p.exists():
            self.cache = {**pickle.loads(p.read_bytes()), **self.cache}
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(f".{os.getpid()}.tmp")
        tmp.write_bytes(pickle.dumps(self.cache))
        tmp.rename(p)
        self.added = 0

    def match(self, decls):
        """Counter of the relation declarations `decls` ((task, case, k, last model token)) by their tables: one
        table whose token is that last model token, one or more otherwise ("differs"), none. A case with a
        declaration that differs gives no features from then on."""
        r = self.t[self.t["relation"] >= 0]
        at = defaultdict(list)
        for task, case, k, tok in zip(r["task"], r["case"], r["relation"].tolist(), r["token"].tolist()):
            at[(task, case, k)].append(tok)
        out = Counter()
        for task, case, k, tok in decls:
            got = at.get((task, case, k), [])
            kind = "no table" if not got else "token matches" if got == [tok] else "differs"
            out[kind] += 1
            if kind == "differs":
                self.bad.add((task, case))
        return out

    def features(self, task, case):
        if (task, case) in self.bad:   # the export's tables do not follow the stream (`match`)
            return None
        if (task, case) not in self.cache:
            self.cache[(task, case)] = self._features(task, case)
            self.added += 1
        return self.cache[(task, case)]

    def _features(self, task, case):
        import detectors as D
        if (task, case) not in self.t_at:
            return None
        tabs = self.t.iloc[self.t_at[(task, case)]].sort_values("table")
        ix = self.i_at.get((task, case), np.zeros(0, np.int64))
        ents = {k: v[ix] for k, v in self.i.items()}
        n_train = int(((ents["table"] == 0) & (ents["example_kind"] == 1)).sum()) or n_train_of(task)
        try:
            fh = open(self.d / "values" / task / f"{case}.i32", "rb")
        except FileNotFoundError:
            fh = None
        whole = np.fromfile(fh, np.int32) if fh is not None and os.fstat(fh.fileno()).st_size <= WHOLE_FILE else None
        D._COLSETS.clear()   # keyed by object ids, so emptied per case
        by_table = defaultdict(list)
        for j, tb in enumerate(ents["table"].tolist()):
            by_table[tb].append(j)
        earlier = []   # the Rows of the earlier tables with rows, ex_output left out
        held = [np.zeros(0, np.int64) for _ in range(n_train)]   # their (type, value) codes per example
        out = {}
        for r in tabs.itertuples():
            if r.point != 0:
                continue
            types = ["Pose" if x.startswith("Pose") else x for x in r.column_types]
            sp = D.spans(types)
            keep = [c for c, ty in enumerate(types) if ty not in ("Example", "Unit")]
            ktypes = [types[c] for c in keep]
            exc = [c for c, ty in enumerate(types) if ty == "Example"]
            f = dict(seen=1.0, width=float(r.width), columns=float(len(keep)), box=float(ktypes.count("Box")),
                     color=float(ktypes.count("Color")), number=float(ktypes.count("Number")),
                     ident=float(ktypes.count("Ident")), orient=float(sum(t in ORIENT for t in ktypes)),
                     example=float(bool(exc)), depth=float(r.depth),
                     det=float(f"slot {r.relation}" in list(r.det_relations)), dets=float(len(r.det_relations)))
            unseen = isinstance(r.fault, str) or r.projections == 1
            counts = np.zeros(n_train)
            rows = [[] for _ in range(n_train)]
            readable = fh is not None
            for j in by_table.get(r.table, []):
                ek, ei, kd, n = int(ents["example_kind"][j]), int(ents["example_index"][j]), int(ents["kind"][j]), int(ents["rows"][j])
                if ek == 2 or (ek == 1 and ei >= n_train):
                    continue
                if kd >= 2:   # undefined, stopped, an example's fault, no entries
                    unseen = True
                    continue
                at = range(n_train) if ek == 0 else [ei]
                if kd != 0 or n > VALUE_ROWS:   # a Count entry, or too many rows to read
                    readable = False
                    for e in at:
                        counts[e] = max(counts[e], n)
                    continue
                o, w = int(ents["offset"][j]), int(r.width)
                if whole is not None:
                    a = whole[o:o + n * w].reshape(n, w)
                else:
                    fh.seek(4 * o)
                    a = np.frombuffer(fh.read(4 * n * w), np.int32).reshape(n, w)
                if ek == 0 and exc:   # a task-wide entry's row counts at the example of its first Example column
                    for e in range(n_train):
                        s = a[a[:, sp[exc[0]][0]] == e]
                        counts[e] = max(counts[e], len(s)); rows[e].append(s)
                else:
                    for e in at:
                        counts[e] = max(counts[e], n); rows[e].append(a)
            f["unseen"] = float(unseen)
            if not unseen:
                f.update(empty=float(counts.max() == 0), zero_some=float(counts.min() == 0),
                         log_rows=math.log1p(counts.mean()))
                if readable and ktypes:
                    x = Rows(ktypes, [np.concatenate(z)[:, np.concatenate([np.arange(*sp[c]) for c in keep])]
                                      if z else None for z in rows])
                    if x.full:
                        f["const_share"] = x.const_share
                        f["restates"] = float(any(x.restates(y) for y in earlier))
                        f["new_values"] = float(np.mean([1 - np.isin(v, h).mean()
                                                         for v, h in zip(x.values, held) if v.size]))
                        if r.table != 1:   # ex_output stays out of the earlier tables, as in detectors.py
                            earlier.append(x)
                            held = [np.union1d(h, v) for h, v in zip(held, x.values)]
            if r.relation >= 0:
                out[int(r.relation)] = [f.get(n, math.nan) for n in TABLE_FEATURES]
        if fh is not None:
            fh.close()
        return out


_TYPE_CODE = {}


class Rows:
    """The rows of a table at each train example (int32 [n, width] arrays over its columns `types`, or None), with
    the (type, value) pairs of each example as sorted int64 codes (`values`), and the keyed rows of
    detectors.restates, built where a test needs them."""
    def __init__(self, types, rows):
        import detectors as D
        self.types, sp = types, D.spans(types)
        tc = [_TYPE_CODE.setdefault(t, len(_TYPE_CODE)) for t in types]
        self.rows = [a if a is not None else np.zeros((0, sp[-1][1]), np.int32) for a in rows]
        self.full = sum(len(a) > 0 for a in self.rows)
        self.values, single, self.distinct = [], [], []
        for a in self.rows:
            codes = np.zeros((len(a), len(types)), np.int64)
            for j, ((lo, hi), t) in enumerate(zip(sp, tc)):
                c = a[:, lo].astype(np.int64)
                for k in range(lo + 1, hi):
                    c = c * 1000003 + a[:, k]
                codes[:, j] = c * 64 + t
            self.values.append(np.unique(codes))
            row = codes[:, 0].copy()
            for j in range(1, len(types)):
                row = row * 998244353 + codes[:, j]
            self.distinct.append(len(np.unique(row)))
            if len(a):
                single.append((codes == codes[0]).all(axis=0))
        self.const_share = float(np.mean(np.all(single, axis=0))) if single else math.nan
        self._keyed = None

    def keyed(self):
        if self._keyed is None:
            self._keyed = {e: frozenset(map(tuple, a.tolist())) for e, a in enumerate(self.rows)}
        return self._keyed

    def restates(self, y):
        """detectors.restates of these rows against y's, tested where y has each column type of these rows, as many
        distinct rows and each (type, value) pair at every example."""
        import detectors as D
        if not set(self.types) <= set(y.types) or any(a > b for a, b in zip(self.distinct, y.distinct)):
            return False
        if any(len(v) > len(w) for v, w in zip(self.values, y.values)):
            return False
        if not all(np.isin(v, w, assume_unique=True).all() for v, w in zip(self.values, y.values)):
            return False
        return D.restates(self.types, self.keyed(), y.types, y.keyed())


_SOURCES = {}


def tables_cache(out, tables):
    key = hashlib.sha256(f"{file_sha(Path(tables) / 'tables.parquet')} {file_sha(Path(tables) / 'index.parquet')} "
                         f"{TABLES_VERSION}".encode()).hexdigest()[:16]
    return Path(out) / "models" / f"tables-{key}.pkl"


def table_source(d, out=None):
    """The TableSource of export d, one per process; with `out`, cached in <out>/models/tables-<key>.pkl."""
    if str(d) not in _SOURCES:
        _SOURCES[str(d)] = TableSource(d, tables_cache(out, d) if out else None)
    return _SOURCES[str(d)]


_STREAMS = {}


def corpus_stream(corpus_dir, task, case):
    """(ids, model) of the case of a cases.npz, as lists, or None where it holds no such case."""
    if str(corpus_dir) not in _STREAMS:
        z = np.load(Path(corpus_dir) / "cases.npz")
        at = {k: j for j, k in enumerate(zip(z["task"].tolist(), z["case"].tolist()))}
        _STREAMS[str(corpus_dir)] = (at, z["ids"], z["model"], z["offsets"])
    at, ids, model, off = _STREAMS[str(corpus_dir)]
    j = at.get((task, case))
    return None if j is None else (ids[off[j]:off[j + 1]].tolist(), model[off[j]:off[j + 1]].astype(int).tolist())


def declarations(rel_k, task, case, ids, model):
    """(task, case, k, the index of the last model-written token before it) of each relation `&r<k>` the stream
    declares; rel_k gives k per vocabulary id, -1 for any other id."""
    out, last = [], -1
    for j, (i, m) in enumerate(zip(ids, model)):
        if m:
            last = j
        elif rel_k[i] >= 0:
            out.append((task, case, int(rel_k[i]), last))
    return out


def gold_tables(task, case, ids, model, a, rel_k):
    """(the relation features of the gold case's tables, where they come from), from `gold_source`."""
    src, how = gold_source(task, case, ids, model, a, rel_k)
    return src.features(task, case), how


def gold_source(task, case, ids, model, a, rel_k):
    """(the TableSource of the gold case's tables, where they come from): --tables where --corpus's cases.npz holds
    the case with the same stream and each relation the stream declares has no table there or one whose token
    matches (`TableSource.match`), else one replay of the stream by tables_export (`export_streams`), kept in
    <out>/tables/<task>-<sha of the stream>."""
    mm = [int(m) for m in model]
    if corpus_stream(a.corpus, task, case) == (list(ids), mm):
        src = TableSource(a.tables, task=task)
        if not src.match(declarations(rel_k, task, case, ids, mm))["differs"]:
            return src, "export"
    d = Path(a.out) / "tables" / f"{task}-{hashlib.sha256(json.dumps([list(ids), mm]).encode()).hexdigest()[:12]}"
    if not (d / "tables.parquet").exists():
        sys.path.insert(0, str(pinned.PIN / "engine/arclog-py") if (pinned.PIN / "pin.json").exists() else str(ROOT / "engine/arclog-py"))
        import tables_export
        tmp = d.with_name(f"{d.name}.{os.getpid()}.tmp")
        shutil.rmtree(tmp, ignore_errors=True)
        import contextlib, io
        with contextlib.redirect_stdout(io.StringIO()):
            tables_export.export_streams(str(tmp), task, [(list(ids), mm)], names=[case])
        try:
            tmp.rename(d)
        except OSError:   # another process wrote it first
            shutil.rmtree(tmp, ignore_errors=True)
    return TableSource(d), "replay"


# ------------------------------------------------------------------ the rows of a case's relations

_PORTS, _FORMS, _DOMAIN_COLUMNS, _WIDTHS, _DETERMINED, _FILTERS = {}, [], {}, {}, {}, {}


def registry_forms():
    """The top-level forms of engine/lib/registry.sexpr, each a nested list of its tokens."""
    if not _FORMS:
        import re
        text = re.sub(r";[^\n]*", "", (ROOT / "engine/lib/registry.sexpr").read_text())
        stack = [[]]
        for tok in re.findall(r'"(?:[^"\\]|\\.)*"|[()]|[^\s()]+', text):
            if tok == "(":
                stack.append([])
            elif tok == ")":
                x = stack.pop()
                stack[-1].append(x)
            else:
                stack[-1].append(tok)
        _FORMS.extend(stack[0])
    return _FORMS


def domain_columns():
    """{lib relation or macro name: the indexes of its columns of a finite domain type}. The finite domain types are
    the engine's orientation types (`arclog.orientation_types`, as ORIENT_DOMAIN gives them); a `(pose-or D4)` column
    is a D4 column. A macro's column takes the types of the sites of its variable in the macro's body."""
    if not _DOMAIN_COLUMNS:
        types = {}   # {relation or macro: [the types of each column]}
        macros = {}
        for form in registry_forms():
            if form and form[0] == "relation":
                cols = next(p for p in form if isinstance(p, list) and p and p[0] == "columns")[1:]
                types[form[1]] = [{c[1][-1] if isinstance(c[1], list) else c[1]} for c in cols]
            elif form and form[0] == "macro":
                cols = next(p for p in form if isinstance(p, list) and p and p[0] == "columns")[1:]
                macros[form[1]] = ([c[1] for c in cols], [x for x in form[2:] if not (x and x[0] == "columns")])
                types[form[1]] = [set() for _ in cols]

        def sites(body):   # (relation, column name, variable) of each one-label site of the atoms of a body
            for x in body:
                if not isinstance(x, list) or not x:
                    continue
                if isinstance(x[0], str) and x[0] in types:
                    for site in x[1:]:
                        if isinstance(site, str):
                            yield x[0], site.lstrip("*^"), site.lstrip("*^")
                        elif len(site) == 2 and isinstance(site[1], str):
                            yield x[0], site[0][1:], site[1].lstrip("*^")
                else:
                    yield from sites(x)
        names = {f[1]: [c[0] for c in next(p for p in f if isinstance(p, list) and p and p[0] == "columns")[1:]]
                 for f in registry_forms() if f and f[0] in ("relation", "macro")}
        grew = True
        while grew:
            grew = False
            for m, (vars_, body) in macros.items():
                got = defaultdict(set)
                for rel, col, var in sites(body):
                    if col in names[rel]:
                        got[var] |= types[rel][names[rel].index(col)]
                for j, var in enumerate(vars_):
                    if not got[var] <= types[m][j]:
                        types[m][j] |= got[var]; grew = True
        for rel, ts in types.items():
            _DOMAIN_COLUMNS[rel] = {j for j, t in enumerate(ts) if t & ORIENT_DOMAIN}
            _WIDTHS[rel] = len(ts)
    return _DOMAIN_COLUMNS


def determined():
    """{(lib relation or macro, column): the sets of its other columns that determine the column}, for each relation
    whose columns are all of a finite domain type (`domain_columns`). The engine counts the rows of a one-atom body
    with a fresh site on each column of a set, on the first task of data/tasks (the lib's relations do not read the
    task): a set X determines column c where X with c has as many rows as X alone, and the empty set where c has
    one row. A relation with a column of another type, or one the engine refuses or does not count, is in none.
    `filters()` gives, from the same counts, the sets X that filter c: X with c has fewer rows than X alone times c
    alone, so a value of X leaves c some of its values only."""
    if not _DETERMINED:
        import itertools, arclog
        task = sorted((ROOT / "data/tasks").glob("*.json"))[0]
        session = arclog.Session(arclog.Task.from_json(task.read_text(), arclog.World.Closed), arclog.DecodeSettings())
        voc = session.vocabulary
        ids = {voc.name(i): i for i in range(len(voc))}
        star = ids["*"]

        def count(rel, cols):
            d = session.decoder()
            try:
                for t in [ids["RULE"], ids[rel]] + [x for c in cols for x in (ids[f":{c}"], star)]:
                    d.step(t)
                got = {n for a in d.counts() or [] for n in a.values if n is not None}
            except (arclog.Refusal, arclog.Fault, KeyError):
                return None
            return got.pop() if len(got) == 1 else None
        for rel, dom in domain_columns().items():
            if not dom or len(dom) != _WIDTHS[rel]:
                continue
            n = {(): 1}
            for k in range(1, len(dom) + 1):
                for x in itertools.combinations(sorted(dom), k):
                    n[x] = count(rel, x)
            for c in dom:
                _DETERMINED[rel, c] = [set(x) for x in n if c not in x and n[x] is not None
                                       and n[x] == n[tuple(sorted(x + (c,)))]]
                _FILTERS[rel, c] = [set(x) for x in n if c not in x and None not in (n[x], n[c,])
                                    and n[tuple(sorted(x + (c,)))] is not None
                                    and n[tuple(sorted(x + (c,)))] < n[x] * n[c,]]
    return _DETERMINED


def filters():
    """{(lib relation or macro, column): the sets of its other columns that filter the column} (`determined`)."""
    determined()
    return _FILTERS


def registry_ports():
    """{component: (outputs, inputs)} of engine/lib/registry.sexpr, each port (its name, its column names)."""
    if not _PORTS:
        for form in registry_forms():
            if form and form[0] == "component":
                got = {}
                for part in form:
                    if isinstance(part, list) and part and part[0] in ("inputs", "outputs"):
                        got[part[0]] = [(p[0], [x[0] for x in p[1:] if isinstance(x, list) and len(x) == 2
                                                and all(isinstance(y, str) for y in x) and x[0] not in ("copies", "default")])
                                        for p in part[1:] if isinstance(p, list)]
                _PORTS[form[1]] = (got.get("outputs", []), got.get("inputs", []))
    return _PORTS


def parse_arg(names, kinds, toks, i):
    n = names[toks[i]]
    if n in ("*", "^"):
        return ("fresh", toks[i + 1]), i + 2
    if kinds[toks[i]] == "label":
        return ("join", toks[i]), i + 1
    if n == "0":
        return ("lit",), i + 1
    raise ValueError(f"no argument at {n}")


def parse_conjunct(names, kinds, toks, i):
    """One conjunct of a clause's tokens (the engine's tokens included) from toks[i]: (the conjunct, the index after
    it). A conjunct is ("atom", relation id, sites), ("not", conjunct), ("cmp", args), or ("or" | "if" | "all",
    lists); a site is (column, arg) or (column, [(field, arg), ...]); an arg is ("fresh", label), ("join", label) or
    ("lit",). Raises ValueError or IndexError on tokens it does not read."""
    n, k = names[toks[i]], kinds[toks[i]]
    if n == "NOT":
        inner, i = parse_conjunct(names, kinds, toks, i + 1)
        return ("not", inner), i
    if k in ATOM_HEADS:
        rel, i, sites = toks[i], i + 1, []
        while kinds[toks[i]] == "column":
            c, i = int(names[toks[i]][1:]), i + 1
            if kinds[toks[i]] == "column":
                fields = []
                while kinds[toks[i]] == "column":
                    f = int(names[toks[i]][1:])
                    arg, i = parse_arg(names, kinds, toks, i + 1)
                    fields.append((f, arg))
                if names[toks[i]] != "END":
                    raise ValueError("a site's fields end in END")
                sites.append((c, fields))
                i += 1
            else:
                arg, i = parse_arg(names, kinds, toks, i)
                sites.append((c, arg))
        return ("atom", rel, sites), i
    if n in COMPARISONS:
        a1, i = parse_arg(names, kinds, toks, i + 1)
        a2, i = parse_arg(names, kinds, toks, i)
        return ("cmp", [a1, a2], n), i
    if n in ("OR", "IF", "ALL"):
        lists, i = [], i + 1
        while True:
            body, i = parse_list(names, kinds, toks, i, ("END", "ALSO") if n == "OR" else ("END",))
            lists.append(body)
            i += 1
            if (names[toks[i - 1]] == "END") if n == "OR" else len(lists) == (3 if n == "IF" else 2):
                return (n.lower(), lists), i
    raise ValueError(f"no conjunct at {n}")


def parse_list(names, kinds, toks, i, stops):
    """The conjuncts from toks[i] up to a token of `stops` at their level: (the conjuncts, the stop's index)."""
    out = []
    while names[toks[i]] not in stops:
        node, i = parse_conjunct(names, kinds, toks, i)
        out.append(node)
    return out, i


def site_args(sites):
    """(column, the field indexes or None, the arg) of each argument of an atom's sites."""
    for c, arg in sites:
        if isinstance(arg, list):
            for f, x in arg:
                yield c, [f], x
        else:
            yield c, None, arg


def body_labels(body):
    out = set()
    for node in body:
        if node[0] == "atom":
            out |= {x[1] for _, _, x in site_args(node[2]) if len(x) == 2}
        elif node[0] == "cmp":
            out |= {x[1] for x in node[1] if len(x) == 2}
        elif node[0] == "not":
            out |= body_labels([node[1]])
        else:
            for body2 in node[1]:
                out |= body_labels(body2)
    return out


def made_labels(body):
    """The labels a body keeps, in order, as the engine's `made_labels` gives them: each a site or a `=` of its own
    list makes, and each an `OR` or an `IF` of its own list exports. A derived relation's column token k reads the
    k-th of its clause's."""
    out = []
    for node in body:
        if node[0] in ("atom", "cmp"):
            args = [x for _, _, x in site_args(node[2])] if node[0] == "atom" else node[1]
            got = [x[1] for x in args if x[0] == "fresh"]
        elif node[0] in ("or", "if"):
            first, later = (node[1][0], node[1][1:]) if node[0] == "or" else (node[1][1], node[1][2:])
            named = [body_labels(b) for b in later]
            got = [x for x in made_labels(first) if all(x in s for s in named)]
        else:
            got = []
        out += [x for x in got if x not in out]
    return out


def equal_classes(body, out=None):
    """{label: the labels a `=` of the body, at any depth, makes equal to it, itself included}."""
    out = {} if out is None else out
    for node in body:
        if node[0] == "cmp" and node[2] == "=" and all(len(x) == 2 for x in node[1]):
            a, b = (x[1] for x in node[1])
            merged = out.get(a, {a}) | out.get(b, {b})
            for x in merged:
                out[x] = merged
        elif node[0] == "not":
            equal_classes([node[1]], out)
        elif node[0] in ("or", "if", "all"):
            for body2 in node[1]:
                equal_classes(body2, out)
    return out


def positive_atoms(body, path=(), out=None):
    """{path: (relation id, sites)} of the positive atoms of a body outside `NOT` and `ALL`, a path as the export's
    flows give an atom's after the form and its clause: the conjunct's place, then a branch's or a list's and the
    conjunct's place in it."""
    out = {} if out is None else out
    for j, node in enumerate(body):
        if node[0] == "atom":
            out[path + (j,)] = (node[1], node[2])
        elif node[0] in ("or", "if"):
            for b, body2 in enumerate(node[1]):
                positive_atoms(body2, path + (j, b), out)
    return out


class CaseRows:
    """The rows of the relations `&r<k>` of one case of a TableSource, for the normal form's one-row test
    (`one_row`). A relation's table holds its columns in the engine's canonical order, which can differ from the
    order of its column tokens (the labels of its clause, `made_labels`); the table's copy flows (flows.parquet)
    give, for each table column, the atoms of the clause it is read from, and so the clause label it holds. A
    column token is mapped to every table column that its label's sites explain, or to all columns where none
    does, so a read's projection holds at least the columns it reads."""
    def __init__(self, src, task, case, ids, model, names, kinds):
        self.src, self.task, self.case, self.names, self.kinds = src, task, case, names, kinds
        self.lays, self.stream, self.ok = {}, (ids, model), None

    def setup(self):
        """Read the case's tables, entries and copy flows, and the form of each relation, at the first layout."""
        src, task, case, (ids, model), names, kinds = self.src, self.task, self.case, self.stream, self.names, self.kinds
        self.ok = (task, case) not in src.bad and (task, case) in src.t_at
        if not self.ok:
            return
        # {k: the tokens of the form after which the engine declares &r<k>}, {k: its place among the form's declarations}
        self.forms, self.place, cur = {}, {}, None
        for t, m in zip(ids, model):
            if m and (cur is None or cur[1]):
                cur = [[], False, 0]
            if cur is not None:
                cur[0].append(t)
                if not m and kinds[t] == "relation":
                    self.forms[int(names[t][2:])], self.place[int(names[t][2:])] = cur[0], cur[2]
                    cur[1], cur[2] = True, cur[2] + 1
        tabs = src.t.iloc[src.t_at[(task, case)]]
        tabs = tabs[tabs["point"] == 0]
        self.rel_of = dict(zip(tabs["table"].tolist(), tabs["relation"].tolist()))
        n_of = Counter(tabs["relation"].tolist())
        self.tabs = {int(r.relation): r for r in tabs.itertuples() if r.relation >= 0 and n_of[r.relation] == 1}
        ix = src.i_at.get((task, case), np.zeros(0, np.int64))
        self.ents = defaultdict(list)
        for tb, ek, ei, kd, n, o, en in zip(*(src.i[c][ix].tolist() for c in
                                              ["table", "example_kind", "example_index", "kind", "rows", "offset", "entry"])):
            self.ents[tb].append((ek, ei, kd, n, o, en))
        fl, at = src.flows()
        fx = at.get((task, case), np.zeros(0, np.int64))
        self.flows = defaultdict(list)   # {(table, column): [(atom path, source table, source relation, source column)]}
        for tb, col, st, sr, sc, det, atom in zip(*(fl[c][fx].tolist() for c in ["table", "column", "source_table",
                                                    "source_relation", "source_column", "det", "atom"])):
            parts = atom.split(".") if atom else []
            if len(parts) >= 3:   # a DET's source column (det >= 0) is into the DET's own columns: not read
                self.flows[tb, col].append((tuple(int(p) for p in parts[2:]), st, sr, sc if det < 0 else None))

    def layout(self, k):
        """The table of relation k as the test reads it, or None where the case gives none."""
        if k in self.lays:
            return self.lays[k]
        if self.ok is None:
            self.setup()
        lay = None
        r = self.tabs.get(k) if self.ok else None
        if r is not None and not isinstance(r.fault, str) and k in self.forms and self.ents.get(r.table):
            import detectors as D
            types = ["Pose" if x.startswith("Pose") else x for x in r.column_types]
            groups, prev = [], None
            for j, name in enumerate(r.column_names):
                head = name.split(".")[0] if "." in name else None
                if head is not None and head == prev:
                    groups[-1][1].append(j)
                else:
                    groups.append((name if head is None else head, [j]))
                prev = head
            toks = self.forms[k]
            first = self.names[toks[0]]
            lay = dict(table=r.table, types=types, spans=D.spans(types), width=int(r.width), groups=groups,
                       entries=self.ents[r.table], per_input=any(e[0] != 0 for e in self.ents[r.table]),
                       example=types.index("Example") if "Example" in types else None, head=first, kind=None, at={})
            if len(types) == len(r.column_names):
                if first in ("RULE", "DET") and len(toks) > 1 and self.kinds[toks[1]] == "proposer":
                    lay["kind"] = "proposer"
                elif first == "INIT":   # its outputs, then each input whose name no output shares
                    outs, ins = registry_ports().get(self.names[toks[1]], ([], []))
                    ports = outs + [p for p in ins if p[0] not in {o[0] for o in outs}]
                    port = ports[self.place[k]][1] if self.place[k] < len(ports) else None
                    held = [g[0] for g in groups]
                    if port is not None and held == [x for x in port if x in held]:
                        lay.update(kind="instance", port=port)
                elif first in ("RULE", "DET"):
                    try:
                        body, _ = parse_list(self.names, self.kinds, toks, 1, ("END", "SET", "ONE"))
                    except (ValueError, IndexError):
                        body = None
                    if body is not None:
                        lay.update(kind="body", labels=made_labels(body), atoms=positive_atoms(body),
                                   equal=equal_classes(body))
        self.lays[k] = lay
        return lay

    def columns(self, k, c, fields, head):
        """The table columns of relation k that a site on its column token c reads in a clause of `head` (fields:
        the field indexes the site reads, or None): a set, "E" for the Example column of a lifted read (a DET
        clause's, or a form's other than RULE, of a per-input relation), or None where unknown."""
        lay = self.layout(k)
        if lay is None:
            return None
        if head in ("DET", "INIT", "CHOOSE", "RIGID_DET") and lay["per_input"]:   # column token 0 is the Example column
            if c == 0:
                return "E"
            c -= 1
        groups = lay["groups"]
        if lay["kind"] == "proposer":
            gs = {c}
        elif lay["kind"] == "instance":   # the registry's columns of the port; the table drops one of no field
            if c >= len(lay["port"]):
                return None
            gs = {g for g, (name, _) in enumerate(groups) if name == lay["port"][c]}
            if not gs:
                return set()
        elif lay["kind"] == "body":
            if c not in lay["at"]:
                lay["at"][c] = self.body_groups(k, lay, c)
            gs = lay["at"][c]
        else:
            return None
        if gs is None or not all(0 <= g < len(groups) for g in gs):
            return None
        if fields and len(gs) == 1:
            cols = groups[next(iter(gs))][1]
            return {cols[f] for f in fields} if all(f < len(cols) for f in fields) else None
        return {j for g in gs for j in groups[g][1]}

    def body_groups(self, k, lay, c):
        """The column groups of relation k (declared by a clause with a body) whose copy flows the sites of its
        clause's label at column token c explain; None where there is no such label or no such group."""
        labels = lay["labels"]
        if len(labels) != len(lay["groups"]) or c >= len(labels):
            return None
        label = labels[c]
        out = set()
        for g, (_, cols) in enumerate(lay["groups"]):
            if all(self.explains(lay, (lay["table"], j), label) for j in cols):
                out.add(g)
        return out or None

    def explains(self, lay, key, label):
        """Whether each copy flow of a table column, at an atom of the clause, comes from a site there of `label` or
        of a label a `=` makes equal to it."""
        same = lay["equal"].get(label, {label})
        for path, st, sr, sc in self.flows.get(key, ()):
            atom = lay["atoms"].get(path)
            if atom is None:
                continue
            rel, sites = atom
            if not any(len(x) == 2 and x[1] in same and self.source_is(lay["head"], rel, c, f, st, sr, sc)
                       for c, f, x in site_args(sites)):
                return False
        return True

    def source_is(self, head, rel, c, f, st, sr, sc):
        kind, name = self.kinds[rel], self.names[rel]
        if kind == "fact relation":
            return sc == c + (name == "input")
        if kind == "lib relation":
            return sr == name and sc == c
        if kind == "relation":
            k2 = int(name[2:])
            if self.rel_of.get(st) != k2:
                return False
            m = self.columns(k2, c, f, head)
            return sc is None or (sc == -2 if m == "E" else m is None or sc in m)
        return True

    def rows(self, lay, e):
        ek, ei, kd, n, o, en = e
        with open(self.src.d / "values" / self.task / f"{self.case}.i32", "rb") as fh:
            fh.seek(4 * o)
            return np.frombuffer(fh.read(4 * n * lay["width"]), np.int32).reshape(n, lay["width"])

    def distinct(self, lay, cols, group=None, pooled=False):
        """The most distinct rows of the table's projection onto `cols` at an input and a DET assignment: per entry
        (one per input, assignment and model); at each Example value of the column `group`; where `pooled`, over the
        entries of one assignment at all inputs together. None where an entry gives no rows to read."""
        sp = lay["spans"]
        cells = [j for t in sorted(cols) for j in range(*sp[t])]
        keys = list(range(*sp[group])) if group is not None else []
        assign = self.src.assignments(self.task, self.case) if pooled else {}
        best, union, counted = 0, defaultdict(list), Counter()
        for e in lay["entries"]:
            ek, ei, kd, n, o, en = e
            if kd >= 2 or (kd == 1 and n > 1):
                return None   # undefined, stopped or faulted, or a count with no rows to project
            if n == 0:
                continue
            if kd == 1 or (n == 1 and not pooled):
                if pooled:
                    counted[assign.get(en, frozenset())] += 1
                best = max(best, n)
                continue
            a = self.rows(lay, e)[:, keys + cells]
            p = np.unique(a, axis=0) if a.shape[1] else a[:1]
            if pooled:
                union[assign.get(en, frozenset())].append(p)
                continue
            if keys:
                _, per = np.unique(p[:, :len(keys)], axis=0, return_counts=True)
                best = max(best, int(per.max()) if cells else 1)
            else:
                best = max(best, len(p) if cells else 1)
            if best > 1:
                return best
        if any(c and (c > 1 or union.get(w)) for w, c in counted.items()):
            return None   # a count of one row beside other rows of the assignment
        for arrs in union.values():
            p = np.concatenate(arrs)
            best = max(best, (len(np.unique(p, axis=0)) if p.shape[1] else 1))
        return best

    def one_row(self, k, sites, head):
        """Whether a positive read of `&r<k>` in a clause of `head`, on its sites [(column token, field indexes or
        None)], has at most one distinct row at every input: the task input and each example, or once for a
        task-wide table (a lifted read in a DET clause: at each example where it names the Example column, else
        over all of them)."""
        lay = self.layout(k)
        if lay is None:
            return False
        cols, named_e, group = set(), False, None
        for c, fields in sites:
            m = self.columns(k, c, fields, head)
            if m == "E":
                named_e = True
            elif m is None:
                cols, group = set(range(len(lay["types"]))), None
                break
            else:
                if lay["example"] is not None and m == {lay["example"]}:
                    group = lay["example"]
                cols |= m
        lifted = head == "DET" and lay["per_input"]
        if group is not None:
            cols.discard(group)
        d = self.distinct(lay, cols, group, pooled=lifted and not named_e)
        return d is not None and d <= 1


# ------------------------------------------------------------------ the scorers

class Ngram:
    """Interpolated Kneser-Ney of order 3 over skeletons."""
    def __init__(self, n_sk):
        self.V = n_sk

    def fit(self, seqs):
        c3 = defaultdict(Counter)
        for s in seqs:
            p = [0, 0] + s
            for j in range(2, len(p)):
                c3[(p[j - 2], p[j - 1])][p[j]] += 1
        self.c3 = {k: dict(v) for k, v in c3.items()}
        self.c3tot = {k: sum(v.values()) for k, v in c3.items()}
        cont2 = defaultdict(Counter)   # N1+(. v w)
        for (u, v), ws in c3.items():
            for w in ws:
                cont2[v][w] += 1
        self.cont2 = {k: dict(v) for k, v in cont2.items()}
        self.cont2tot = {k: sum(v.values()) for k, v in cont2.items()}
        cont1 = Counter()   # N1+(. w) over the bigram types
        for v, ws in cont2.items():
            for w in ws:
                cont1[w] += 1
        self.cont1, self.cont1tot = dict(cont1), sum(cont1.values())
        return self

    def p1(self, w):
        return (max(self.cont1.get(w, 0) - DISCOUNT, 0) + DISCOUNT * len(self.cont1) / self.V) / self.cont1tot

    def p2(self, w, v):
        t = self.cont2tot.get(v)
        if not t:
            return self.p1(w)
        c = self.cont2[v]
        return (max(c.get(w, 0) - DISCOUNT, 0) + DISCOUNT * len(c) * self.p1(w)) / t

    def p3(self, w, u, v):
        t = self.c3tot.get((u, v))
        if not t:
            return self.p2(w, v)
        c = self.c3[(u, v)]
        return (max(c.get(w, 0) - DISCOUNT, 0) + DISCOUNT * len(c) * self.p2(w, v)) / t

    def scores(self, ctxs, cands):
        """[np.array of log-probabilities] per (context, candidates); a context is (hist, k, index, n_rel, n_lab)."""
        out = []
        for (hist, *_), cs in zip(ctxs, cands):
            u, v = ([0, 0] + hist)[-2:]
            out.append(np.log([self.p3(w, u, v) for w in cs]))
        return out


def features(hist, k, index, n_rel, n_lab, cand):
    h = [0, 0, 0] + hist
    return [h[-3], h[-2], h[-1], cand, k, index, n_rel, n_lab]


def expand(sk, ids, x):
    """The candidates of the scorer `tables`: (skeleton index, vocabulary id) of each candidate, with the class
    RELATION replaced by each relation of x["rels"]; the class LABEL keeps the id -1."""
    out = []
    for s, i in zip(sk, ids):
        if s == 1:
            out += [(1, r) for r in x["rels"]]
        else:
            out.append((s, i))
    return out


def rel_vector(x, r, rel_k):
    """The values of REL_FEATURES of relation r (a vocabulary id) in context x; every value missing for None."""
    if r is None:
        return [math.nan] * len(REL_FEATURES)
    k = int(rel_k[r])
    f = NO_TABLE if x["feats"] is None else x["feats"].get(k, UNSEEN_TABLE)
    return f + [x["n_rel"] - 1 - k, x["uses"].get(r, 0), x["heads"].get(r, 5)]


NO_TABLE = [math.nan] * len(TABLE_FEATURES)   # the case has no tables in the export
UNSEEN_TABLE = [0.0] + [math.nan] * (len(TABLE_FEATURES) - 1)   # the case has no table of the relation


class Trees:
    kind, expanded = "trees", False
    categorical = [0, 1, 2, 3]

    def row(self, ctx, c):
        return features(*ctx[:5], c)

    def candidates(self, sk, ids, x):
        return sk

    def gold(self, g, tok):
        return g

    def fit(self, corpus, clauses, rng, source=None):
        from sklearn.ensemble import HistGradientBoostingClassifier
        X, y = [], []
        order = list(range(len(clauses)))
        rng.shuffle(order)
        for x in order:
            for ctx, sk, g, tok in corpus.walk(clauses[x], source):
                cs, gold = self.candidates(sk, sk, ctx[5]), self.gold(g, tok)
                others = [c for c in cs if c != gold]
                neg = rng.sample(others, min(NEGATIVES, len(others)))
                for c in [gold] + neg:
                    X.append(self.row(ctx, c)); y.append(int(c == gold))
            if len(X) >= ROWS:
                break
        self.rows = len(X)
        self.m = HistGradientBoostingClassifier(categorical_features=self.categorical, **TREES).fit(
            np.array(X, dtype=float), np.array(y))
        return self

    def matrix(self, ctxs, cands):
        """The rows of the candidates of each context, in order, as one float array."""
        return np.array([self.row(ctx, c) for ctx, cs in zip(ctxs, cands) for c in cs], dtype=float)

    def decision(self, X):
        """self.m.decision_function(X), with the same floats, without sklearn's checks of X on each call: X's
        categorical columns through the fit's OrdinalEncoder (an unknown value or NaN gives NaN), first, then its
        other columns, as the fit's ColumnTransformer orders them; then the baseline plus each tree's leaf value,
        in tree order."""
        if not hasattr(self, "_trees"):
            m = self.m
            (_, enc, cat), (_, _, num) = m._preprocessor.transformers_[:2]
            known, f_idx = m._bin_mapper.make_known_categories_bitsets()
            self._trees = (np.flatnonzero(cat), enc.categories_, np.flatnonzero(num), known, f_idx,
                           float(m._baseline_prediction[0, 0]),
                           [(p.nodes, p.raw_left_cat_bitsets) for (p,) in m._predictors])
        from sklearn.ensemble._hist_gradient_boosting._predictor import _predict_from_raw_data
        cat, cats, num, known, f_idx, base, trees = self._trees
        Xt = np.empty_like(X)
        for j, (c, cs) in enumerate(zip(cat, cats)):
            k = np.searchsorted(cs, X[:, c]).clip(0, len(cs) - 1)
            Xt[:, j] = np.where(cs[k] == X[:, c], k, np.nan)
        Xt[:, len(cat):] = X[:, num]
        raw, out = np.zeros(len(X)) + base, np.empty(len(X))
        for nodes, left in trees:
            _predict_from_raw_data(nodes, Xt, left, known, f_idx, 1, out)
            raw += out
        return raw

    def scores(self, ctxs, cands):
        if not any(cands):
            return [np.zeros(0) for _ in cands]
        s = self.decision(self.matrix(ctxs, cands))
        out, j = [], 0
        for cs in cands:
            out.append(s[j:j + len(cs)]); j += len(cs)
        return out


class TableTrees(Trees):
    """The scorer `tables`: Trees on the candidates of `expand`, each row with the features of the candidate's
    relation and of the relation the clause refers to last (`rel_vector`)."""
    kind, expanded = "tables", True
    H = REL_FEATURES.index("head")
    categorical = [0, 1, 2, 3, 8 + H, 8 + len(REL_FEATURES) + H]

    def __init__(self, rel_k):
        self.rel_k = rel_k

    def row(self, ctx, c):
        x = ctx[5]
        return (features(*ctx[:5], c[0]) + rel_vector(x, c[1] if c[0] == 1 else None, self.rel_k)
                + rel_vector(x, x["last"], self.rel_k))

    def matrix(self, ctxs, cands):
        """As Trees.matrix, with the features of the context and of its last relation written once per context."""
        n = len(REL_FEATURES)
        X = np.empty((sum(map(len, cands)), 8 + 2 * n))
        j = 0
        for ctx, cs in zip(ctxs, cands):
            x = ctx[5]
            b = X[j:j + len(cs)]
            b[:] = features(*ctx[:5], 0) + rel_vector(x, None, self.rel_k) + rel_vector(x, x["last"], self.rel_k)
            b[:, 3] = [c[0] for c in cs]
            for i, (s, r) in enumerate(cs):
                if s == 1:
                    b[i, 8:8 + n] = rel_vector(x, r, self.rel_k)
            j += len(cs)
        return X

    def candidates(self, sk, ids, x):
        return expand(sk, [-1] * len(sk), x)

    def gold(self, g, tok):
        return (g, tok if g == 1 else -1)


def model_path(out, kind, fold, corpus_dir, tables=None):
    extra = f" {file_sha(Path(tables) / 'tables.parquet')} {file_sha(Path(tables) / 'index.parquet')}" if kind == "tables" else ""
    key = hashlib.sha256(f"{file_sha(Path(corpus_dir) / 'cases.npz')} {file_sha(__file__)} {FIT_VERSION} {kind}{extra}".encode()).hexdigest()[:16]
    return Path(out) / "models" / f"{kind}-f{fold}-{key}.pkl"


def fit_model(kind, fold, corpus, tables=None, out=None):
    t0 = time.time()
    train = [c for c in corpus.clauses if c["fold"] != fold]
    if kind == "ngram":
        m = Ngram(len(corpus.vocab.sk_names)).fit([corpus.vocab.sk[c["toks"]].tolist() for c in train])
    elif kind == "trees":
        m = Trees().fit(corpus, train, random.Random(fold))
    else:
        src = table_source(tables, out)
        src.match(corpus.decls)
        m = TableTrees(corpus.vocab.rel_k).fit(corpus, train, random.Random(fold), src)
        src.save()
    m.fold, m.closers, m.median, m.seconds = fold, corpus.closers, corpus.median, time.time() - t0
    return m


def get_model(kind, fold, corpus_dir, out, vocab, corpus=None, tables=None):
    """The scorer `kind` of fold `fold`, from <out>/models where it is there, else fit and written there."""
    p = model_path(out, kind, fold, corpus_dir, tables)
    if p.exists():
        return pickle.loads(p.read_bytes()), corpus
    corpus = corpus or Corpus(corpus_dir, vocab)
    m = fit_model(kind, fold, corpus, tables, out)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(f".{time.time_ns()}.tmp")
    tmp.write_bytes(pickle.dumps(m))
    tmp.rename(p)
    return m, corpus


# ------------------------------------------------------------------ the shape of a clause

ATOM_HEADS = {"relation", "lib relation", "relation macro", "fact relation"}
LIB_HEADS = {"lib relation", "relation macro"}   # the lib's relations: not a program relation &r<k> or a fact relation
COMPARISONS = {"=", "!=", "<", "<=", ">", ">="}


class Shape:
    """The conjuncts of a clause, read token by token: `feed` takes each model-written token with the tokens the
    engine emits after it. A conjunct is a relation token (kinds relation, lib relation, relation macro, fact
    relation) and its arguments `:c ARG`, where ARG is `*` or `^` (a fresh variable: the engine emits its label), a
    label (a variable bound earlier), `0` (a literal), or a nested `:c ARG ... END`. It closes at the first token
    after an argument that is not a column, or where the engine declares the clause's relation. A column token that
    the engine emits starts a new segment (an INIT clause's part for one column); `key_seg` is the segment of an INIT
    clause's key clause, the one the engine's first column token starts, and None in a clause of another head. A comparison and the labels after
    it are a link (`links`: (segment, labels)). Each closed conjunct is a dict: rel (its relation token), args, fresh,
    lits (its `0` arguments), other (any other argument token), reads (the labels it reads), before (those of them
    bound before it), binds, neg (after NOT), first (the first of its segment), seg (its segment), full (it reads every
    column: the mask at the token that closes it admits no column; None where unknown), domain (its relation is an
    `_elem` lib relation or one that a DET clause declares, from `heads`), dup (an earlier conjunct of the clause
    reads its relation), sites (per site, [its column token's index, the indexes of the field tokens of a site on
    a record's fields, or None]), fresh_at (per `*` argument of a site with no fields, (its column token's index,
    the label it binds)), key_at (the same per `^` argument) and lit_at (the column token's index of each `0` argument
    of a site with no fields). `read` holds every label that a model-written token reads, in a conjunct, a comparison
    or a mark, and `reads` how many times; `eqs` holds the two arguments of each `=`, each a label or the `0` token,
    and whether the `=` makes its first label."""
    def __init__(self, v, heads=None):
        self.v, self.heads = v, heads or {}
        if not hasattr(v, "is_col"):
            v.is_col = np.array([k == "column" for k in v.kinds])
            v.is_head = np.array([k in ATOM_HEADS for k in v.kinds])
            v.tok = {n: i for i, n in enumerate(v.names) if n in ("*", "^", "0", "NOT", "END")}
            v.is_elem = np.array([k == "lib relation" and n.endswith("_elem") for n, k in zip(v.names, v.kinds)])
            dom = domain_columns()
            v.dom_cols = {i: dom[n] for i, (n, k) in enumerate(zip(v.names, v.kinds))
                          if k in LIB_HEADS and dom.get(n)}
        self.atoms, self.cur, self.bound, self.seg, self.neg, self.ended = [], None, set(), 0, False, False
        self.segno, self.links, self.link, self.key_seg = 0, [], None, None
        self.state, self.depth, self.fresh_col, self.key_col = None, 0, None, None
        self.eqs, self.eq = [], None   # the `=` comparisons read; the arguments of the open one
        self.read = set()   # the labels that a model-written token reads: at a site, in a comparison, in a mark
        self.reads = Counter()
        self.head, self.rows = None, None   # the clause's first token's name; a CaseRows of the prefix, for `normal_form`

    def closes(self, t):
        """Whether model token t closes the open conjunct."""
        return self.cur is not None and self.state == "cols" and self.depth == 0 and not self.v.is_col[t]

    def close(self, full=None):
        a = self.cur
        a["full"] = full
        a["domain"] = bool(self.v.is_elem[a["rel"]] or self.heads.get(a["rel"]) == HEADS["DET"])
        a["dup"] = any(b["rel"] == a["rel"] for b in self.atoms)
        self.atoms.append(a)
        self.bound |= a["binds"]
        self.seg += 1
        self.cur = None
        return a

    def feed(self, t, emitted, cols=None):
        """Read model token t and the tokens emitted after it; gives the conjunct t closes, or None. `cols`: whether
        the mask at t admits a column token (where t closes a conjunct, the conjunct reads every column where not)."""
        v, tk = self.v, self.v.tok
        if self.head is None:
            self.head = v.names[t]
        if v.is_lab[t]:
            self.read.add(t)
            self.reads[t] += 1
        closed = self.close(None if cols is None else not cols) if self.closes(t) else None
        if self.cur is None:
            if v.names[t] == "=":
                self.eq = []
            elif self.eq is not None and (v.is_lab[t] or t == tk.get("0")):
                self.eq.append((t, False))
            elif t != tk.get("*"):
                self.eq = None
            if v.is_head[t]:
                self.cur = dict(rel=t, args=0, fresh=0, lits=0, other=0, reads=set(), before=set(), binds=set(),
                                neg=self.neg, first=self.seg == 0, seg=self.segno, sites=[], fresh_at=[], site_labels=[],
                                key_at=[], lit_at=[])
                self.state, self.depth, self.neg, self.link = "cols", 0, False, None
            elif t == tk.get("NOT"):
                self.neg, self.link = True, None
            elif v.is_lab[t] and self.link is not None:
                self.link.add(t)
            elif v.names[t] in COMPARISONS:
                self.link = set()
                self.links.append((self.segno, self.link))
            elif t != tk.get("0"):
                self.link = None
        elif self.state == "arg":
            if v.is_col[t]:
                self.depth += 1
                if self.depth == 1:
                    self.cur["sites"][-1][1] = [int(v.names[t][1:])]
            else:
                a = self.cur
                a["args"] += 1
                if t in (tk.get("*"), tk.get("^")):
                    a["fresh"] += 1
                    if t == tk.get("*") and self.depth == 0:
                        self.fresh_col = a["sites"][-1][0]
                    elif self.depth == 0:
                        self.key_col = a["sites"][-1][0]
                elif v.is_lab[t]:
                    a["reads"].add(t)
                    if self.depth == 0:
                        a["site_labels"].append((a["sites"][-1][0], t))
                    if t in self.bound:
                        a["before"].add(t)
                elif t == tk.get("0"):
                    a["lits"] += 1
                    if self.depth == 0:
                        a["lit_at"].append(a["sites"][-1][0])
                else:
                    a["other"] += 1
                self.state = "cols"
        elif v.is_col[t]:
            self.state = "arg"
            if self.depth == 0:
                self.cur["sites"].append([int(v.names[t][1:]), None])
            elif self.depth == 1:
                self.cur["sites"][-1][1].append(int(v.names[t][1:]))
        elif t == tk.get("END") and self.depth > 0:
            self.depth -= 1
        for x in emitted:
            if v.is_lab[x]:
                (self.cur["binds"] if self.cur is not None else self.bound).add(x)
                if self.cur is not None and self.fresh_col is not None:
                    self.cur["fresh_at"].append((self.fresh_col, x))
                    self.cur["site_labels"].append((self.fresh_col, x))
                elif self.cur is not None and self.key_col is not None:
                    self.cur["key_at"].append((self.key_col, x))
                elif self.cur is None and self.eq is not None:
                    self.eq.append((x, True))
                self.fresh_col = self.key_col = None
            elif v.is_col[x]:
                if self.cur is not None:
                    closed = closed or self.close()
                self.seg, self.segno, self.link = 0, self.segno + 1, None
                if self.head == "INIT" and self.key_seg is None:
                    self.key_seg = self.segno
            elif v.is_rel[x] and not self.ended:
                self.ended = True
                if self.cur is not None:
                    closed = closed or self.close()
        self.fresh_col = self.key_col = None
        if self.eq is not None and len(self.eq) == 2:
            self.eqs.append((self.eq[0][0], self.eq[1][0], self.eq[0][1]))
            self.eq = None
        return closed

    def copy(self):
        """A copy that later feeds leave unchanged, taken before a conjunct opens."""
        c = copy.copy(self)
        c.atoms, c.cur, c.bound = [dict(a) for a in self.atoms], copy.deepcopy(self.cur), set(self.bound)
        c.links, c.link, c.read, c.reads = [(g, set(ls)) for g, ls in self.links], None, set(self.read), Counter(self.reads)
        c.eqs, c.eq = list(self.eqs), None if self.eq is None else list(self.eq)
        return c


# The structural constraints: each test reads a Shape, and a conjunct test also the conjunct `a` that has just
# closed. `constraints` prints each test's compliance on the corpus clauses by head.
def connected(s, a):   # a conjunct that is not its segment's first reads a variable bound before it
    return a["first"] or bool(a["before"])


def not_all_literal(s, a):
    return not (a["args"] and a["lits"] == a["args"])


def one_literal(s, a):
    return a["lits"] <= 1


def no_literal(s, a):
    return a["lits"] == 0


def no_self_join(s, a):
    return not a["dup"]


def graph_connected(s):   # in each segment, the conjuncts with arguments are one component of the join graph
    atoms = [a for a in s.atoms if a["args"]]
    for seg in {a["seg"] for a in atoms}:
        parts = [a["reads"] | a["binds"] for a in atoms if a["seg"] == seg]
        n = len(parts)
        parts += [set(ls) for g, ls in s.links if g == seg]
        comp, rest, grew = set(parts[0]), list(range(1, len(parts))), True
        while grew:
            grew = False
            for j in list(rest):
                if parts[j] & comp:
                    comp |= parts[j]; rest.remove(j); grew = True
        if any(j < n for j in rest):
            return False
    return True


def components(s, segs):
    """The components of the join graph of each segment of segs: lists of the conjuncts with arguments."""
    atoms = [a for a in s.atoms if a["args"]]
    out = []
    for seg in segs:
        mine = [a for a in atoms if a["seg"] == seg]
        parts = [a["reads"] | a["binds"] for a in mine] + [set(ls) for g, ls in s.links if g == seg]
        left = set(range(len(parts)))
        while left:
            j = min(left)
            comp, labels, grew = {j}, set(parts[j]), True
            left.discard(j)
            while grew:
                grew = False
                for i in list(left):
                    if parts[i] & labels:
                        comp.add(i); labels |= parts[i]; left.discard(i); grew = True
            if any(i < len(mine) for i in comp):
                out.append([mine[i] for i in comp if i < len(mine)])
    return out


def normal_form(s):   # in each segment, one component of the join graph, or every component but one is one-row
    by = defaultdict(list)
    for comp in components(s, {a["seg"] for a in s.atoms if a["args"]} - {s.key_seg}):   # an INIT's key body is its instance set, one per row
        by[comp[0]["seg"]].append(comp)
    return not any(len(comps) > 1 and sum(not one_row_component(s, c) for c in comps) > 1 for comps in by.values())


def one_row_component(s, comp):
    """Whether a component binds no label (each label it reads is bound outside its segment, such as a key label):
    it then holds or not, so it has at most one row whatever its relations are; or whether each of its atoms is a
    positive read of a derived relation whose projection onto the columns its sites read has at most one distinct
    row at every input (`CaseRows.one_row`), which needs `s.rows`."""
    if not any(a["binds"] or a["fresh"] for a in comp):
        return True
    return s.rows is not None and all(
        s.v.is_rel[a["rel"]] and not a["neg"]
        and s.rows.one_row(s.v.rel_k[a["rel"]], [(c, f) for c, f in a["sites"]], s.head) for a in comp)


def domain_joined(s):   # each conjunct of a domain shares a variable with another conjunct or a comparison
    for a in s.atoms:
        own = a["reads"] | a["binds"]
        if a["domain"] and own and not any(own & (b["reads"] | b["binds"]) for b in s.atoms
                                           if b is not a and b["seg"] == a["seg"]) \
                and not any(own & ls for g, ls in s.links if g == a["seg"]):
            return False
    return True


def no_free_domain(s):   # no unread `*` label on a lib relation's finite-domain column that its read columns leave open
    det = determined()
    for a in s.atoms:
        cols = s.v.dom_cols.get(a["rel"], ())
        for c, x in a["fresh_at"]:
            if c in cols and x not in s.read:
                bound = {c2 for c2, y in a["site_labels"] if c2 != c and c2 in cols and y in s.read}
                if not any(x0 <= bound for x0 in det.get((s.v.names[a["rel"]], c), ())):
                    return False
    return True


def data_domain(s):   # each label on a lib relation's finite-domain column takes its values from the task's data
    v, fil, zero = s.v, filters(), s.v.tok.get("0")
    lib = []   # per lib atom: (its relation, {column: its label or `0`}, the width, the finite-domain columns, the atom)
    ok = {zero}   # the labels whose values the task's data restricts
    for a in s.atoms:
        if v.kinds[a["rel"]] in LIB_HEADS:
            m = dict(a["site_labels"] + a["key_at"]) | {c: zero for c in a["lit_at"]}
            lib.append((v.names[a["rel"]], m, _WIDTHS[v.names[a["rel"]]], v.dom_cols.get(a["rel"], set()), a))
        else:
            ok |= a["reads"] | a["binds"]
    if s.head == "INIT":   # a component's constant input, such as a Ray's four Dirs: lib relations that read no other label
        for comp in components(s, {a["seg"] for a in s.atoms}):
            labels = set().union(*(a["reads"] | a["binds"] for a in comp))
            if all(v.kinds[a["rel"]] in LIB_HEADS for a in comp) and labels <= set().union(*(a["binds"] for a in comp)):
                ok |= labels
    grew = True
    while grew:
        n = len(ok)
        for x, y, _ in s.eqs:
            if x in ok or y in ok:
                ok |= {x, y}
        for rel, m, width, dom, a in lib:
            for c, x in m.items():
                if x in ok:
                    continue
                others = [m.get(c2) for c2 in range(width) if c2 != c]
                if len(dom) == width:   # some values of it only at each value of the data labels of its other columns
                    known = {c2 for c2, y in m.items() if c2 != c and y in ok}
                    if any(x0 <= known for x0 in fil.get((rel, c), ())):
                        ok.add(x)
                elif all(y in ok for y in others) or zero in others and all(y in ok for y in others if y is not None):
                    ok.add(x)   # a filter by the data labels and `0`s of its other columns
                elif not a["neg"] and c in dom and sum(y != zero for c2, y in m.items() if c2 not in dom) > 1 \
                        and any(y in ok and y != zero for c2, y in m.items() if c2 not in dom):
                    ok.add(x)   # an index of a value it gives from data, such as the margin of a box on each side
        grew = len(ok) > n
    copied = Counter(y for x, y, made in s.eqs if made and not s.reads[x])   # reads that only copy into an unread label
    return all(x in ok for _, m, _, dom, _ in lib for c, x in m.items() if c in dom) and \
        not any(s.reads[x] == copied[x] > 0 for _, _, _, dom, a in lib for c, x in a["fresh_at"] if c in dom)


def shared_self_join(s):   # a relation read twice shares a variable between the two reads
    for j, a in enumerate(s.atoms):
        for b in s.atoms[:j]:
            if a["rel"] == b["rel"] and a["args"] and not (a["reads"] | a["binds"]) & (b["reads"] | b["binds"]):
                return False
    return True


def restatement(s, full=False):
    """Whether the body is one positive conjunct of a program relation with only fresh arguments (with `full`, one
    that also reads every column)."""
    if len(s.atoms) != 1:
        return False
    a = s.atoms[0]
    return bool(s.v.is_rel[a["rel"]] and not a["neg"] and a["fresh"] == a["args"] and (a["full"] or not full))


# name: (level, test, what it requires); a conjunct test runs as each conjunct closes, a clause test as the clause ends
TESTS = {
    "connected": ("conjunct", connected, "each conjunct after its segment's first reads a variable bound before it"),
    "connected join graph": ("clause", graph_connected, "the conjuncts with arguments of each segment are one "
                             "component under shared variables and comparisons"),
    "domain joined": ("clause", domain_joined, "each conjunct of an `_elem` relation or of a relation a DET clause "
                      "declares shares a variable with another conjunct or a comparison"),
    "no free domain argument": ("clause", no_free_domain, "each label that a site of a lib relation on a column of "
                                "a finite domain type (an orientation type) binds with `*` is read at another site, "
                                "in a comparison or in a mark of the clause, or is a function of the atom's other "
                                "finite-domain columns whose labels the clause reads"),
    "domain from data": ("clause", data_domain, "each label on a finite-domain column of a lib relation is "
                         "restricted by the task's data: read by a derived or fact relation, equal to such a label, in "
                         "an INIT clause's constant input, or filtered or indexed by a lib relation from such labels"),
    "normal form": ("clause", normal_form, "in each segment but an INIT clause's key clause, the join graph is one "
                    "component, or every component "
                    "but one is one-row: it binds no label, or each of its conjuncts is a positive read of a derived relation with at most one "
                    "distinct row of the columns it reads at every input (needs --tables)"),
    "not all literal": ("conjunct", not_all_literal, "no conjunct has every argument a literal"),
    "no literal": ("conjunct", no_literal, "no argument is a literal"),
    "at most one literal": ("conjunct", one_literal, "at most one literal argument per conjunct"),
    "no self-join": ("conjunct", no_self_join, "no relation is read twice"),
    "self-join shares": ("clause", shared_self_join, "a relation read twice shares a variable between the two reads"),
    "not a restatement": ("clause", lambda s: not restatement(s), "the body is not one positive conjunct of a "
                          "program relation with only fresh arguments"),
    "not a full restatement": ("clause", lambda s: not restatement(s, True), "nor one that also reads every column"),
}
HEADED = ("RULE", "DET", "INIT")   # the clause heads the compliance is measured on
# --constraints: {set: {test: the clause heads it applies to}}; gold98 (gold95) holds each test at the heads where at
# least 98% (95%) of the corpus clauses meet it (`constraints`); normal holds the normal form
CONSTRAINT_SETS = {"gold98": {"not all literal": HEADED, "at most one literal": HEADED,
                              "connected join graph": ("DET",), "no literal": ("DET", "INIT"),
                              "not a full restatement": ("INIT",)},
                   "gold95": {"not all literal": HEADED, "at most one literal": HEADED, "no literal": HEADED,
                              "connected join graph": ("RULE", "DET"), "domain joined": ("RULE", "DET"),
                              "self-join shares": ("DET",), "not a full restatement": ("DET", "INIT")},
                   "normal": {"normal form": HEADED},
                   "normal2": {"normal form": HEADED, "no free domain argument": HEADED},
                   "normal3": {"normal form": HEADED, "no free domain argument": HEADED, "domain from data": HEADED}}
TABLE_TESTS = ("normal form",)   # the tests that read the prefix's tables (`Shape.rows`)
CONJUNCT_TRIES = 10   # the conjuncts a clause may draw again before it is given up as "no candidate"


def clause_shape(corpus, cl, rows=None):
    """The Shape of a corpus clause, with each token's mask from cases.npz; `rows`, the CaseRows of its case."""
    v = corpus.vocab
    s = Shape(v, cl["heads"])
    s.rows = rows
    for t, em, st in zip(cl["toks"], cl["forced"], cl["steps"]):
        adm = np.unpackbits(corpus.mask_table[corpus.mask_index[st]], bitorder="little")[:len(v.names)].astype(bool)
        s.feed(t, em, bool((adm & v.is_col).any()))
    return s


def passes(s, name, a=None):
    level, f, _ = TESTS[name]
    return f(s) if level == "clause" else all(f(s, b) for b in ([a] if a is not None else s.atoms))


# ------------------------------------------------------------------ the writer

def empty_counts(e):
    """Whether the body of the clause in progress on decoder e has no row at any example under any DET assignment
    (`Decoder.counts`); None where the engine gives no count (no clause in progress, a fault, every count None)."""
    try:
        c = e.counts()
    except Exception:
        return None
    if c is None:
        return None
    vals = [x for a in c for x in a.values if x is not None]
    return all(x == 0 for x in vals) if vals else None


class Writer:
    def __init__(self, vocab, model, temperature, counts=False, constraints=None):
        self.v, self.model, self.T, self.counts = vocab, model, temperature, counts
        self.tests = defaultdict(list)   # {clause head: the names of the tests of `constraints` that apply to it}
        for name, heads in CONSTRAINT_SETS[constraints].items() if constraints else ():
            for h in heads:
                self.tests[h].append(name)
        self.redrawn = 0
        self.expanded = getattr(model, "expanded", False)
        self.closers = np.zeros(len(vocab.names), dtype=bool)
        self.closers[list(model.closers)] = True

    def draw(self, rng, scores):
        z = np.asarray(scores, dtype=float) / self.T
        p = np.exp(z - z.max()); p /= p.sum()
        return int(np.searchsorted(np.cumsum(p), rng.random() * p.sum(), side="right").clip(0, len(p) - 1))

    def write(self, rng, d, declared, index, lo, hi, step, state=None, heads=None, rows=None):
        """Draw one clause on a fork of d, with the random choices from rng. A generator: at each step it yields
        (context, candidates) and is sent the scorer's scores of those candidates, and it returns (reason or None,
        the fork, ids, model flags, last consistency, tokens, empty). `state` is the prefix's (relation features, heads, uses) for the scorer `tables`, `heads` the
        prefix's heads (`stream_state`) and `rows` its CaseRows for the constraints. With `counts`, empty is `empty_counts` before the
        clause's last token, else None. With constraints, the state before each conjunct is kept, and a conjunct
        that fails a test is drawn again from there (`CONJUNCT_TRIES`)."""
        v = self.v
        e = d.fork()
        decl = np.zeros(len(v.names), dtype=bool)
        decl[list(declared)] = True
        hist, s_ids, s_model, cons = [], [], [], None
        feats, heads0, uses = state if state is not None else (None, {}, {})
        last = None
        shape = Shape(v, heads if heads is not None else heads0) if self.tests else None
        if shape is not None:
            shape.rows = rows
        tests, saved, tries = [], [], 0
        while True:
            if e.ended:
                return "ended", None, None, None, None, len(hist), None
            if len(hist) >= hi:
                return "too long", None, None, None, None, len(hist), None
            adm = unpack(e.admissible(), len(v.names))
            sk, ids = v.candidates(adm, decl)
            if len(hist) < lo:
                keep = []
                for j, i in enumerate(ids):
                    if i >= 0 and self.closers[i]:
                        if hasattr(e, "forced"):
                            # forced(i) gives the forced ids that step's result has first (f[0]); a refusal
                            # raises, where step gives None, and the token is kept
                            try:
                                forced = e.forced(i)
                            except Exception:
                                forced = None
                        else:
                            f = step(e.fork(), i)
                            forced = None if f is None else f[0]
                        if forced is not None and any(v.is_rel[x] for x in forced):
                            continue
                    keep.append(j)
                sk, ids = [sk[j] for j in keep], [ids[j] for j in keep]
            if not sk:
                return "no candidate", None, None, None, None, len(hist), None
            n_rel = int((decl & v.is_rel).sum())
            if self.expanded:
                x = relation_context(v, adm, decl, feats, heads0, uses, last, n_rel)
                ctx = (hist, len(hist), index, n_rel, int((decl & v.is_lab).sum()), x)
                cs = expand(sk, ids, x)
                j = self.draw(rng, (yield ctx, cs))
                s, t = cs[j]
                if t < 0:
                    t = rng.choice(np.flatnonzero(adm & v.is_lab & decl).tolist())
            else:
                ctx = (hist, len(hist), index, n_rel, int((decl & v.is_lab).sum()))
                j = self.draw(rng, (yield ctx, sk))
                s, t = sk[j], ids[j]
                if t < 0:
                    kind = v.is_rel if sk[j] == 1 else v.is_lab
                    t = rng.choice(np.flatnonzero(adm & kind & decl).tolist())
            if shape is not None and v.is_head[t] and (shape.cur is None or shape.closes(t)):
                saved.append((e.fork(), hist, list(s_ids), list(s_model), decl.copy(), uses, last, shape.copy(),
                              cons))
            before = e.fork() if self.counts and len(hist) + 1 >= lo else None   # counted only where t ends the clause
            f = step(e, t)
            if f is None:
                return "fault", None, None, None, None, len(hist), None
            emitted, cons = f
            s_ids += [t] + emitted
            s_model += [1] + [0] * len(emitted)
            hist = hist + [s]
            if v.is_rel[t]:
                uses, last = {**uses, t: uses.get(t, 0) + 1}, t
            for x in emitted:
                if v.ident[x]:
                    decl[x] = True
            if shape is not None:
                if len(hist) == 1:
                    tests = self.tests.get(v.names[t], [])
                a = shape.feed(t, emitted, bool((adm & v.is_col).any()))
                if tests and ((a is not None and not all(passes(shape, n, a) for n in tests
                                                         if TESTS[n][0] == "conjunct"))
                              or (shape.ended and not all(passes(shape, n) for n in tests if TESTS[n][0] == "clause"))):
                    tries += 1; self.redrawn += 1
                    if tries > CONJUNCT_TRIES or not shape.atoms:
                        return "no candidate", None, None, None, None, len(hist), None
                    j = len(shape.atoms) - 1   # the conjunct that failed, or the last one where the clause did
                    se, hist, s_ids, s_model, decl, uses, last, sh, cons = saved[j]
                    del saved[j:]
                    e, s_ids, s_model, decl, shape = se.fork(), list(s_ids), list(s_model), decl.copy(), sh.copy()
                    continue
            if any(v.is_rel[x] for x in emitted):
                if len(hist) < lo:
                    return "too short", None, None, None, None, len(hist), None
                return None, e, s_ids, s_model, cons, len(hist), None if before is None else empty_counts(before)


def gold_clause_len(ids, model, kinds, n):
    k = 0
    for j in range(n, len(ids)):
        if model[j]:
            k += 1
        elif kinds[ids[j]] == "relation" and k:
            return k
    return None


def clause_index(ids, model, kinds, n):
    idx, cur = 0, False
    for j in range(n):
        if model[j]:
            cur = True
        elif cur and kinds[ids[j]] == "relation":
            idx, cur = idx + 1, False
    return idx


def bounds(a, g):
    lo = max(a.min_tokens, math.ceil(a.length_low * g))
    return lo, max(lo + 2, math.floor(a.length_high * g))


class Task:
    """A task's session, vocabulary, root decoder and gold lines of points.py."""
    def __init__(self, task, a, first, vocab_names):
        import arclog, points
        self.task = task
        tj = json.load(open(ROOT / "data/tasks" / f"{task}.json"))
        self.tests = [t["output"] for t in tj["test"]] if all("output" in t for t in tj["test"]) else None
        self.session, self.head = points.head(task, a.world, a.data)
        v = self.session.vocabulary
        self.names = [v.name(i) for i in range(len(v))]
        self.kinds = [v.kind(i) for i in range(len(v))]
        assert self.names == vocab_names, f"{task}: the engine's vocabulary differs from {a.data}'s"
        self.root = self.session.decoder()
        self.case, self.ids, self.model = first[task]
        self.golds = points.golds(task, self.root, *first[task])
        rel_k = [int(n[2:]) if k == "relation" else -1 for n, k in zip(self.names, self.kinds)]
        tables = bool(a.model_list and "tables" in a.model_list)
        normal = any(t in TABLE_TESTS for t in CONSTRAINT_SETS.get(a.constraints, ()))
        src, how = gold_source(task, self.case, self.ids, self.model, a, rel_k) if tables or normal else (None, None)
        self.feats, self.feats_from = (src.features(task, self.case), how) if tables else (None, None)
        self.rows = (CaseRows(src, task, self.case, self.ids, [int(m) for m in self.model], self.names, self.kinds)
                     if normal else None)


def step(d, i):
    """Step decoder d by id i: (forced ids, consistency), or None where the engine faults or refuses."""
    import arclog
    r = arclog.step_batch([d], [i])[0]
    if isinstance(r, (arclog.Fault, Exception)):
        return None
    return list(r[0]), r[1]


def point_clauses(T, g, a, model, vocab, median, on_clause, counts=False):
    """Draw clauses at the branch point of gold line g until a bound; on_clause(written, ids, model flags, decoder,
    consistency, tokens, empty) for each completable one, in the order they end. With `--reject-empty`, a clause that
    `empty_counts` gives as empty is drawn again and counted as "empty". The clauses in progress step together (the
    module docstring). Gives the counts."""
    import points
    from sample import hash_seed
    from foreign import replay_prefix
    tp = time.time()
    n = int(g["prefix_tokens"])
    gl = gold_clause_len(g["ids"], g["model"], T.kinds, n)
    lo, hi = bounds(a, gl or median)
    d, declared = replay_prefix(T.root, g["ids"], n, T.kinds, f"{T.task} {g['case']}")
    index = clause_index(g["ids"], g["model"], T.kinds, n)
    seed = hash_seed(a.seed, T.task, n)
    w = Writer(vocab, model, a.temperature, counts=counts or a.reject_empty, constraints=a.constraints)
    state = (T.feats, *stream_state(vocab, g["ids"], g["model"], n)) if getattr(model, "expanded", False) else None
    heads = stream_state(vocab, g["ids"], g["model"], n)[0] if a.constraints else None
    cnt = Counter()
    written = 0

    def advance(draw, scores):   # (the draw's next (context, candidates), None), or (None, its result) where it ended
        try:
            return draw.send(scores), None
        except StopIteration as stop:
            return None, stop.value

    def end(result):
        nonlocal written
        reason, e, s_ids, s_model, cons, k, empty = result
        if reason is None and a.reject_empty and empty:
            reason = "empty"
        if reason is not None:
            cnt[reason] += 1; return
        cnt["completable"] += 1
        if w.counts:
            cnt["counted"] += empty is not None
            cnt["counted empty"] += bool(empty)
        on_clause(written, g["ids"][:n] + s_ids, g["model"][:n] + s_model, e, cons, k, empty)
        written += 1

    live = []   # [(draw, its pending (context, candidates))], in the order the draws started
    while True:
        while (written + len(live) < a.per_point and cnt["candidates"] < a.max_tries
               and time.time() - tp <= a.point_seconds):
            draw = w.write(random.Random(f"{seed} {cnt['candidates']}"), d, declared, index, lo, hi, step, state,
                           heads, T.rows)
            cnt["candidates"] += 1
            req, result = advance(draw, None)
            if result is None:
                live.append((draw, req))
            else:
                end(result)
        if not live:
            break
        scores = model.scores([req[0] for _, req in live], [req[1] for _, req in live])
        going = []
        for (draw, _), sc in zip(live, scores):
            req, result = advance(draw, sc)
            if result is None:
                going.append((draw, req))
            else:
                end(result)
        live = going
    if a.constraints:
        cnt["redrawn"] = w.redrawn
    return dict(cnt, written=written, gold_tokens=gl, lo=lo, hi=hi, seconds=round(time.time() - tp, 1))


# ------------------------------------------------------------------ modes

def mode_sample(a):
    import points
    from sample import kind_name, record
    stamps = json.loads(Path(a.stamps).read_text()) if a.stamps else None
    first = points.first_cases(a.data)
    tasks = a.tasks or sorted(first)
    vocab_json = json.load(open(Path(a.data) / "vocab.json"))
    vocab = Vocab(vocab_json["names"], vocab_json["kinds"])
    out = Path(a.out); (out / "samples").mkdir(parents=True, exist_ok=True)
    (out / "counts").mkdir(exist_ok=True)
    models, corpus = {}, None
    for task in points.queued(a.queue) if a.queue else tasks:
        t0 = time.time()
        fold = fold_of(task)
        if fold not in models:
            models[fold], corpus = get_model(a.model, fold, a.corpus, out, vocab, corpus, a.tables)
        model = models[fold]
        try:
            T = Task(task, a, first, vocab.names)
        except BaseException as e:
            if not points.caught(e):
                raise
            points.refused(out, task, first[task][0], e, t0)
            points.write_stamp(out, task, stamps); continue
        settings = {"settings": T.head["settings"], "world": T.head["world"],
                    "args": {"model": None, "prefix": "random", "data": T.head["args"]["data"], "source": None,
                             "points": "all", "corpus": str(a.corpus), "writer": a.model,
                             "temperature": a.temperature, "per_point": a.per_point, "max_tries": a.max_tries,
                             "point_seconds": a.point_seconds, "min_tokens": a.min_tokens,
                             "length_low": a.length_low, "length_high": a.length_high, "seed": a.seed,
                             **({"tables": str(a.tables), "tables_from": T.feats_from} if a.model == "tables" else {}),
                             **({"reject_empty": True} if a.reject_empty else {}),
                             **({"constraints": a.constraints} if a.constraints else {}),
                             "maker": "work/lm/data-study/writer.py"},
                    "model_meta": {"fold": None}}
        task_counts = {}
        with open(out / "samples" / f"{task}.jsonl", "w") as fh:
            fh.write("".join(json.dumps(r) + "\n" for r in [settings] + T.golds)); fh.flush()
            for g in T.golds:
                key = f"{g['case']} {g['prefix_tokens']}"
                if time.time() - t0 > a.seconds:
                    task_counts[key] = dict(skipped="time"); continue
                n = int(g["prefix_tokens"])

                def emit(r, ids_f, model_f, e, cons, k, empty):
                    rule = T.names[ids_f[n]] == "RULE"
                    rec = record(task, g["case"], g["prefix_rules"], r, ids_f, model_f, n, e, cons, T.tests,
                                 end="writer", rules=[kind_name(cons)] if rule and cons is not None else [],
                                 model_steps=sum(model_f[n:]), refusals=0, max_steps_used=None, max_cont_used=None,
                                 max_clause_used=None, panic=None,
                                 writer={"model": a.model, "temperature": a.temperature, "fold": fold, "tokens": k})
                    fh.write(json.dumps(rec) + "\n"); fh.flush()
                try:
                    task_counts[key] = point_clauses(T, g, a, model, vocab, model.median, emit)
                except BaseException as e:
                    if not points.caught(e):
                        raise
                    task_counts[key] = dict(error=points.message(e))
                    print(f"{task} {key}: error, {points.message(e)}", flush=True); continue
                (out / "counts" / f"{task}.json").write_text(json.dumps(task_counts, indent=1))
        (out / "counts" / f"{task}.json").write_text(json.dumps(task_counts, indent=1))
        points.write_stamp(out, task, stamps)
        tot = Counter()
        for c in task_counts.values():
            tot.update({k: v for k, v in c.items() if isinstance(v, int) and k not in ("gold_tokens", "lo", "hi")})
        print(f"{task}: {len(task_counts)} branch points, {dict(tot)}, {time.time() - t0:.1f} s", flush=True)


def mode_fit(a):
    vocab_json = json.load(open(Path(a.corpus) / "vocab.json"))
    vocab = Vocab(vocab_json["names"], vocab_json["kinds"])
    corpus = None
    for kind in a.model_list:
        for fold in range(FOLDS):
            p = model_path(a.out, kind, fold, a.corpus, a.tables)
            had = p.exists()
            m, corpus = get_model(kind, fold, a.corpus, a.out, vocab, corpus, a.tables)
            print(f"{kind} fold {fold}: {'reused' if had else f'fit in {m.seconds:.1f} s'}"
                  + (f", {m.rows} rows" if kind != "ngram" else "") + f", {p}", flush=True)


def ll_of(model, corpus, clauses, source=None):
    """Summed over the clauses' steps: (log-likelihood of the gold token, of the uniform choice among the tokens,
    log-likelihood of the gold's class, of the uniform choice among the classes), the steps scored, and the steps
    whose gold is outside the candidates. A token is a candidate of `expand` (each admitted declared relation on its
    own, a label as its class); a class is a candidate of `Vocab.candidates`. The scorers ngram and trees choose a
    relation among the admitted declared ones uniformly, and the class of `tables` sums its relations."""
    expanded = getattr(model, "expanded", False)
    ctxs, cands, steps = [], [], []
    for cl in clauses:
        for ctx, sk, g, tok in corpus.walk(cl, source if expanded else _NoSource()):
            ctxs.append(ctx); cands.append(expand(sk, [-1] * len(sk), ctx[5]) if expanded else sk)
            steps.append((sk, g, tok))
    sc = model.scores(ctxs, cands)
    tok_ll = tok_un = cls_ll = cls_un = 0.0
    n = miss = 0
    for j, (s, cs, (sk, g, tok)) in enumerate(zip(sc, cands, steps)):
        if g not in sk:
            miss += 1; continue
        z = s - s.max()
        lp = z - math.log(np.exp(z).sum())
        if expanded:
            gold = (g, tok if g == 1 else -1)
            if gold not in cs:
                miss += 1; continue
            tok_ll += lp[cs.index(gold)]
            m = lp[[i for i, c in enumerate(cs) if c[0] == g]]
            cls_ll += m.max() + math.log(np.exp(m - m.max()).sum())
            tok_un -= math.log(len(cs))
        else:
            nr = len(ctxs[j][5]["rels"])
            cls_ll += lp[sk.index(g)]
            tok_ll += lp[sk.index(g)] - (math.log(nr) if g == 1 else 0.0)
            tok_un -= math.log(len(sk) - 1 + nr if 1 in sk else len(sk))
        cls_un -= math.log(len(sk))
        n += 1
    return tok_ll, tok_un, cls_ll, cls_un, n, miss


class _NoSource:
    """A source that gives no features, for the admitted declared relations of `relation_context` alone."""
    def features(self, task, case):
        return None


def mode_tables(a):
    t0 = time.time()
    src = table_source(a.tables, a.out)
    had = len(src.cache)
    for key in src.t_at:
        src.features(*key)
    src.save()
    print(f"{a.tables}: the relation features of {len(src.cache)} cases, {len(src.cache) - had} read, in "
          f"{time.time() - t0:.1f} s; {tables_cache(a.out, a.tables)}", flush=True)


def mode_constraints(a):
    t0 = time.time()
    vocab_json = json.load(open(Path(a.corpus) / "vocab.json"))
    corpus = Corpus(a.corpus, Vocab(vocab_json["names"], vocab_json["kinds"]))
    v = corpus.vocab
    src, rows = None, {}
    if a.tables_given:
        ts = time.time()
        src = table_source(a.tables)
        m = src.match(corpus.decls)
        print(f"tables {a.tables}: of {sum(m.values())} relations the corpus streams declare, {m['differs']} have "
              f"tables that do not follow the stream ({time.time() - ts:.1f} s)", flush=True)

    def rows_of(cl):
        key = (cl["task"], cl["case"])
        if key not in rows:
            rows[key] = CaseRows(src, *key, *corpus_stream(a.corpus, *key), v.names, v.kinds)
        return rows[key]
    tests = [name for name in TESTS if src is not None or name not in TABLE_TESTS]
    sets = [k for k, v_ in CONSTRAINT_SETS.items() if all(t in tests for t in v_)]
    n, ok = Counter(), Counter()
    for col, cls in (("", corpus.clauses), ("output", corpus.outputs)):
        for cl in cls:
            head = v.names[cl["toks"][0]]
            if head not in HEADED:
                continue
            s = clause_shape(corpus, cl, rows_of(cl) if src is not None else None)
            col_ = col or head
            n[col_] += 1
            got = {name: passes(s, name) for name in tests}
            for name in tests:
                ok[col_, name] += got[name]
            for k in sets:
                ok[col_, k] += all(got[t] for t, heads in CONSTRAINT_SETS[k].items() if head in heads)
    n["all"] = sum(n[h] for h in HEADED)
    for name in tests + sets:
        ok["all", name] = sum(ok[h, name] for h in HEADED)
    cols = ("all",) + HEADED + ("output",)
    print(f"corpus {a.corpus}: the clauses of {len(HEADED)} heads, once per task as the fits read them, and the "
          f"output clause (the last RULE clause) of each of its cases; the share of them that meets each test, and "
          f"their count ({time.time() - t0:.1f} s)")
    print(f"  {'test':<24}" + "".join(f"{c + ' ' + str(n[c]):>18}" for c in cols))
    for name in tests + [f"--constraints {k}" for k in sets]:
        key = name.removeprefix("--constraints ")
        print(f"  {name:<24}" + "".join(f"{ok[c, key] / n[c]:>11.3f} {ok[c, key]:>6}" for c in cols))
    if src is None:
        print(f"  ({', '.join(TABLE_TESTS)}: not tested, which needs --tables)")
    for name, (_, _, what) in TESTS.items():
        print(f"  {name}: {what}")
    for k, v in CONSTRAINT_SETS.items():
        print(f"  --constraints {k}: " + "; ".join(f"{t} ({', '.join(h)})" for t, h in v.items()))


def mode_eval(a):
    t0 = time.time()
    vocab_json = json.load(open(Path(a.corpus) / "vocab.json"))
    vocab = Vocab(vocab_json["names"], vocab_json["kinds"])
    corpus = Corpus(a.corpus, vocab)
    L = np.array(corpus.lengths)
    print(f"corpus {a.corpus}: {corpus.n_cases} cases, {corpus.n_tasks} tasks, {len(L)} clauses, "
          f"{len(corpus.clauses)} once per task; clause length p25 {np.percentile(L, 25):.0f} median "
          f"{corpus.median} p75 {np.percentile(L, 75):.0f}; closers: "
          + " ".join(sorted(vocab.names[i] for i in corpus.closers)) + f" ({time.time() - t0:.1f} s)", flush=True)
    source = None
    if "tables" in a.model_list:
        ts = time.time()
        source = table_source(a.tables, a.out)
        m = source.match(corpus.decls)
        print(f"tables {a.tables}: of {sum(m.values())} relations the corpus streams declare, {m['token matches']} have one "
              f"table whose token is the last model-written token before the declaration, {m['differs']} one or more "
              f"tables otherwise, {m['no table']} no table ({time.time() - ts:.1f} s)", flush=True)
    print(f"held-out mean log-likelihood per step (softmax over the step's candidates), at most {a.eval_clauses} "
          f"clauses per fold: of the token (a relation identifier on its own), and of its class; uniform beside each")
    models = {}
    for kind in a.model_list:
        tot = np.zeros(6)
        for fold in range(FOLDS):
            m, _ = get_model(kind, fold, a.corpus, a.out, vocab, corpus, a.tables)
            models[kind, fold] = m
            held = [c for c in corpus.clauses if c["fold"] == fold]
            held = random.Random(fold).sample(held, min(a.eval_clauses, len(held)))
            if not held:
                print(f"  {kind:<6} fold {fold}: no held-out clause", flush=True); continue
            ts = time.time()
            r = ll_of(m, corpus, held, source)
            if source is not None:
                source.save()
            tot += r
            tl, tu, cl, cu, n, miss = r
            print(f"  {kind:<6} fold {fold}: fit {m.seconds:5.1f} s{f', {m.rows} rows' if kind != 'ngram' else ''}; "
                  f"{len(held)} clauses, {n} steps: token {tl / n:.3f} (uniform {tu / n:.3f}), class {cl / n:.3f} "
                  f"(uniform {cu / n:.3f}), {miss} gold outside the candidates; {time.time() - ts:.1f} s", flush=True)
        tl, tu, cl, cu, n, miss = tot
        print(f"  {kind:<6} all folds: token {tl / n:.3f} (uniform {tu / n:.3f}), class {cl / n:.3f} "
              f"(uniform {cu / n:.3f})", flush=True)
    if not a.points:
        return
    import points
    first = points.first_cases(a.data)
    tasks = a.tasks or sorted(first)[:3]
    print(f"completable share at up to {a.points} branch points of each of {len(tasks)} tasks, temperature "
          f"{a.temperature}, up to {a.per_point} completable or {a.max_tries} drawn per point; empty: of the "
          f"completable clauses whose body the engine counts before the last token, those with no row")
    Ts = {}
    for task in tasks:
        Ts[task] = Task(task, a, first, vocab.names)
        if Ts[task].feats_from:
            print(f"  {task}: relation features from the {Ts[task].feats_from}", flush=True)
    for kind in a.model_list:
        tot, ratio = Counter(), []
        ts = time.time()
        for task in tasks:
            T = Ts[task]
            m = models[kind, fold_of(task)]
            gs = T.golds
            gs = [gs[int(i)] for i in np.linspace(0, len(gs) - 1, min(a.points, len(gs)))] if gs else []
            for g in gs:
                lens = []
                c = point_clauses(T, g, a, m, vocab, m.median, lambda r, i, mo, e, cons, k, empty: lens.append(k),
                                  counts=True)
                tot.update({k: v for k, v in c.items() if k in ("candidates", "completable", "counted", "counted empty", *REASONS)})
                ratio += [k / (c["gold_tokens"] or m.median) for k in lens]
        print(f"  {kind:<6}: {tot['completable']} of {tot['candidates']} completable "
              f"({tot['completable'] / max(tot['candidates'], 1):.0%}); " + ", ".join(f"{r} {tot[r]}" for r in REASONS if tot[r])
              + f"; empty {tot['counted empty']} of {tot['counted']} counted"
              + (f"; length / gold length median {np.median(ratio):.2f} (p25 {np.percentile(ratio, 25):.2f}, "
                 f"p75 {np.percentile(ratio, 75):.2f})" if ratio else "") + f"; {time.time() - ts:.1f} s", flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("mode", choices=["sample", "fit", "eval", "tables", "constraints"])
    ap.add_argument("--model", nargs="+", default=["ngram"], choices=["ngram", "trees", "tables"],
                    help="sample takes one")
    ap.add_argument("--tables", help=f"the tables export of --corpus, for the scorer tables (default {TABLES}) and "
                    "for --constraints normal, normal2 and normal3 (no default)")
    ap.add_argument("--reject-empty", action="store_true")
    ap.add_argument("--constraints", choices=sorted(CONSTRAINT_SETS), help="the structural constraints of the clauses drawn")
    ap.add_argument("--temperature", type=float, default=1.0)
    ap.add_argument("--data", default=str(ROOT / "work/lm/data-full-4663b88a"))
    ap.add_argument("--corpus", help="the data export whose cases.npz the scorers are fit on; default --data")
    ap.add_argument("--out", default=str(ROOT / "work/lm/rollouts-writer"))
    ap.add_argument("--tasks", nargs="*")
    ap.add_argument("--per-point", type=int, default=4)
    ap.add_argument("--max-tries", type=int, default=200)
    ap.add_argument("--point-seconds", type=float, default=8)
    ap.add_argument("--seconds", type=float, default=600, help="per task")
    ap.add_argument("--min-tokens", type=int, default=6)
    ap.add_argument("--length-low", type=float, default=0.75)
    ap.add_argument("--length-high", type=float, default=1.5)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--world", choices=["Closed", "Open"], default="Closed")
    ap.add_argument("--points", default=None, help="sample: `all` (the only choice); eval: the branch points per task (default 4, 0 for none)")
    ap.add_argument("--stamps")
    ap.add_argument("--queue")
    ap.add_argument("--eval-clauses", type=int, default=2000)
    a = ap.parse_args()
    a.corpus = a.corpus or a.data
    a.model_list = a.model
    a.tables_given = a.tables is not None
    if any(t in TABLE_TESTS for t in CONSTRAINT_SETS.get(a.constraints, ())) and not a.tables_given:
        ap.error(f"--constraints {a.constraints} reads the tables of the prefix's relations: give --tables, the "
                 f"tables export of --corpus")
    a.tables = a.tables or str(TABLES)
    if a.tables_given and not (Path(a.tables) / "tables.parquet").exists():
        ap.error(f"--tables {a.tables}: no tables.parquet there")
    if a.mode == "sample":
        if len(a.model) != 1 or a.points not in (None, "all"):
            ap.error("sample takes one --model and --points all")
        a.model = a.model[0]
        mode_sample(a)
    elif a.mode == "fit":
        mode_fit(a)
    elif a.mode == "tables":
        mode_tables(a)
    elif a.mode == "constraints":
        mode_constraints(a)
    else:
        a.points = 4 if a.points is None else int(a.points)
        mode_eval(a)


if __name__ == "__main__":
    main()
