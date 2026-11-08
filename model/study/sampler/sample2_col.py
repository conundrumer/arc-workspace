#!/usr/bin/env python
"""Whole-clause sampler v2 at RULE points of the feature-inputs export (fstore/points), dev tasks only.

Changes from sample.py (v1):
- points come from fstore/points, so the feature study's RuleCheck can read each point;
- a name map {task|case|point: {&rN: written name}} is written to DIR/names.json;
- X carries the engine's column frames and each entry's model;
- the binder prior is conditioned on (relation, column), so a binder that gold never writes at a column gets no mass;
- the relation choice looks one step ahead and favours relations that can join a label in scope;
- an atom is redrawn (up to ATOM_TRIES, and up to CHEAP_TRIES more for a repeated or unjoined atom) where it cannot complete, joins nothing (kept at gold's rate), or makes the
  prefix's X empty on every train entry, which is anti-monotone; each redraw is counted by reason;
- the decoder's static pruning mask is on (STATIC_MASK=0 turns it off);
- gold's clause records whether each of its prefixes is safe (can end);
- an atom that repeats an earlier atom of its conjunction or an enclosing one is redrawn;
- an atom that the engine's static prune matches (as in a row's 'static') is redrawn, in the clause and in the last
  branch of an OR;
- a draw may not stop at one atom at a DET or at a RULE that is not the output clause (MIN2_KINDS), unless that atom calls a
  derived relation's method (one_call), and at an INIT port it
  may not stop before its body reads a derived relation (DERIVED_GROUPS) or with more than MAX_UNREAD unread labels;
- at the output clause, the columns and fresh binders of the types it still needs are favoured (dr.need).
- the tests that the feature study's checks also apply are theirs, called in place of copies: the point group and
  depth (strata.point_fields), the repeated atom (h3_repeated_test) and the unread labels of a port body (g3_unread), both
  through rulecheck.RuleCheck, and the column types of a lib relation (featlib's interfaces).
- with --samples, each draw with a clause and no fail is also a study-sample-v1 record (DIR/samples.jsonl.zst) of its point's
  original gold (DIR/golds.jsonl.zst), for sample_label.py; a draw row carries body_path, clause_path and point_kind.
- a draw row carries logp, the log probability of its path under the count prior P (the moves the decoder allows, with no
  steering), and logq_full, logq plus the stop factors, so that exp(logp - logq_full) is its importance weight; gold's row
  has the values of its own path, or None where the path is not scored (a compound atom).
- the grammar gives a constraint operator (`=`, `!=`, `<`, `<=`, `>`, `>=`) no mass directly under NOT, which the reader does
  not accept, and gives `=` no mass with the same operand twice (`(= A A)`), anywhere; both are left out of the options, so P
  and q lose them alike.
- the study-sample-v1 records (and so original_point and the files DIR/samples.jsonl.zst and DIR/golds.jsonl.zst) are made
  only with --samples; a draw row's body_path, clause_path and point_kind come from the original program either way.
- the frontier of an atom start in the main clause loop is kept per point by (clause tokens so far, label count), with the
  nodes it grows (their checks, masks and child decoders), so draws that share their clause tokens before an atom build
  it once (Drawer.frontier, ROOT_CAP and NODE_CAP); the reach memo is per Drawer.frontier call, as the fresh nodes were, so
  the draws are unchanged.
- a static match of class `valid` (an atom that always holds, as gold's membership.subtype atoms) is no prune, so only
  the other classes redraw an atom. An atom whose prefix X is empty on every train entry and on the test input is redrawn
  (EMPTY_ATOM=0 keeps it; X's empty_inputs), except at a point where gold's X is (a guard clause, such as a defect check
  under NOT, that holds on no input); such a point is marked in its info (gold.empty).
- each atom's can_end (a full check of the closed clause) is kept per point by the memo's key, and the accepted atom
  reuses it.
- SAMPLER_CORPUS (sample.py), SAMPLER_FSTORE and SAMPLER_GEN replace the gold the sampler reads: the AST corpus, the
  feature-store points and the converted corpus;
- GOLD_APPROXIMATED=1 (sample.py) makes the fits read a corpus stem whose first row has `approximated: true` (its gold solver has @approximated); by default the fits (corpus_forms, body_hazard, group_hazards, and so live_priors.py and live_rows.py) leave that stem out. A view with no such flag is read whole;
- HAZARD_GROUP=1 gives a RULE point the stop factors of its own point group's gold bodies, in place of all RULE bodies';
- PREFIX_DRAWS=1 writes cuts.jsonl.zst: each passing draw's clause (and gold's) cut after each atom where it can end,
  evaluated as a draw, with prefix_of, prefix_k and draw = prefix_of * 1000 + prefix_k;
- STEER_GROUPS (a comma list of point groups) limits STEER_M to those groups;
- STEER_M=m (m > 1) steers the first STEER_K atoms (default 3) of a draw at a point that is not an INIT port: m candidate
  atoms are drawn, each cut is scored by the cut score at STEER_MODEL, and one is picked with weight exp(STEER_BETA * score).
  logq_full takes log(g(picked) / mean g) for each steered atom, so the draws stay properly weighted for π; the draw's
  `steer` gives [k, scores, picked] per steered atom; with STEER_ONLINE=1 the cut score is the feature study's online scorer
  (online_score.PointScorer): the soft score of a cut that passes the hard rules, STEER_FLOOR otherwise; with
  STEER_ONLINE=norows, its soft score without X rows (SOFT_NOROWS, no hard rules); with STEER_ONLINE=cut, the log-odds of
  the feature study's cut scorer (cut_score.CutScorer) on the cut as a cuts.jsonl row. EXACT=1 composes with STEER_M: each
  candidate comes from the EXACT sampler with its own A^, and the picked candidate's A^ (and coin delta) enters logq_full;
  GOLD_Q=1 gives a steered gold atom (k <= STEER_K, not a port) the SIR factor log m + log mean_r [g(a) / (g(a) + sum_j g(Y_rj))] in
  its site q, from STEER_GQ_R (default 8) replicates of the m - 1 other candidates Y drawn by the EXACT sampler on gold_q's own rng;
  the atom's parts gain steer_lf, steer_m, steer_r and steer_sd (the replicates' spread);
- JOIN_BOOST, JOINABLE_BOOST, NEED_BOOST and WANT_BOOST are the proposal's boosts (default 1: none);
- UNREAD_BETA (nats, default 0: off) raises the log weight of a derived option at an atom start where its form is one that no kept form
  reads (Drawer.unread, which live.py sets). P stays as it is, so the steers' rows do not change;
- STRUCT_P=1 gives P's relation weight at an atom start and value weight at a column the structural logits REL_W
  and VAL_W: P's count weight to a fitted power, times exp of the other features (the relation's kind by first atom, its
  column types in scope, arity, a repeat of a relation the clause read, a derived relation's recency; a value's kind, a
  label's recency, its type against the column's, a label the atom names already). The callers give the atom's own k and
  the types in scope (p_k, p_scope), which q's steering does not change; STRUCT_B=1 adds to the relation logit
  explorer b's terms for the relations of r14b.INPUT_SLOTS (REL_WB): every input slot has a label in scope, a Box and a
  Position in scope, a relation that follows the last atom's (`inside`, `relative`, a repeat), and a column that takes a
  type the last atom enumerates; the callers also give the last atom's tokens (p_last);
- CHOICE_ROWS=1 writes choices.jsonl.zst, a frame per point: a row per pick of gold's clause after the relation (a
  column or the stop at a column, a value, a record field, an operand, and the stop after each atom where the clause can
  end), with the relation, the column's name, gold's pick and each option's token, kind and P share (STOP and GO for a
  stop);
  The rows also carry neg, rkind, ctype and rtypes (a derived relation's by column position), a column option's ctype, name and key, and an atom
  stop's rel, text, rkind, rtypes, arity and ncols, and its prefix and scope include the finished atom; each row has point_group, {'kind': the
  clause's head, INIT for a port}, and prior_uses, the earlier atoms of the pick's relation, which for an atom stop leave out the finished
  atom (choicefeat.py's docstring has the fields);
- STEER_CHOICE (the path of choicecheap's pickle, choicefeat.Scorer) multiplies the weight of each option of a column, a column stop, a
  field, a value or an operand by exp(STEER_CHOICE_BETA * f), f from the model on the row that CHOICE_ROWS would write at that pick
  (P's shares unsteered; GOLD_Q applies it to gold's path, P never). At a column pick where the atom may stop, the stop and the columns
  are one softmax, so the steered stop chance is the stop's share of the steered weights. The atom stop (phase 'stop') multiplies the odds
  of q's stop hazard, after the tilt's, by exp(STEER_CHOICE_BETA * (f_STOP - f_GO)) on the row of the finished atom. STEER_CHOICE_PHASES
  (default cols,fcol,val,fval,op,stop) limits it. CHOICE_CHECK=path appends the draw-time rows (one JSON line each, with `id`) for choicecheck_cmp.py;
- REL_ROWS=1 writes relrows.jsonl.zst, a frame per point: a row per atom start of gold's clause (k, the types in scope,
  the clause cut before it, gold's option) with each option the decoder allows there (its token, program name, kind,
  columns with their types where known, and P's share of it). In the read graph of the forms before the point, a row
  has the base relations its prefix reads and their deepest depth, and a derived option has `dag`: its base relation,
  whether it is a method or port of that base, the base's readers and depth, whether the prefix reads the same base,
  and the fewest edges from a base the prefix reads (dag_info, dag_path);
- CUT_OPTS=n writes cutopts.jsonl.zst, a frame per point: at each of gold's first n atom starts, each lib or derived
  option's one-atom extension of gold's prefix with a fresh label at each of its columns (every field of a record
  column), evaluated as a cut row (clause, x, x_rows), with k, tok, name and gold (whether it is gold's relation); a
  point stops after CUT_OPTS_SECONDS of CPU on them (cutopts_truncated in its info); with CUT_OPTS_TOP=n only the n
  options of most P weight among all the atom start's options are cut (gold has no place of its own among them);
- VAL_CUTS=1 writes valcuts.jsonl.zst, a frame per point: at each value pick of gold's clause (phase val or fval, the
  atom so far as text), each option's cut: the atom with that value, its other columns completed as for CUT_OPTS, as a
  cut row with k, phase, text, tok and gold (whether it is gold's value); CUT_OPTS_SECONDS caps a point's CPU on them;
- PREFIX_CUTS=1 writes prefcuts.jsonl.zst, a frame per point: before each atom k of gold's clause, gold's clause cut
  after its first k - 1 atoms, as a cut row with k and tok null (fail 'empty prefix' at k 1);
- STRUCT_C=1 gives the column picks and the column stop the structural logit COL_W over the columns and the stop;
- JOIN_P=f multiplies P's weight of a relation that can join a label in scope (after the first atom) by f;
- COL_FREQ=1 names the columns of an atom of a relation with gold counts by each column's rate in gold atoms of that
  relation (each column independently, in order): the next column and the stop take those rates in place of the
  position decay and the site-count stop;
- ORDER_FREE=col,tie,key (default unset: none) turns on the readings of a body as a DAG that the walk had in written order: `col` gives the columns of a derived
  relation a coin each by (place, kind, in scope) (col_kind: the column's type, or @Record, @Example, @unknown; COL_TYPE, counted by col_type_counts.py), so that a set of columns has one chance in any column order, and
  zeroes COL_W's back; `tie` breaks the tie of equal chances in a search by the options' facts, not their order (search.py); `key` picks a key's labels by the
  types of their sites (live.Run.key_pick, with the priors' key_types from key_type_counts.py). A setting that is unset keeps the draws and the chances as they were;
- KEY_IDENT=rel (default unset: none) multiplies the weight of a declared relation that has an Ident column by m (the priors' key_rel, from key_rel_counts.py) at an atom start of an INIT's key body
  where no label in scope has the type Ident and no rel steer acts (live.Run.key_rel_m). Unset, or with priors that have no key_rel, m is 1: the weights and the draws are as they were;
- STEER_DERIVED=<file> (default unset: off), a file of the models folder, replaces the relation steer's split at an atom start where STEER_REL is on, INIT
  bodies included: a gate g gives the derived relations the share g of P's total there and the other options 1 - g; the derived relations share theirs by
  the model's conditional logit over facts of the scope's DAG and tables, and the others keep the steered shape (Drawer.derived_steer);
- STEER_REL_GROUPS=1 (default unset: off) keeps P's split between the derived relations and the other options at an atom start under STEER_REL: each group's steered
  weights are scaled to that group's total before the steer, so the steer moves weight only within a group (Drawer.group_steer). Unset, the steer multiplies each option's weight;
- SEED_TAG (default v2) seeds each point's draws, so a run with another tag draws other programs at the same points; with
  --engine-stats, a point's info gives its CPU ms per engine phase (`engine`);
- a DET's value in an assignment is its value hash (the engine's), so a point's tables repeat the same assignments at no cost.
- --split holdout draws the holdout tasks' points; the prior and the hazards are dev's either way.
- ROW_ORDERS=n gives REL_ROWS and CHOICE_ROWS for n random valid orders of gold's clause in place of the written one, and each row has `order`
  (0 to n - 1). GOLD_ORDERS=all adds to gold's row logq_orders, gold's log q summed over its valid orders, each order's q as GOLD_Q gives it.
  An order is valid where the decoder takes its tokens through the clause's END and the clause's rows do not change; in an order the first
  occurrence of a label is `*` and the later ones are reads (reorder), so its tokens differ from gold's. The orders come from a seed of the
  task and the clause (order_rng). Both settings turn on ANCESTOR_PREFIX. A clause of at most 5 atoms takes all its orders; a longer clause
  takes GOLD_ORDER_CAP orders at random, with the sum estimated as the number of orders times the mean q. An order with an atom after a compound
  has q 0, since a draw ends at a compound, so only orders with the compound last are scored and counted in that estimate; the row's
  orders_n counts every valid order where n <= 5, orders_drawn the orders with the compound last (estimated above 5 atoms), and order_q each
  scored order's atoms and log q;
- ANCESTOR_PREFIX=1 gives a point a prefix of its clause's ancestors by reads only, in an order that reads no written position, so slot numbers
  follow from the DAG (ancestor_order, ancestor_spec); gold's tables, GOLD_Q, the rows and the draws all stand on that prefix. A run with it has
  no --samples, whose records are in the slots of the written program;
- --seconds is the CPU budget of a point's draws; the point's setup (the prefix's tables, which the engine computes at
  every model step, and gold's row) is outside it, and its CPU is the info's setup_cpu.

  scripts/run_heavy.py --cpus N --need now <runtime python> -u sample2.py --out DIR [--points 50] [--draws 200]
      [--jobs N] [--seconds 20] [--samples]
"""
import argparse
import collections
import concurrent.futures as cf
import contextlib
import functools
import resource
import gzip
import hashlib
import itertools
import json
import math
import os
import pickle
import random
import re
import statistics
import sys
import time
import traceback

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sample import M, arclog, M_sexprs, SHAPES, SPLITS, TASKS, OPS, CORPUS, body_hazard, GOLD_APPROXIMATED, left_out, first_row, table_rows, static_prune, n_forms  # noqa: E402
import sample as _sample  # noqa: E402
import table_adapter as TA  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sampler_paths as P  # noqa: E402
STUDY = P.STUDY
sys.path += [STUDY, STUDY + '/features']
import featlib  # noqa: E402
import strata  # noqa: E402
from col_type_counts import col_kind  # noqa: E402
from rulecheck import PREFIX_CLASSES, RuleCheck, rename_relations  # noqa: E402
sys.path.append(P.CODE)
from judge3.framed_jsonl import JsonlWriter, iter_json  # noqa: E402
_path = list(sys.path)
sys.path[:0] = [P.CODE + '/ast/run', P.CODE + '/ast/run/mech',
                P.CODE]
import sample_label as sl  # noqa: E402
sys.path[:] = _path
SOURCE_REVISION = hashlib.sha256(open(__file__, 'rb').read()).hexdigest()[:16]  # the producer's revision, in each candidate

FSTORE = os.environ.get('SAMPLER_FSTORE', P.DATA + '/feat-exp/fstore-gen3/points-t/')
REGISTRY = P.REPO + '/engine/lib/registry.sexpr'
GEN = os.environ.get('SAMPLER_GEN', P.DATA + '/gold/gen-v3-11f6a212c/corpus/gen')
MAX_ATOMS = int(os.environ.get('MAX_ATOMS', '16'))  # gold bodies reach 12 atoms
BACK_COL = float(os.environ.get('BACK_COL', '0.02'))  # the weight factor of a column below the last column named, which gold sometimes names after it
ZERO_FLOOR = 0.05  # the zero count of a column where gold never writes 0
MEMO_CAP = 512  # prefixes whose checks a point keeps
ROOT_CAP = 256  # atom-start frontiers (roots, with their nodes) a point keeps
NODE_CAP = 30000  # nodes made since the frontiers were last dropped, at which Drawer.frontier drops them
ALPHA = 0.5
JOIN_BOOST = float(os.environ.get('JOIN_BOOST', '1'))
SAFE_PREFIX = os.environ.get('SAFE_PREFIX', '1') == '1'
JOINABLE_BOOST = float(os.environ.get('JOINABLE_BOOST', '1'))
STATIC_MASK = os.environ.get('STATIC_MASK', '1') == '1'
ATOM_TRIES = 8
CHEAP_TRIES = 24  # redraws for a repeated atom or an unjoined one (a few ms each), apart from ATOM_TRIES
SP_CUT_EXEMPT = frozenset()  # SP keys that fire on a gold clause cut after some atom: the per-atom check leaves them out
MAX_FIELDS = 6
IDENT_SOURCE = os.environ.get('ARCLOG_IDENT_SOURCE', 'type') not in ('', '0')  # the engine gives each Ident column one source, so the decoder says which labels a column admits
COMPLETE = os.environ.get('COMPLETE', '1') == '1'
COMPLETE_BUDGET = 80
REACH = os.environ.get('REACH', '1') == '1'
# What reachable()'s cache is keyed by, beside (relation, negation, phase, last column, need, column): 'state' the frontier root (the clause's tokens before
# the atom and its label count) and the atom's tokens so far, which fix the decoder's state, so a result holds only there; 'labs' the label count; 'old' nothing.
# REACH_CHECK=1 recomputes each cache hit and counts those that differ (reach_stats in a point's info).
REACH_KEY = os.environ.get('REACH_KEY', 'state')
REACH_CHECK = os.environ.get('REACH_CHECK', '') == '1'
OUTPUT_GATE = os.environ.get('OUTPUT_GATE', '1') == '1'
COMPOUND = os.environ.get('COMPOUND', '1') == '1'
STATIC_ATOM = os.environ.get('STATIC_ATOM', '1') == '1'  # an atom is redrawn where the static prune matches it
ROW_ORDERS = int(os.environ.get('ROW_ORDERS', '0'))  # REL_ROWS and CHOICE_ROWS: this many random valid orders per clause; 0: the written order
GOLD_ORDERS = os.environ.get('GOLD_ORDERS', '') == 'all'  # GOLD_Q: logq_orders, gold's log q summed over its valid orders
GOLD_ORDER_CAP = int(os.environ.get('GOLD_ORDER_CAP', '24'))  # the orders scored for a clause of more than 5 atoms
ORDER_SHUFFLES = 2000  # the random orders tried for a clause of more than 5 atoms
ORDER_EXACT = 12  # BodyOrders: a body of at most this many atoms has its orders' law in full
ORDER_SAMPLES = 1024  # BodyOrders: the orders drawn for a longer body
ANCESTOR_PREFIX = os.environ.get('ANCESTOR_PREFIX', '') == '1' or ROW_ORDERS > 0 or GOLD_ORDERS  # a point's prefix holds only its clause's ancestors by reads (ancestor_spec)
SEED_TAG = os.environ.get('SEED_TAG', 'v2')  # a point's draws follow seed_of(task, case, point, SEED_TAG); another tag gives other draws
HAZARD_GROUP = os.environ.get('HAZARD_GROUP', '') == '1'  # a RULE point's stop factors come from the gold bodies of its own point group
PREFIX_DRAWS = os.environ.get('PREFIX_DRAWS', '') == '1'  # each passing draw and gold also give their clause cut at each atom where it can end
STRUCT_P = os.environ.get('STRUCT_P', '') == '1'  # P's relation and value weights take the structural logits (REL_W, VAL_W)
P_DAG = False  # live.set_steers sets this from the environment. On: P's value weights read no label number. The labels of a value pick share its join weight, and STRUCT_P's value logit takes a label's type by its name
STAR_NAME = re.compile(r'\*([A-Za-z_]\w*)')  # a label's first site in a prefix atom, as choicefeat has it
# fitted by relfit.py and valfit.py on dev gold picks (runR_dev, runD_dev), tested on holdout
REL_W = dict(logp=0.83, lib=-0.20, derived=-0.19, op=0.39, lib_k1=0.08, derived_k1=1.30, op_k1=-1.37, in_scope=0.15,
             in_scope_frac=0.52, none_in_scope=-0.48, arity=0.10, repeat=-0.27, recency0=0.09, recency_log=-0.48, no_types=0.12)
VAL_W = dict(logp=0.82, fresh=-0.91, zero=-0.28, label=0.30, field=0.89, newest=-0.24, recency_log=-0.29, type_same=0.92,
             type_differs=0.51, in_atom=-2.78)
STRUCT_C = os.environ.get('STRUCT_C', '') == '1'  # P's column picks and column stop take the structural logit COL_W
# fitted by colfit.py on dev gold picks (runD_dev, runR_dev), tested on holdout
COL_W = dict(logp=0.84, stop=-0.22, col0=0.77, pos_log=0.08, type_in_scope=0.27, type_count_log=0.37, type_unknown=0.04,
             derived=0.28, input=-0.36, k1=0.04, stop_named=-0.59, stop_named0=-0.23, stop_left_in_scope=0.08,
             stop_derived=-0.28, stop_k1=-0.04, back=0.01, after_gap=-0.26)
ARITY_CAP = os.environ.get('ARITY_CAP', '1') == '1'
FIELD_MEMO = os.environ.get('FIELD_MEMO', '1') == '1'
ADMITS = os.environ.get('ADMITS', '') == '1'  # a node's decoder checks are one Decoder.admits call (a runtime that has it)
ROOT_ADMITS = os.environ.get('ROOT_ADMITS', '1') == '1' and hasattr(arclog.Decoder, 'admits')  # an atom start's checks are one Decoder.admits call over its start tokens, where the runtime has it
PRUNE_SESSION = os.environ.get('PRUNE_SESSION', '1') == '1'  # static_prune reads its program through the point's session, whose check cache keeps the checks of the forms that candidates share
GC_TUNE = os.environ.get('GC_TUNE', '1') == '1'  # the cyclic collector runs less often: the sampler's data is long-lived and holds few cycles
PRUNE_SESSIONS = {}  # 'sess' -> the point's session; set by run_point


def static_prune(prog_text, clause_index, settings, _plain=_sample.static_prune):  # noqa: F811
    """sample.static_prune, reading the program through the point's session where PRUNE_SESSION is set."""
    sess = PRUNE_SESSIONS.get('sess')
    if not PRUNE_SESSION or sess is None:
        return _plain(prog_text, clause_index, settings)
    try:
        try:
            sp = arclog.StudyProgram.from_sexp(prog_text + '\n(OUT (input ^P ^Col))', settings, session=sess)
        except TypeError:  # a runtime whose from_sexp takes no session
            return _plain(prog_text, clause_index, settings)
        except ValueError as e:
            if 'settings differ' not in str(e):
                raise
            return _plain(prog_text, clause_index, settings)
        js = json.loads(sp.static_prune_json())
    except Exception as e:  # noqa: BLE001
        return None, '%s: %s' % (type(e).__name__, str(e)[:200])
    return js, None

ARITY_CHECK = os.environ.get('ARITY_CHECK', '') == '1'  # with ARITY_CAP=0, stderr names each column admitted past a learned arity
ADM_STATS = collections.Counter() if os.environ.get('ADM_STATS') else None  # (phase, token kind, admitted) -> count of Decoder.forced checks
PREFIX_CUTS = os.environ.get('PREFIX_CUTS', '') == '1'  # prefcuts.jsonl.zst: gold's clause cut before each of its atoms
STRUCT_B = os.environ.get('STRUCT_B', '') == '1'  # with STRUCT_P, the relation logit also takes explorer b's box-relation terms (REL_WB)
REL_WB = dict(logp=0.84, lib=-0.25, derived=-0.15, op=0.39, lib_k1=0.40, derived_k1=1.01, op_k1=-1.41, in_scope=0.04,
              in_scope_frac=0.20, none_in_scope=-0.48, arity=0.12, repeat=0.22, recency0=-0.12, recency_log=-0.45, no_types=0.07,
              b_ready=1.38, b_boxpos=1.96, b_follows_crop=2.09, b_follows_relative=0.22, b_repeat=0.34, b_fits_enum=2.13,
              b_listed=-1.71)  # relfit.py --b on runR_dev
if STRUCT_B:
    sys.path.append(STUDY + '/features')
    from r14b import FOLLOWS_INSIDE, FOLLOWS_RELATIVE, INPUT_SLOTS, REPEATS, _sub  # noqa: E402
CHOICE_ROWS = os.environ.get('CHOICE_ROWS', '') == '1'  # choices.jsonl.zst: every other forced pick of gold with its options
REL_ROWS = os.environ.get('REL_ROWS', '') == '1'  # relrows.jsonl.zst: at each gold atom start, the options and gold's pick
CUT_OPTS = int(os.environ.get('CUT_OPTS', '0'))  # cutopts.jsonl.zst: gold's first CUT_OPTS atom starts, each option's one-atom cut
VAL_CUTS = os.environ.get('VAL_CUTS', '') == '1'  # valcuts.jsonl.zst: each value option's cut at each value pick of gold
CUT_OPTS_TOP = int(os.environ.get('CUT_OPTS_TOP', '0'))  # with n > 0, only the n options with the most P weight at the atom start are cut
CUT_OPTS_SECONDS = float(os.environ.get('CUT_OPTS_SECONDS', '120'))  # a point's CPU for its option cuts, after which the rest are skipped
JOIN_P = float(os.environ.get('JOIN_P', '1'))  # P's factor on a relation that can join a label in scope, after the first atom
COL_FREQ = os.environ.get('COL_FREQ', '') == '1'  # a lib relation's columns are named by their rates in gold atoms
STEER_M = int(os.environ.get('STEER_M', '1'))  # candidate atoms per steered atom; 1 is no steering
STEER_K = int(os.environ.get('STEER_K', '3'))  # the last atom index that is steered
STEER_BETA = float(os.environ.get('STEER_BETA', '1'))
STEER_MODEL = os.environ.get('STEER_MODEL', P.DATA + '/feat-exp/data/soft/cut_p2.npz')
STEER_ONLINE = os.environ.get('STEER_ONLINE', '')  # with STEER_M > 1, a cut is scored by the feature study's online scorer: '1' its rules and soft score, 'norows' its soft score without X rows, 'cut' the feature study's cut scorer (cut_score.CutScorer)
STEER_GROUPS = [g for g in os.environ.get('STEER_GROUPS', '').split(',') if g]  # the point groups where STEER_M applies; empty: every group
STEER_GQ_R = int(os.environ.get('STEER_GQ_R', '8'))  # GOLD_Q with STEER_M > 1: replicates of the other candidates per steered gold atom
STEER_FLOOR = -10.0  # the score of a cut that the score cannot read (no table or no clause)
EMPTY_ATOM = os.environ.get('EMPTY_ATOM', '1') == '1'  # an atom is redrawn where it makes the prefix's X empty on every train entry
STEER_REL = os.environ.get('STEER_REL', '')  # path of relcheap's pickle (relsteer.Scorer): at a root-phase atom start each option's weight is multiplied by exp(STEER_REL_BETA * f); unset: off
STEER_REL_BETA = float(os.environ.get('STEER_REL_BETA', '1'))
STEER_REL_GROUPS = os.environ.get('STEER_REL_GROUPS', '') == '1'  # the steer keeps P's total of the derived relations and of the other options (see the module docstring)
STEER_DERIVED = ''  # the path of the derived-pick model; live.set_steers sets it from the setting STEER_DERIVED (see the module docstring)
DERIVED_STATS = collections.Counter()  # STEER_DERIVED: calls, cache misses and CPU seconds of derived_steer
REL_CHECK = os.environ.get('REL_CHECK', '')
STEER_CHOICE = os.environ.get('STEER_CHOICE', '')  # path of choicecheap's pickle (choicefeat.Scorer): at a column, field, value or operand pick each option's weight is multiplied by exp(STEER_CHOICE_BETA * f); unset: off
STEER_CHOICE_BETA = float(os.environ.get('STEER_CHOICE_BETA', '1'))
STEER_CHOICE_PHASES = frozenset(os.environ.get('STEER_CHOICE_PHASES', 'cols,fcol,val,fval,op,stop').split(','))  # 'stop' is the atom stop; a phase that the model was not trained on is not steered
CHOICE_CHECK = os.environ.get('CHOICE_CHECK', '')
STEER_REL_MODEL = os.environ.get('STEER_REL_MODEL', 'hgb')  # 'hgb' (the tree) or 'logit'
STEER_COVER = frozenset(filter(None, os.environ.get('STEER_COVER', '').split(',')))  # places where the steers go beyond S's draw: 'init' (the bodies of an INIT's key and ports, which the prefix text gives), 'branch' (the first atom of a later branch of an OR, whose clause cannot close)
ORDER_FREE = frozenset(filter(None, os.environ.get('ORDER_FREE', '').split(',')))  # 'col', 'tie', 'key': a body read as a DAG where the walk read its written order (see the module docstring)
IDENT = frozenset({'Ident'})
KEY_IDENT = frozenset(filter(None, os.environ.get('KEY_IDENT', '').split(',')))  # 'rel': an INIT key body's first Ident relation is likelier (see the module docstring)
COL_TYPE = {('DET', '@Example', False): 0.861, ('DET', '@Record', False): 0.904, ('DET', '@unknown', False): 0.643, ('DET', 'Axis', False): 0.501, ('DET', 'Axis', True): 0.84, ('DET', 'Box', False): 0.603, ('DET', 'Box', True): 0.673, ('DET', 'Color', False): 0.585, ('DET', 'Color', True): 0.76, ('DET', 'D4', False): 0.506, ('DET', 'D4', True): 0.94, ('DET', 'DiagDir', False): 0.663, ('DET', 'DiagDir', True): 0.793, ('DET', 'Dir', False): 0.499, ('DET', 'Dir', True): 0.666, ('DET', 'Dir8', False): 0.573, ('DET', 'Example', False): 0.643, ('DET', 'Example', True): 0.893, ('DET', 'Ident', False): 0.721, ('DET', 'Ident', True): 0.928, ('DET', 'Int', False): 0.611, ('DET', 'Int', True): 0.927, ('DET', 'Nat', False): 0.706, ('DET', 'Nat', True): 0.914, ('DET', 'Offset', False): 0.555, ('DET', 'Position', False): 0.551, ('DET', 'Position', True): 0.696, ('RULE', '@Example', False): 0.474, ('RULE', '@Record', False): 0.929, ('RULE', '@unknown', False): 0.744, ('RULE', 'Axis', False): 0.487, ('RULE', 'Axis', True): 0.827, ('RULE', 'Axis4', False): 0.779, ('RULE', 'Box', False): 0.636, ('RULE', 'Box', True): 0.745, ('RULE', 'C4', False): 0.643, ('RULE', 'Color', False): 0.72, ('RULE', 'Color', True): 0.82, ('RULE', 'D4', False): 0.677, ('RULE', 'D4', True): 0.97, ('RULE', 'DiagAxis', False): 0.608, ('RULE', 'DiagAxis', True): 0.94, ('RULE', 'DiagDir', False): 0.586, ('RULE', 'DiagDir', True): 0.928, ('RULE', 'Dir', False): 0.546, ('RULE', 'Dir', True): 0.782, ('RULE', 'Dir8', False): 0.584, ('RULE', 'Dir8', True): 0.882, ('RULE', 'Ident', False): 0.789, ('RULE', 'Ident', True): 0.952, ('RULE', 'Int', False): 0.551, ('RULE', 'Int', True): 0.816, ('RULE', 'Nat', False): 0.479, ('RULE', 'Nat', True): 0.767, ('RULE', 'Offset', False): 0.569, ('RULE', 'Offset', True): 0.9, ('RULE', 'Pose', False): 0.664, ('RULE', 'Position', False): 0.743, ('RULE', 'Position', True): 0.738, ('RULE', 'Sense', False): 0.482, ('RULE', 'Sense', True): 0.964, ('RULE', 'Sym', False): 0.505, ('key', '@Example', False): 0.037, ('key', '@Record', False): 0.968, ('key', '@unknown', False): 0.561, ('key', 'Axis', False): 0.511, ('key', 'Box', False): 0.55, ('key', 'Color', False): 0.513, ('key', 'Color', True): 0.993, ('key', 'D4', False): 0.828, ('key', 'DiagDir', False): 0.611, ('key', 'Dir', False): 0.616, ('key', 'Example', False): 0.917, ('key', 'Ident', False): 0.866, ('key', 'Int', False): 0.346, ('key', 'Nat', False): 0.479, ('key', 'Position', False): 0.566, ('key', 'Position', True): 0.695, ('port', '@Example', False): 0.023, ('port', '@Record', False): 0.944, ('port', '@unknown', False): 0.561, ('port', 'Axis', False): 0.619, ('port', 'Axis', True): 0.669, ('port', 'Box', False): 0.574, ('port', 'Color', False): 0.548, ('port', 'Color', True): 0.93, ('port', 'D4', False): 0.791, ('port', 'DiagDir', False): 0.486, ('port', 'Dir', False): 0.581, ('port', 'Dir', True): 0.734, ('port', 'Dir8', False): 0.851, ('port', 'Example', False): 0.842, ('port', 'Ident', False): 0.83, ('port', 'Ident', True): 0.943, ('port', 'Int', False): 0.82, ('port', 'Nat', False): 0.74, ('port', 'Offset', False): 0.881, ('port', 'Position', False): 0.697, ('port', 'Position', True): 0.79}  # ORDER_FREE col: (place, column kind (col_kind), kind in scope) -> the chance that an atom of a derived relation names a column of that kind (col_type_counts.py counts it from the rows)
COL_TYPE_DEFAULT = {('DET', False): 0.618, ('DET', True): 0.783, ('RULE', False): 0.668, ('RULE', True): 0.794, ('key', False): 0.496, ('key', True): 0.836, ('port', False): 0.537, ('port', True): 0.846}  # the chance for a kind that COL_TYPE has no entry for, by place and kind in scope
UNREAD_BETA = float(os.environ.get('UNREAD_BETA', '0'))  # nats added to the log weight of a derived option whose form no kept form reads (Drawer.unread); 0: off
UNREAD_BOOST = math.exp(UNREAD_BETA)
TILT = os.environ.get('TILT', '')  # path of a JSON file of score tilts (tilt_fit.py): q's weight of a choice is multiplied by exp(TILT_BETA * TILT_SCALE * theta); unset: no tilt, the draws are unchanged
TILT_BETA = float(os.environ.get('TILT_BETA', '0.5'))  # the beta of the target
TILT_SCALE = float(os.environ.get('TILT_SCALE', '1'))  # 1: the fitted theta in full; below 1: shrunk
TILT_STOP = os.environ.get('TILT_STOP', '1')  # q's stop hazard takes a tilt for the clause length: '1' the score's part (beta * stop_tau), 'lw' the fitted shift of log(P/q) + beta s with the length (stop_tau_lw, in nats), '0' none
TILT_STOP_CLAMP = float(os.environ.get('TILT_STOP_CLAMP', '1.0'))  # the largest odds shift of a stop, in nats
TILT_TABLE = json.load(open(TILT))['groups'] if TILT else None
TILT_CMP = {v: k for k, v in OPS.items()}  # 'cmp:Ne' -> '!='


def tilt_nk(atext):
    """A drawn atom's feature name for the tilt table: the relation kind of its text, with N before it under NOT."""
    neg = atext.startswith('(NOT')
    m = re.match(r'\(([^\s()]+)', atext[5:] if neg else atext)
    rel = m.group(1) if m else '?'
    kind = 'cmp:' + rel if rel in TILT_CMP.values() else 'der' if rel.startswith('&r') else 'OR' if rel == 'OR' else 'lib:' + rel
    return ('N' if neg else '') + kind


def tilt_stop_odds(tab, k):
    """The log odds shift of q's stop hazard after k atoms: the clause-length part of the tilt."""
    lw = TILT_STOP == 'lw'
    st = tab.get('stop_tau_lw' if lw else 'stop_tau')
    if not st or TILT_STOP == '0':
        return 0.0
    v = (1.0 if lw else TILT_BETA) * TILT_SCALE * st[min(k, len(st)) - 1]
    return max(-TILT_STOP_CLAMP, min(TILT_STOP_CLAMP, v))


FACTS = {'input', 'ex_input', 'ex_output'}
NO_ROWS = {'fields': [], 'entries': []}  # X of a check that reads no table
RULE_TOK, IF_TOK, ALSO_TOK = 0, 9, 13
MAX_BRANCH = 6
WANT_BOOST = float(os.environ.get('WANT_BOOST', '1'))
NEED_BOOST = float(os.environ.get('NEED_BOOST', '1'))
# At the clause that OUT reads, the boosts for the needed types and the wanted labels are NEED_BOOST_OUT and WANT_BOOST_OUT.
# They scale weights that q alone uses, and q's share of each pick includes them, so logq_full stays q's probability.
NEED_BOOST_OUT = float(os.environ.get('NEED_BOOST_OUT', '4'))
WANT_BOOST_OUT = float(os.environ.get('WANT_BOOST_OUT', '4'))
# At the clause that OUT reads, a stop is refused where the feature study's q5c_output_cells.fewer_cells_f1 fires on the table
# (a hard rule: no Position column of X paints every cell of the output). The gate is a function of the state, like the
# 'out columns' gate, so p goes on with probability 1 - h and q goes on with probability 1.
# A branch of a compound stops only where it can close. A stop that is refused there counts log(1 - h) in p, as the stop gates
# of the atom loop do; BRANCH_GATE_P=0 leaves it out.
BRANCH_GATE_P = os.environ.get('BRANCH_GATE_P', '1') == '1'
CELLS_GATE = os.environ.get('CELLS_GATE', '1') == '1'
UNJOINED = 0.14  # the value for priors with no 'hand'; otherwise the fit's hand_counts gives it (live.set_hand)
PROG_CHUNK = int(os.environ.get('PROG_CHUNK', '4'))  # points of one gold program to a job; a job holds its points' draw rows (with X rows) until it ends
SESSION_BYTES = int(os.environ.get('SESSION_BYTES', '0')) or None  # a point's session cap; a job past it gives an error row, where it would hold the whole machine
X_ROWS_CAP = 2000  # rows kept per entry of a draw's X; gold's X keeps all
MIN2_KINDS = {'DET', 'RULE'}  # kinds of point where a draw may not stop at one atom, except at the output clause or with a method call (one_call)
ONE_CALL = os.environ.get('ONE_CALL', '1') == '1'
DERIVED_GROUPS = {'INIT port'}  # point groups where gold's body reads a derived relation
MAX_UNREAD = 1  # labels that a port body makes and nothing reads: gold has at most 1
P_REEXPORT = 0.33  # the value for priors with no 'hand'; otherwise the fit's hand_counts gives it (live.set_hand). Gold's final OR exports a label of its first branch that the branch reads again: output 113 of 334, elsewhere 86 of 269
P_UNNAMED = 0.02  # a later branch of a final OR may close without naming every exported label, away from the output clause: gold 6 of 274
P_UNREAD_LOCAL = 0.015  # a later branch may close with a label it makes and does not read: gold 8 of 515
BRANCH_TRIES = 3  # draws of a later branch of a final OR, each from the branch's start
# EXACT=1: a rejected atom or branch is redrawn by a fixed-count scheme whose acceptance estimate A^ enters logq_full, so that the weights
# are exact in expectation (pseudo-marginal). An atom site draws EXACT_N1 candidates i.i.d. from q0, applies the cheap checks (repeat, prefix
# key, unjoined) to all of them (K1 pass), applies the expensive checks (construct, can end, empty, static) to the first min(K1, EXACT_N2)
# passers (K2 of N2' pass), picks the first candidate that passed both, and takes A^ = (K1 / N1) (K2 / N2'). A later branch of a final OR is
# drawn BRANCH_N times from its start; the first that closes is picked, and A^ = K_b / BRANCH_N.
EXACT = os.environ.get('EXACT', '') == '1'
# EXACT_COIN=1: an atom's log q is the mixture over the must_join coin, in place of q given the drawn coin (the draws are unchanged).
# The accepted atom's proposal density is u q_free(x) + (1 - u) q_join(x) [x is joined, or the caller does not reject unjoined atoms], with u = UNJOINED.
EXACT_COIN = os.environ.get('EXACT_COIN', '') == '1'
COIN_LOG = os.environ.get('COIN_LOG', '')
# GOLD_Q=1: gold's row also gets logq_steer, the log probability of gold's path under the proposal that the draws use (the steer weights with the
# tilt, the coin mixture, the stop hazard with its tilt and the gates, and at each atom site log A^ from EXACT_N1 fresh candidates, drawn with a
# separate rng stream), and logq_steer_parts per atom. The draws are unchanged. With STEER_M > 1, each candidate of a steered atom site comes from
# the EXACT sampler with its own A^ (the picked candidate's A^ enters logq_full), and gold's site q gains the SIR factor, from STEER_GQ_R replicates
# of the other m - 1 candidates. A compound atom of gold (a last OR) is scored by gold_compound: p_comp, the shape, each branch's atoms, stops and
# separators, the negation and export draws, and the gates are known, and the acceptance of each branch atom and the chance that a try of a later
# branch fails (GQ_BRANCH_N tries) are estimated; the part's `comp` has the factors.
GOLD_Q = os.environ.get('GOLD_Q', '') == '1'
EXACT_N1 = int(os.environ.get('EXACT_N1', str(CHEAP_TRIES + ATOM_TRIES)))
EXACT_N2 = int(os.environ.get('EXACT_N2', '4'))
BRANCH_N = int(os.environ.get('BRANCH_N', '1'))
GQ_BRANCH_N = int(os.environ.get('GQ_BRANCH_N', '32'))  # GOLD_Q: tries of a later branch of gold's compound that estimate the chance that a try fails


FAMILIES = [{'Position', 'Box', 'Offset'}, {'Int', 'Nat', 'Number'}, {'Dir', 'Dir8', 'DiagDir'}, {'Axis', 'Axis4', 'DiagAxis'},
            {'D4', 'C4', 'Sym'}]


FAMILY = {t: i for i, f in enumerate(FAMILIES) for t in f}


def dag_info(forms, i):
    """The read graph of the program's forms before form i, as a function from a relation's base name (&grp of &grp.equal)
    to its fields, and the graph for dag_path: readers (forms before i that read it), depth (strata's depth of its
    defining form, 0 where no form before i defines it) and defined (whether one does)."""
    heads, body, kind, d = strata._depths(forms[:i])
    readers = collections.Counter(r for rs in body.values() for r in rs)
    adj = collections.defaultdict(set)
    for j, rs in body.items():
        h = forms[j][1]
        for r in rs:
            adj[h].add(r)
            adj[r].add(h)

    def fields(base):
        return dict(readers=readers.get(base, 0), depth=d(heads[base]) if base in heads else 0, defined=base in heads)
    return fields, adj


def dag_path(adj, srcs, dst, cap=8):
    """The fewest edges between dst and any of srcs in the undirected read graph adj, or None beyond cap or unreached."""
    if dst in srcs:
        return 0
    seen, front = set(srcs), set(srcs)
    for n in range(1, cap + 1):
        front = {y for x in front for y in adj.get(x, ()) if y not in seen}
        if dst in front:
            return n
        if not front:
            return None
        seen |= front
    return None


def top_cols(text):
    """The number of columns an atom's text names (the fields of a record column are not counted)."""
    return sum(1 for m in re.finditer(r'\(:', text) if text[:m.start()].count('(') - text[:m.start()].count(')') == 1)


def body_atoms(clause):
    """The top-level atoms of a clause's body, as text."""
    out, depth, start, inner = [], 0, None, clause[1:-1]
    for i, ch in enumerate(inner):
        if ch == '(':
            if depth == 0:
                start = i
            depth += 1
        elif ch == ')':
            depth -= 1
            if depth == 0:
                out.append(inner[start:i + 1])
    return out


def label_sites(V, atoms):
    """{(atom, token position): label number} of the label sites of a clause's atoms (token lists): a `*` has the next number, and
    a label token has its own."""
    out, n = {}, 0
    for a, toks in enumerate(atoms):
        for j, t in enumerate(toks):
            if t == M.STAR:
                out[a, j], n = n, n + 1
            elif V.kind(t) == 'label':
                out[a, j] = int(V.name(t)[1:])
    return out


def guard_reads(atoms, sites):
    """Per atom, the labels it needs bound before it: a NOT's and a comparison's reads, which bind nothing. Other atoms need none."""
    return [{sites[a, j] for j, t in enumerate(toks) if (a, j) in sites and t != M.STAR} if toks[0] == M.NOT or toks[0] in M.CMP else set()
            for a, toks in enumerate(atoms)]


def reorder(atoms, sites, order, label_tok):
    """The tokens of atoms in the order `order`: a label's first occurrence is `*`, and a later one is a read of the label's new
    number. None where a NOT or a comparison comes before the labels it reads."""
    num, out = {}, []
    for a in order:
        toks = list(atoms[a])
        guard = toks[0] == M.NOT or toks[0] in M.CMP
        for j, t in enumerate(toks):
            lab = sites.get((a, j))
            if lab is None:
                continue
            if lab in num:
                toks[j] = label_tok[num[lab]]
            elif guard and t != M.STAR:
                return None
            else:
                num[lab] = len(num)
                toks[j] = M.STAR
        out.append(toks)
    return out


def random_orders(items, rng):
    """Distinct orders of items, each uniform among those not given yet: all of them for at most 5 items, else up to ORDER_SHUFFLES tries."""
    if len(items) <= 5:
        orders = list(itertools.permutations(items))
        rng.shuffle(orders)
        yield from orders
        return
    seen = set()
    for _ in range(ORDER_SHUFFLES):
        o = tuple(rng.sample(items, len(items)))
        if o not in seen:
            seen.add(o)
            yield o


def count_orders(atoms, sites, items):
    """The number of orders of the atoms items where each NOT and comparison comes after the labels it reads."""
    needs = guard_reads(atoms, sites)
    labs = [{sites[a, j] for j in range(len(atoms[a])) if (a, j) in sites} for a in items]
    ways = {0: 1}
    for size in range(len(items)):
        nxt = collections.Counter()
        for mask, w in ways.items():
            bound = set().union(*[labs[i] for i in range(len(items)) if mask >> i & 1])
            for i, a in enumerate(items):
                if not mask >> i & 1 and needs[a] <= bound:
                    nxt[mask | 1 << i] += w
        ways = nxt
    return sum(ways.values())


def lse(xs):
    """log of the sum of exp(x) over xs."""
    m = max(xs, default=-math.inf)
    return m + math.log(sum(math.exp(x - m) for x in xs)) if m > -math.inf else -math.inf


RELATION_KINDS = ('relation', 'lib relation', 'relation macro', 'fact relation')  # the decoder's kinds of a relation token


def atom_uses(V, toks):
    """The atoms of the model tokens toks (vocabulary V), in order, as (relation token, {column token: how the atom binds it}):
    'fresh' for a * or ^, 'read' for a label, 'zero' for 0 and 'rec' for a record value. A NOT, a comparison and a compound's
    keyword end the atom before; the atoms inside a compound count as atoms."""
    out, cur, col, rec = [], None, None, False
    for t in toks:
        if rec:
            rec = t != M.END
            continue
        k = V.kind(t)
        if k in RELATION_KINDS:
            cur, col = {}, None
            out.append((t, cur))
        elif cur is None:
            continue
        elif k == 'column':
            if col is None:
                col = V.name(t)
            else:  # a column right after a column: the first is a record's, and this is its field
                cur[col], col, rec = 'rec', None, True
        elif col is not None and (t in (M.STAR, M.CARET, M.ZERO) or k == 'label'):
            cur[col], col = 'zero' if t == M.ZERO else 'fresh' if t in (M.STAR, M.CARET) else 'read', None
        else:
            cur, col = None, None
    return out


def prior_history(V, ids, model, paths, clause):
    """(the head of clause `clause` of the program stream (ids, model, paths), {relation token: [the uses of it in the clauses
    before, oldest first, as a CHOICE_ROWS row's prior_uses lists them]})."""
    start = next(i for i, p in enumerate(paths) if p and p[0] == clause)
    hist = collections.defaultdict(list)
    for t, cols in atom_uses(V, [ids[i] for i in range(start) if model[i]]):
        hist[t].append(dict(same_clause=False, cols=cols))
    return V.name(ids[start]), hist


def compat(a, b):
    return a == b or FAMILY.get(a, -1) == FAMILY.get(b, -2)


@functools.lru_cache(maxsize=None)
def compat_any(scope, ts):
    return any(compat(a, b) for a in scope for b in ts)


def column_type(ts, cols, pos, field=None):
    """The type of column pos of a relation, or of its field `field` where the column is a record: from cols (a
    column_positions entry) for a declared relation, else from ts (a lib, macro or fact relation's types by position);
    None where unknown."""
    if cols is not None:
        return cols.get((pos, field))
    return str(ts[pos]) if ts and field is None and 0 <= pos < len(ts) else None


@functools.lru_cache(maxsize=4)
def vocab_columns(V):
    """([(position, token)] of the vocabulary's column tokens, in position order; [(slot, token)] of its relation tokens)."""
    cols = sorted((int(V.name(i)[1:]), i) for i in range(len(V)) if V.kind(i) == 'column' and V.name(i)[1:].isdigit())
    return cols, [(M.slot_no(V.name(t)), t) for t in range(len(V)) if V.kind(t) == 'relation']


def column_positions(dec, V, entries, ndecl):
    """{relation slot: {(column position, field position or None): type}} of the declared relations below slot ndecl,
    at decoder dec at an atom start. entries[slot] lists a relation's columns as [(table slot, type)], one entry per
    field of a record column, from its prefix table or its native relation. The decoder's column tokens take the table's
    columns in slot order, after an Example column where the relation has one per example and its table leaves it out,
    and skipping a key column that the INIT does not bind. So the positions are the column tokens the decoder admits
    right after the relation token, less the first where they number one more than the table's columns; a relation
    whose admitted columns number neither is left out."""
    cols, rels = vocab_columns(V)
    out = {}
    for sl, t in rels:
        if sl >= ndecl or not entries.get(sl):
            continue
        f = dec.fork()
        try:
            f.step(t)
        except arclog.Refusal:
            continue
        slots = sorted({c for c, _ in entries[sl]})
        adm = []
        for p, c in cols[:len(slots) + 3]:
            try:
                f.forced(c)
                adm.append(p)
            except arclog.Refusal:
                pass
        if len(adm) == len(slots) + 1:
            adm = adm[1:]
        if len(adm) != len(slots):
            continue
        m = {}
        for p, c in zip(adm, slots):
            ts = [ty for c2, ty in entries[sl] if c2 == c]
            if len(ts) == 1:
                m[p, None] = ts[0]
            for k, ty in enumerate(ts):
                m[p, k] = ty
        out[sl] = m
    return out


def out_need(types):
    """The column types that an output clause lacks among types: a Color, and a Position or a Box (OUT takes either first)."""
    need = set() if 'Color' in types else {'Color'}
    return need if {'Position', 'Box'} & set(types) else need | {'Position', 'Box'}


def lib_types(rc, regcols):
    """{lib relation, macro or fact relation: [column type by position]} for the names in regcols, from featlib's
    interfaces of the libraries of rc's point. A relation with a column that has not exactly one type is left out."""
    lib = featlib._lib(str(rc.state.libraries_path))
    out = {}
    for name in regcols:
        iface = lib.interface(name)
        ts = [next(iter(c.types)) if len(c.types) == 1 else None for c in iface.columns.values()] if iface else [None]
        if None not in ts:
            out[name] = ts
    return out


def native_relations(program):
    """The native relations of the engine's render of a program."""
    return json.loads(program.render_json())['definitions']['native_relations']


def native_types(native):
    """{relation slot: [column types]} of the native relations to which the engine gives a type at every column, in the
    order of the physical columns. An INIT port's relation has a prefix table only where the engine builds one. A derived
    relation's physical columns are not in its table's order, so a caller takes these only where no prefix table gave
    types."""
    out = {}
    for e in native:
        ws = e.get('column_witnesses') or []
        if e.get('column_witness_status') == 'complete' and ws and all(w.get('type') for w in ws):
            out[e['relation_slot']] = [w['type'] for w in sorted(ws, key=lambda w: w['physical_column'])]
    return out


def registry_columns():
    """{lib relation or macro: [column names by position]}."""
    text = open(REGISTRY).read()
    out = {}
    for m in re.finditer(r'\((?:relation|macro)\s+(\S+)\s+\(columns\s+((?:\([^()]*\)\s*)*)\)', text):
        out[m[1]] = re.findall(r'\((\S+)\s+[^()]*\)', m[2])
    out['input'] = ['P', 'Col']
    out['ex_input'] = out['ex_output'] = ['E', 'P', 'Col']
    return out


@functools.lru_cache(maxsize=None)
def corpus_forms(t):
    """The parsed gold program of task t's first corpus pair, or None where the corpus has no pairs for t or left_out names t."""
    r = first_row(t)
    return r and M_sexprs(r['gold_sexp'])


def gold_bodies(dev, kind):
    """{task: [body]} of the clauses of a kind ('RULE' or 'DET') in the corpus gold of the dev tasks; a body is the list
    of its top-level atoms."""
    out = collections.defaultdict(list)
    for t in dev:
        for e in corpus_forms(t) or []:
            if e and e[0] == kind:
                out[t].append([a for a in e[2:] if isinstance(a, list)])
    return out


def port_parts(form):
    """[(port name, head [(column, label)], atoms)] of an INIT form's ports that have a head (a key group has none)."""
    out = []
    for p in form[3:]:
        if (isinstance(p, list) and len(p) >= 2 and isinstance(p[0], str) and isinstance(p[1], list) and
                all(isinstance(x, list) and len(x) == 2 and isinstance(x[0], str) and x[0].startswith(':') for x in p[1])):
            out.append((p[0], [(x[0][1:], x[1]) for x in p[1]], [a for a in p[2:] if isinstance(a, list)]))
    return out


def gold_port_bodies(dev):
    """{task: [body]} of the INIT ports with a head in the corpus gold of the dev tasks."""
    out = collections.defaultdict(list)
    for t in dev:
        forms = corpus_forms(t)
        if forms is None:
            continue
        for e in forms:
            if e and e[0] == 'INIT':
                out[t] += [atoms for _, _, atoms in port_parts(e)]
    return out


def component_ports():
    """{component: (type parameters, {input port: {column: type}})} from the registry."""
    forms = M_sexprs(re.sub(r';[^\n]*', '', open(REGISTRY).read()))
    out = {}
    for f in forms:
        if f and f[0] == 'component':
            params, ports = set(), {}
            for x in f[2:]:
                if isinstance(x, list) and x and x[0] == 'type-parameters':
                    params = {y if isinstance(y, str) else y[0] for y in x[1:]}
                if isinstance(x, list) and x and x[0] == 'inputs':
                    ports = {p[0]: {c[0]: c[1] for c in p[1:] if isinstance(c, list) and len(c) == 2} for p in x[1:] if isinstance(p, list)}
            out[f[1]] = (params, ports)
    return out


def sx(x):
    return x if isinstance(x, str) else '(' + ' '.join(sx(y) for y in x) + ')'


def one_call(dr, texts):
    """Whether a one-atom body reads a derived relation's method (program name &order.rank, atom text '&r4 ...'): golds of
    this form occur at DET and RULE points, where other one-atom bodies are refused (ONE_CALL=0 refuses these too)."""
    if not ONE_CALL or len(texts) != 1:
        return False
    m = re.match(r'\(\s*(&r\d+)', texts[0].lstrip())
    return m is not None and '.' in dr.prog_names.get(m.group(1), '')


def reads_derived(texts):
    """Whether some atom text reads a derived relation (a name that starts with &), as an atom or under NOT."""
    return any('(&' in t for t in texts)


def binders(x, out):
    """Label names bound in x (by * or ^), in text order."""
    if isinstance(x, str):
        if len(x) > 1 and x[0] in '*^' and x[1].isalpha():
            out.append(x[1:])
    elif isinstance(x, list):
        for y in x:
            binders(y, out)
    return out


def renamed(x, ren):
    if isinstance(x, str):
        p = x[0] if x[:1] in ('*', '^') else ''
        return p + ren[x[len(p):]] if x[len(p):] in ren else x
    return [renamed(y, ren) for y in x]


def project(tb, cols):
    """A port's X: table tb projected onto [(name, column index, type)], distinct rows per entry."""
    tb = full(tb)
    off = [sum(tb['widths'][:i]) for i in range(len(tb['types']))]
    wide = [i for i, t in enumerate(tb['types']) if str(t) in M.WIDE]
    entries = []
    for ex, asg, rows, exts, model in tb['entries']:
        got = {}
        for r, e in zip(rows, exts):
            pr = tuple(v for _, i, _ in cols for v in r[off[i]:off[i] + tb['widths'][i]])
            if pr not in got:
                got[pr] = [e[wide.index(i)] for _, i, _ in cols if i in wide]
        entries.append((ex, asg, list(got), list(got.values()), model))
    return dict(labels=[n for n, _, _ in cols], types=[t for _, _, t in cols], widths=[tb['widths'][i] for _, i, _ in cols],
                frames=[(tb.get('frames') or [''] * len(tb['types']))[i] for _, i, _ in cols], entries=entries)


def count_compound(c, body, out):
    """Adds to the Counter c what compound_counts gives for one body, as the mean over BodyOrders(body). The compound of an order is its
    first OR or IF, and an atom after it is left out."""
    law = BodyOrders(body)
    comps = {i for i, a in enumerate(law.atoms) if a and a[0] in ('OR', 'IF')}
    for (done, i), w in law.steps.items():
        if done & comps:
            continue
        k, a = len(done) + 1, law.atoms[i]
        c['reach', out, k] += w
        if i not in comps:
            continue
        parts = [b for b in a[1:] if isinstance(b, list)]
        c['comp', out, k] += w
        c['shape', a[0] + str(len(parts))] += w
        c['after', ] += w * (k < len(law.atoms))
        if a[0] == 'OR':  # branches are a set: each is the first in the same share of their orders
            c['later', ] += w * (len(parts) - 1)
            c['neg1', ] += w * negating_branches(parts) / len(parts)
        for b in parts:
            if b:
                c['blen', len(b)] += w


def negating_branches(parts):
    """The count of pairs (x, y) of branches of an OR where y negates a relation that x holds positively."""
    pairs = 0
    for i, x in enumerate(parts):
        held = {a[0] for a in x if isinstance(a, list) and a and a[0] != 'NOT'}
        pairs += sum(any(isinstance(a, list) and a and a[0] == 'NOT' and isinstance(a[1], list) and a[1][0] in held for a in y) for j, y in enumerate(parts) if j != i)
    return pairs


def compound_counts(dev):
    """{task: Counter} over the gold RULE bodies of the dev tasks, for a body's OR or IF (the compound), as count_compound counts them: ('reach',
    out, k) bodies whose k-th atom exists, ('comp', out, k) bodies whose k-th atom is the compound, where out tells whether the clause is the
    one OUT reads; ('shape', 'OR2' ...) the compound's kind and part count; ('blen', n) part lengths; ('after',) compounds with an atom after them;
    ('later',) OR branches past one and ('neg1',) those that negate a relation that another branch holds positively."""
    per = collections.defaultdict(collections.Counter)
    for t in dev:
        forms = corpus_forms(t)
        if forms is None:
            continue
        outs = {f[1][0] for f in forms if f and f[0] == 'OUT' and len(f) > 1 and isinstance(f[1], list) and f[1]}
        for e in forms:
            if e and e[0] == 'RULE':
                count_compound(per[t], [a for a in e[2:] if isinstance(a, list)], e[1] in outs)
    return per


def held_out(per, task):
    c = sum(per.values(), collections.Counter())
    c.subtract(per.get(task, collections.Counter()))
    return c


def group_hazards(dev):
    """{point group: P(END after k atoms | k atoms)} from the RULE bodies of the corpus gold of the dev tasks, each
    body counted in its clause's point group (strata.point_fields)."""
    bodies = collections.defaultdict(lambda: collections.defaultdict(list))
    for t in dev:
        r = first_row(t)
        if r is None:
            continue
        forms = strata.sexprs(r['gold_sexp'])
        for i, e in enumerate(forms):
            if e and e[0] == 'RULE':
                bodies[strata.point_fields(forms, i)['point_group']][t].append([a for a in e[2:] if isinstance(a, list)])
    return {g: kind_hazard(b) for g, b in bodies.items()}


def kind_hazard(bodies):
    """P(END after k atoms | k atoms) from the lengths of the bodies."""
    lens = collections.Counter(len(b) for bs in bodies.values() for b in bs)
    h = {}
    for k in range(1, MAX_ATOMS + 1):
        at = sum(v for n, v in lens.items() if n >= k)
        h[k] = (lens[k] + 0.5) / (at + 1.0) if at else 1.0
    return h


def atom_shape(a, bound=None):
    """An atom s-expression as a shape in the form of gold-shapes.jsonl: {neg, rel, args [(column, kind)]}, or None for
    a compound atom (OR, IF). A declared relation is `declared` and its columns `_`; a comparison is its OPS name; a
    record binder is left out of args. A site's kind is the mark that the text gives it. With bound, the labels bound before the atom, a
    site of an atom that binds its labels has the kind that those labels give it."""
    neg, seen = False, None if bound is None else set(bound)
    if a and a[0] == 'NOT' and len(a) > 1 and isinstance(a[1], list):
        neg, a = True, a[1]
    if not a or not isinstance(a[0], str) or a[0] in ('OR', 'IF', 'ALSO', 'NOT'):
        return None
    if a[0] in OPS:
        return dict(neg=neg, rel=OPS[a[0]], args=[])
    rel = 'declared' if a[0].startswith('&') else a[0]
    args = []
    for site in a[1:]:
        if not (isinstance(site, list) and len(site) == 2 and isinstance(site[0], str) and site[0].startswith(':') and isinstance(site[1], str)):
            if seen is not None:
                seen |= atom_labels(site)
            continue
        b = site[1]
        kind = 'zero' if b == '0' else 'fresh' if b.startswith('*') else 'caret' if b.startswith('^') else 'join'
        if seen is not None and kind != 'zero' and not neg:
            kind = 'join' if b.lstrip('*^') in seen else 'fresh'
            seen.add(b.lstrip('*^'))
        args.append(('_' if rel == 'declared' else site[0][1:], kind))
    return dict(neg=neg, rel=rel, args=args)


def atom_labels(x, marked=False):
    """The labels of an atom or of a list of atoms; with marked, those that a * or ^ marks somewhere in x."""
    if isinstance(x, str):
        name = x.lstrip('*^')
        return {name} if name[:1].isupper() and (not marked or name != x) else set()
    return set().union(*[atom_labels(y, marked) for y in (x[1:] if x and isinstance(x[0], str) else x)])


@functools.lru_cache(maxsize=None)
def mode_holds(rel, bound, unbound):
    """Whether an atom of a lib relation may stand where its sites at the columns bound are bound and those at the columns unbound aren't,
    by the engine's safety check, which alone knows a relation macro's modes."""
    atom = [(c, 'B%d' % j) for j, c in enumerate(sorted(bound))] + [(c, '*U%d' % j) for j, c in enumerate(sorted(unbound))]
    text = '(RULE &x %s (%s %s))\n(RULE &y (input (:P *P) (:Col *Col)))\n(OUT (&y ^P ^Col))' % (' '.join('(= *%s 0)' % x for _, x in atom if x[0] == 'B'), rel, ' '.join('(:%s %s)' % x for x in atom))
    try:
        arclog.StudyProgram.from_sexp(text, arclog.DecodeSettings())
    except arclog.Refusal as e:
        return 'no mode of the atom' not in str(e)
    return True


def atom_binds(a, bound, outer):
    """The labels that the atom a binds where the labels of bound are bound, or None where a may not stand there. outer is the labels that
    stand outside a, in the rest of its body or before the body; a label of a compound that outer doesn't hold is local to a part of it.
    A positive atom binds its labels once a mode of its relation holds. `=` binds its labels once one of them is bound. A NOT, an ALL and
    another comparison bind none, and need the labels they read from outside. An OR or an IF binds what every part binds, and needs
    each outer label that some part leaves unbound."""
    if not a or a[0] in ('ONE', 'SET'):
        return set()
    labels = atom_labels(a)
    if a[0] == '=':
        return labels if labels & bound or len(labels) < 2 else None
    if a[0] in OPS or a[0] == 'NOT':
        return set() if labels <= bound else None
    if a[0] == 'ALL':
        return set() if labels & outer <= bound else None
    if a[0] in ('OR', 'IF'):
        parts = [p for p in a[1:] if isinstance(p, list)]
        parts = [parts[0] + parts[1], parts[2]] if a[0] == 'IF' else parts
        got = [atoms_bound(p, bound, outer) for p in parts]
        shared = set.intersection(*got)
        return shared if labels & outer <= bound | shared else None
    if a[0].startswith('&'):
        return labels
    sites = [(x[0][1:], atom_labels(x)) for x in a[1:] if isinstance(x, list) and x]
    held = frozenset(c for c, ls in sites if ls <= bound)
    return labels if mode_holds(a[0], held, frozenset(c for c, _ in sites) - held) else None


def atoms_bound(atoms, bound, outer):
    """The labels bound after the atoms of a list that may stand in some order, where the labels of bound are bound."""
    atoms = [a for a in atoms if isinstance(a, list)]
    bound, left = set(bound), list(range(len(atoms)))
    while left:
        kept = []
        for i in left:
            got = atom_binds(atoms[i], bound, outer | atom_labels(atoms[:i] + atoms[i + 1:]))
            if got is None:
                kept.append(i)
            else:
                bound |= got
        if len(kept) == len(left):
            break
        left = kept
    return bound


class BodyOrders:
    """The law of the orders of a body's atoms, a fact of the set of atoms: the next atom is uniform over those that may stand after the atoms
    before it (atom_binds), as a next clause is in live_priors' walk counts. atoms is the body sorted by text with no * or ^, steps maps (positions
    of the atoms before, position of the atom) to the chance that an order has those atoms first and this atom next, and bounds maps the former to
    the labels bound after them. A label that a body reads and never marks, and that no atom of the body binds, is bound before the body, and
    so is a label of bound, the labels that the code around the body binds. Over ORDER_EXACT atoms, steps are the mean of ORDER_SAMPLES draws."""

    def __init__(self, body, bound=()):
        self.atoms = sorted((a for a in body if isinstance(a, list)), key=lambda a: re.sub(r'[*^]', '', sx(a)))
        free = atom_labels(self.atoms) - atom_labels(self.atoms, True)
        free -= atoms_bound(self.atoms, set(), set())
        free |= set(bound) & atom_labels(self.atoms)
        self.outer = [free | atom_labels(self.atoms[:i] + self.atoms[i + 1:]) for i in range(len(self.atoms))]
        self.bounds = {frozenset(): free}
        self.steps = collections.Counter()
        if len(self.atoms) > ORDER_EXACT:
            rng = random.Random(0)
            for _ in range(ORDER_SAMPLES):
                done = frozenset()
                for _ in self.atoms:
                    opts = self.ready(done)
                    i = rng.choice(sorted(opts))
                    self.steps[done, i] += 1 / ORDER_SAMPLES
                    done = self.after(done, i, opts[i])
            return
        layer = {frozenset(): 1.0}
        for _ in self.atoms:
            nxt = collections.Counter()
            for done, w in layer.items():
                opts = self.ready(done)
                for i, binds in opts.items():
                    self.steps[done, i] += w / len(opts)
                    nxt[self.after(done, i, binds)] += w / len(opts)
            layer = nxt

    def ready(self, done):
        """{position: labels it binds} of the atoms that may come after those at the positions done."""
        rest = [i for i in range(len(self.atoms)) if i not in done]
        got = {i: atom_binds(self.atoms[i], self.bounds[done], self.outer[i]) for i in rest}
        return {i: b for i, b in got.items() if b is not None} or {i: atom_labels(self.atoms[i]) for i in rest}

    def after(self, done, i, binds):
        out = done | {i}
        self.bounds.setdefault(out, self.bounds[done] | binds)
        return out


def body_kinds(body):
    """{(relation, column, kind): sites} of a body's plain atoms, as the mean over BodyOrders(body) of atom_shape's kinds."""
    law, out = BodyOrders(body), collections.Counter()
    for (done, i), w in law.steps.items():
        sh = atom_shape(law.atoms[i], law.bounds[done])
        for col, k in sh['args'] if sh else ():
            out[sh['rel'], col, k] += w
    return out


class Prior:
    """Production counts of gold atoms by task (so that a point's task can be held out): of RULE atoms from
    gold-shapes.jsonl, whose kinds read gold's written order, or of the atoms of the given bodies ({task: [body]}), whose kinds read no order."""

    FIELDS = ('rel', 'neg', 'kind', 'ckind', 'nsites')

    def __init__(self, bodies=None):
        for f in self.FIELDS:
            setattr(self, f, collections.defaultdict(collections.Counter))
        if bodies is None:
            shapes = ((json.loads(line)) for line in open(SHAPES))
        else:
            shapes = (dict(task=t, count=1, shape=dict(none=sh)) for t, bs in bodies.items() for b in bs
                      for sh in map(atom_shape, b) if sh is not None)
        for r in shapes:
            sh, n, t = r['shape']['none'], r['count'], r['task']
            rel = sh['rel']
            self.rel[t][rel] += n
            self.neg[t][rel] += n * sh['neg']
            self.nsites[t][(rel, len(sh['args']))] += n
            for col, k in sh['args'] if bodies is None else ():
                k = k.split(':')[0]
                self.kind[t][(rel, k)] += n
                self.ckind[t][(rel, col, k)] += n
        for t, bs in (bodies or {}).items():  # a site's kind depends on the atoms before it, so a body counts it over its orders
            for b in bs:
                for (rel, col, k), n in body_kinds(b).items():
                    self.kind[t][(rel, k)] += n
                    self.ckind[t][(rel, col, k)] += n
        self.total = {f: sum(getattr(self, f).values(), collections.Counter()) for f in self.FIELDS}

    def held_out(self, task):
        out = {}
        for f in self.FIELDS:
            c = collections.Counter(self.total[f])
            c.subtract(getattr(self, f)[task])
            out[f] = c
        return out


# ---------------------------------------------------------------- the atom grammar, by per-token checks

class FNode:
    __slots__ = ('toks', 'dec', 'phase', 'last', 'need', 'text', 'ok', 'kids', 'neg', 'labs', 'rtok', 'mask')

    def __init__(self, toks, dec, phase, last, need, text, neg, labs, rtok):
        self.toks, self.dec, self.phase, self.last, self.need, self.text, self.neg = toks, dec, phase, last, need, text, neg
        self.labs, self.rtok = labs, rtok
        self.ok = {}
        self.kids = {}
        self.mask = None


class FastFrontier:
    """measure.Frontier's atom grammar, with each candidate token checked by `Decoder.forced` (a per-token check)
    in place of the whole mask. The candidates of a phase are the grammar's: relation starts (lib relations, the
    fact `input` and the declared slots so far), comparison operators and NOT at an atom start (none under NOT, and an
    `=` takes no second operand equal to its first); the relation's
    column positions above the last; `*`, `0` and the clause's labels at a binder."""

    def __init__(self, V, ndeclared, regcols):
        self.V = V
        nv = len(V)
        self.KIND = [V.kind(i) for i in range(nv)]
        self.colpos = {i: int(V.name(i)[1:]) for i in range(nv) if self.KIND[i] == 'column' and V.name(i)[1:].isdigit()}
        self.col_by_pos = {p: i for i, p in self.colpos.items()}
        self.label_tok = {int(V.name(i)[1:]): i for i in range(nv) if self.KIND[i] == 'label'}
        rel = [i for i in range(nv) if self.KIND[i] in ('lib relation', 'relation macro')]
        decl = [i for i in range(nv) if self.KIND[i] == 'relation' and M.slot_no(V.name(i)) < ndeclared]
        inp = V.id('input')
        facts = [i for i in range(nv) if self.KIND[i] == 'fact relation']
        self.starts_list = rel + decl + facts
        self.starts = set(self.starts_list)
        # END is no evidence that an atom is complete: it also closes a site on a record-valued column (a port's key)
        self.closers_try = [M.NOT] + ([inp] if inp is not None else []) + [M.CMP[0]]
        self.reg = regcols
        self.root = None
        self.created = 0
        self.arity = {}  # a declared relation's token -> a bound on its column positions, from its table's columns
        self.record_col = {}  # (relation token, column) -> whether a field token opens a site there, from a node checked whole

    def reset(self, dec, labs):
        self.root = FNode((), dec, 'root', -1, 0, '', False, labs, None)
        return self.root

    def adm(self, n, j):
        """Whether the decoder admits token j at n: at an atom start, where every start token is checked, by the node's
        whole mask (`Decoder.admissible`, which agrees with `forced`), and elsewhere by `Decoder.forced`, or with ADMITS by
        `Decoder.admits` over the node's candidates."""
        v = n.ok.get(j)
        if v is None:
            if n.phase in ('root', 'root2') and ROOT_ADMITS:  # one `Decoder.admits` call over the start tokens, in place of the whole mask
                group = dict.fromkeys(t for t in self.candidates(n) + self.closers_try if t not in n.ok)
                group[j] = None
                group = list(group)
                for t, ok in zip(group, n.dec.admits(group)):
                    n.ok[t] = ok
                v = n.ok[j]
            elif n.phase in ('root', 'root2'):
                if n.mask is None:
                    n.mask = n.dec.admissible()
                v = bool(n.mask[j >> 3] >> (j & 7) & 1)
            elif ADMITS:  # one `Decoder.admits` call checks every token that a caller asks about at n: the phase's candidates and its closers
                group = dict.fromkeys(t for t in self.candidates(n) + (self.closers_try if n.phase in ('cols', 'done') else []) if t not in n.ok)
                group[j] = None
                group = list(group)
                for t, ok in zip(group, n.dec.admits(group)):
                    n.ok[t] = ok
                    if ADM_STATS is not None:
                        ADM_STATS[n.phase, self.KIND[t] if t >= 0 and t not in (M.STAR, M.ZERO, M.END) else self.V.name(t), ok] += 1
                v = n.ok[j]
            else:
                try:
                    n.dec.forced(j)
                    v = True
                except arclog.Refusal:
                    v = False
                if ADM_STATS is not None:
                    ADM_STATS[n.phase, self.KIND[j] if j >= 0 and j not in (M.STAR, M.ZERO, M.END) else self.V.name(j), v] += 1
            n.ok[j] = v
        return v

    def ncols(self, rtok):
        name = self.V.name(rtok)
        if self.KIND[rtok] in ('lib relation', 'relation macro') and name in self.reg:
            return len(self.reg[name])
        if self.KIND[rtok] == 'fact relation':
            return len(self.reg.get(name, ())) or 24
        return self.arity.get(rtok, 24) if ARITY_CAP else 24

    def candidates(self, n):
        """The grammar's tokens at n, in order, before the decoder's check."""
        if n.phase in ('root', 'root2'):
            c = self.starts_list + (list(M.CMP) + [M.NOT] if n.phase == 'root' else [])  # a constraint under NOT is not read
        elif n.phase == 'cols':
            named = {int(x) for x in re.findall(r'\(:(\d+)', n.text)}
            c = [self.col_by_pos[p] for p in range(n.last + 1, self.ncols(n.rtok)) if p in self.col_by_pos] + \
                [self.col_by_pos[p] for p in range(0, max(n.last, 0)) if p in self.col_by_pos and p not in named]
        elif n.phase in ('val', 'fval'):
            c = [M.STAR, M.ZERO] + [self.label_tok[i] for i in range(n.labs) if i in self.label_tok]
            if n.phase == 'val' and (not FIELD_MEMO or self.record_col.get((n.rtok, n.last)) is not False):  # a field token opens a site on a record-valued column
                c += [self.col_by_pos[p] for p in range(MAX_FIELDS) if p in self.col_by_pos]
        elif n.phase == 'fcol':  # the next field of the record, or the END that closes its site
            c = [self.col_by_pos[p] for p in range(n.need + 1, MAX_FIELDS) if p in self.col_by_pos] + [M.END]
        elif n.phase == 'op':
            c = [M.ZERO] + [self.label_tok[i] for i in range(n.labs) if i in self.label_tok]
            if n.need == 1 and n.toks[-2] == M.CMP[0]:  # the second operand of `=`
                c = [j for j in c if j != n.toks[-1]]
        else:
            c = []
        return c

    def options(self, n):
        out = [j for j in self.candidates(n) if self.adm(n, j)]
        if n.phase == 'val' and (n.rtok, n.last) not in self.record_col:  # every field token was checked here
            self.record_col[n.rtok, n.last] = any(self.KIND[j] == 'column' for j in out)
        if ARITY_CHECK and n.phase == 'cols' and n.rtok in self.arity and not ARITY_CAP:
            hi = [self.colpos[j] for j in out if self.colpos.get(j, -1) >= self.arity[n.rtok]]
            if hi:
                sys.stderr.write('ARITY_CHECK %s learned %d, admitted %s at last %d in %r\n' % (
                    self.V.name(n.rtok), self.arity[n.rtok], hi, n.last, n.text[-160:]))
        return out

    def admitted(self, n, skip=None):
        """options(n) one token at a time, with the decoder's check made only when a caller asks for the next token, and
        none made on a token that skip(token) rejects."""
        for j in self.candidates(n):
            if (skip is None or not skip(j)) and self.adm(n, j):
                yield j

    def is_leaf(self, n):
        return n.phase in ('cols', 'done') and any(self.adm(n, j) for j in self.closers_try)

    def child(self, n, tok):
        if tok in n.kids:
            return n.kids[tok]
        f = n.dec.fork()
        try:
            r = f.step(tok)
        except arclog.Refusal:
            n.kids[tok] = None
            return None
        self.created += 1
        V, ph = self.V, n.phase
        text, last, need, neg, labs, rtok = n.text, n.last, n.need, n.neg, n.labs, n.rtok
        if ph in ('root', 'root2'):
            if tok == M.NOT:
                nph, neg = 'root2', True
            elif tok in M.CMP:
                nph, need, text = 'op', 2, '(%s' % V.name(tok)
            else:
                nph, last, text, rtok = 'cols', -1, '(%s' % V.name(tok), tok
        elif ph == 'cols':
            nph, last, text = 'val', self.colpos[tok], n.text + ' (:%d' % self.colpos[tok]
        elif ph in ('val', 'fcol') and tok in self.colpos:
            nph, need, text = 'fval', self.colpos[tok], n.text + ' (:%d' % self.colpos[tok]
        elif ph == 'fcol':  # END: the record site closes
            nph, text = 'cols', n.text + ')'
        elif ph in ('val', 'fval'):
            nph = 'cols' if ph == 'val' else 'fcol'
            if tok == M.STAR:
                labs += 1
            text = n.text + ' %s)' % (('*' + V.name(r[0][0])) if tok == M.STAR and r[0] else V.name(tok))
        else:
            need -= 1
            nph = 'done' if need == 0 else 'op'
            text = n.text + ' ' + V.name(tok)
        c = FNode(n.toks + (tok,), f, nph, last, need, text, neg, labs, rtok)
        n.kids[tok] = c
        return c

    def render(self, n):
        t = n.text + ')'
        return '(NOT %s)' % t if n.neg else t

    def probe(self, dec):
        """A token that starts a next atom at `dec` (the engine gives a body table only at an atom start)."""
        n = FNode((), dec, 'root', -1, 0, '', False, 0, None)
        cands = [j for j in self.closers_try[1:2] + self.starts_list if self.KIND[j] != 'relation']
        if ROOT_ADMITS and cands and dec.admits(cands[:1])[0]:  # the first candidate is nearly always the one; `adm` would check every start token
            return cands[0]
        for j in cands:
            if self.adm(n, j):
                return j
        return None


# ---------------------------------------------------------------- tables with frames and models

parse_table, full, entry_cells = TA.parse_table, TA.full, TA.entry_cells  # the one adapter reads the rows of a table


def body_table(fr, task, case, parent_dec, parent_before, rows=True):
    """(the body table at parent_dec after a probe token, None), or (None, why). With rows False the table has its counts and its AssignmentSummaries, and `full` cannot give its rows."""
    f = parent_dec.fork()
    p = fr.probe(f)
    if p is None:
        return None, 'no probe token'
    try:
        f.step(p)
        ct = TA.export(f, task, case, parent_before, rows)
        return parse_table(ct, with_rows=False), None
    except M.Fail as e:
        return None, str(e)
    except (Exception, BaseException) as e:  # noqa: BLE001
        if isinstance(e, (KeyboardInterrupt, SystemExit)):
            raise
        return None, '%s: %s' % (type(e).__name__, e)


summary, rows_with_models = TA.summary, TA.rows_of


# ---------------------------------------------------------------- one atom

def log0(x):
    return math.log(x) if x > 0 else -math.inf


def two_stage_counts(n1, n2, draw, cheap, costly):
    """(K1, N2', K2) of the two-stage scheme of exact_two_stage, with no early stop."""
    cands = [draw() for _ in range(n1)]
    passers = [c for c in cands if cheap(c)]
    checked = passers[:n2]
    outs = [costly(c) for c in checked]
    return len(passers), len(checked), sum(o is not None for o in outs)


def exact_two_stage(n1, n2, draw, cheap, costly, dtries):
    """(payload, log A^) of the two-stage draw at an atom site, or (None, None) where K1 or K2 is 0. draw() gives a candidate
    (i.i.d. from q0 at the state); cheap(c) is whether it passes the cheap checks; costly(c) is the payload of a candidate that
    passes the expensive ones, else None. All n1 candidates get the cheap checks, and all min(K1, n2) first passers get the
    expensive ones, with no early stop, so that A^ = (K1 / n1)(K2 / n2') is unbiased and independent of the candidate that is picked."""
    cands = [draw() for _ in range(n1)]
    passers = [c for c in cands if cheap(c)]  # a list, so that no candidate is skipped
    if not passers:
        dtries['exact K1=0'] += 1
        return None, None
    checked = passers[:n2]
    outs = [costly(c) for c in checked]  # likewise
    k2 = sum(o is not None for o in outs)
    if not k2:
        dtries['exact K2=0'] += 1
        return None, None
    first = next(o for o in outs if o is not None)
    return first, math.log(len(passers) / n1) + math.log(k2 / len(checked))


class Unscored(Exception):
    """A step of gold's path that gold_q cannot score; the message is the reason."""


class Logs:
    """The log probabilities of a path: q of its picks, P of its picks and of its other factors, and q's other factors
    (logq_full is q + x). A factor with the same rate in P and in q is added to both by `both`."""

    def __init__(self, q=0.0, p=0.0, x=0.0):
        self.q, self.p, self.x = q, p, x

    def both(self, f):
        self.p += f
        self.x += f

    def add(self, o):
        self.q, self.p, self.x = self.q + o.q, self.p + o.p, self.x + o.x

    def copy(self):
        return Logs(self.q, self.p, self.x)


class Drawer:
    root_cap, node_cap = ROOT_CAP, NODE_CAP
    cache_cap = 4096  # entries of rel_cache and of choice_cache, at which each is emptied
    join_context = ()  # the tokens of the key group that the body reads: a key on another source gives other answers to joinable and completable, whose keys hold the body's tokens alone

    def __init__(self, V, counts, rng, regcols, fr, regtypes):
        self.V, self.c, self.rng, self.reg, self.fr, self.types = V, counts, rng, regcols, fr, regtypes
        self.port_rel = sum(v for q, v in counts['rel'].items() if q.startswith('port:'))
        self.lookahead_forks = 0
        self.srel_cache = {}  # STRUCT_P's relation weights at an atom start (weights)
        self.jcache = {}
        self.reach_cache = {}
        self.reach_stats = collections.Counter()  # reachable()'s column tests: hit, miss, and with REACH_CHECK stale (a hit that a fresh search contradicts)
        self.root_key = None  # the key of the frontier root last asked for
        self.root_seq = itertools.count()
        self.reach_drops = 0
        self.complete_drops = 0
        self.need_boost, self.want_boost = NEED_BOOST, WANT_BOOST  # run_point sets the OUT values at the clause that OUT reads
        self.want_types = frozenset()  # the types of the wanted labels: columns of those types get WANT_BOOST at a relation's columns
        self.want = set()  # label tokens to favour at a site (the labels a later OR branch must bind)
        self.unread = frozenset()  # UNREAD_BETA: the relation tokens of the forms that no kept form reads
        self.need = set()  # column types to favour at an atom start (the output clause's missing Position or Color)
        self.decl_types = {}
        self.colmap = {}
        self.force = None  # a deque of the tokens that atom takes in place of draws (scoring gold's atom), else None
        self.reached = {}  # node -> reach(node), for the nodes of the frontier last asked for
        self.roots = {}  # (clause tokens, labels) -> the root of that atom start's frontier
        self.created0 = 0  # fr.created when self.roots was last emptied
        self.tilt = None  # the point group's {feature: theta} of the tilt table (TILT), else None
        self.t_prev = '^'  # the tilt feature name of the previous atom of the draw, '^' at the first atom
        self.alt_q = None  # EXACT_COIN: the last pick's share under the other coin value
        self.p_k = 2
        self.gq = False  # GOLD_Q: gold's tokens are forced and the tilt and the coin mixture apply, as on a draw
        self.deltas = {}  # EXACT_COIN: id of an atom result -> its mixture log q minus its coin-conditional log q
        self.gq_rel = []  # GOLD_Q: per root-phase pick of gold's atom, gold's log share under P, and under q's free and joined weights without and with STEER_REL
        self.rel_cache = {}  # STEER_REL: (clause tokens, phase, k, scope) -> exp(beta f) of the atom start's options; one Drawer is one point
        self.rel_pre = {}  # STEER_REL: clause tokens -> the prefix atoms in relrows format
        self.rel_id = None
        self.p_labels = None  # the labels of the prefix table the atom reads (aligned with p_scope), None at atom 1
        self.choice_cache = {}  # STEER_CHOICE: (clause tokens, phase, k, atom text) -> (exp(beta f) per option, of the stop)
        self.choice_stats = collections.Counter()  # STEER_CHOICE: calls, misses and CPU seconds (row, scoring)
        self.rel_stats = collections.Counter()  # STEER_REL: calls, misses and CPU seconds (prefix render, P weights, scoring)
        self.rel_closed, self.rel_base, self.rel_pg, self.rel_off = None, 0, None, False  # run_point sets these (closed_program, base_forms, point group, no steer)
        self.row_pg, self.hist = {}, {}  # run_point sets these: a CHOICE_ROWS row's point_group, and prior_history's uses of each relation token before the clause
        self.rel_dag_src = None  # run_point sets this: (spec, point index), the forms before the point
        self.rel_dag = None  # STEER_REL: dag_info's (fields, adj) of those forms, built at the first miss; False where it cannot be built
        self.rel_dag_f, self.rel_dag_p = {}, {}  # base -> its fields; (bases the prefix reads, base) -> dag_path
        self.sink = None  # a function (kind, row, gold): each pick of a forced atom (kind 'rel' or 'choice') and each stop row (kind 'stop', gold None) adds the row that its steer scores at that pick
        self.p_text = None  # the atoms drawn before this one, as text, where the clause cannot close (an INIT body, the first atom of a later branch); the live walk sets it
        self.or_done = ()  # the atoms of the branches that the OR being drawn has finished
        self.rel_text = False  # the prefix is p_text, not the closed clause (an INIT body)
        self.pg, self.kind = None, None  # STEER_DERIVED: the Program at the body's form and the form's kind; live.Run.steer sets them
        self.scope_facts = {}  # STEER_DERIVED: 'derived' -> (the program's last step_tables result and form count, its DerivedScope); the Drawers of one scope share it

    def frontier(self, dec, labs=0, key=None):
        """The frontier at decoder dec, an atom start with labs labels in the clause. With key (the clause's tokens so far,
        which fix dec's state), the root is kept in self.roots and a later call with the same key and labs gets that root,
        with the nodes grown below it: a node holds only the decoder's answers at its state (its checks, mask and child
        decoders), nothing of a draw. The caller must not step dec, or the decoder of a node below it, in place. The reach
        memo is emptied at each call, as a new root's nodes had none, so reach (which a search past its budget makes depend
        on the memo) gives what it gave on new nodes."""
        self.reached.clear()
        if key is None:
            self.root_key = ('fresh', next(self.root_seq))
            self.fr.reset(dec, labs)
            return self.fr
        ck = self.root_key = (key, labs)
        root = self.roots.get(ck)
        if root is None:
            if len(self.roots) >= self.root_cap or self.fr.created - self.created0 >= self.node_cap:
                self.roots.clear()
                self.created0 = self.fr.created
            root = self.roots[ck] = self.fr.reset(dec, labs)
        else:
            self.fr.root = root
        return self.fr

    def pick(self, opts, weights):
        tot = sum(weights)
        if self.force is not None:
            o = self.force.popleft()
            return o, weights[opts.index(o)] / tot if o in opts else 0.0
        x = self.rng.random() * tot
        for o, w in zip(opts, weights):
            x -= w
            if x <= 0:
                return o, w / tot
        return opts[-1], weights[-1] / tot

    def alt_share(self, alt, i):
        """The share of option i among the alt weights that EXACT_COIN keeps beside the drawn ones (same drops), 0 where none is left."""
        tot = sum(alt)
        return alt[i] / tot if tot > 0 else 0.0

    def pick_reach(self, n, opts, weights, alt=None):
        """pick, restricted to the options whose child can still reach the atom's end (a value can make the atom one
        that the decoder's static pruning refuses to close): a picked option that cannot is dropped and the pick repeats
        over the rest, which samples the same law as masking first. Returns (None, None) where no option can. q is the
        option's share of the options left, which is at most its share of the reachable options."""
        ws = list(weights)
        alt = list(alt) if alt is not None else None  # EXACT_COIN: the weights under the other coin value, dropped as ws is
        self.alt_q = None
        while sum(ws) > 0:
            o, q = self.pick(opts, ws)
            if alt is not None:
                self.alt_q = self.alt_share(alt, opts.index(o)) if o in opts else 0.0
            if self.force is not None or not REACH or self.fr.KIND[o] == 'column':
                return o, q
            ch = self.fr.child(n, o)
            if ch is not None and self.reach(ch):
                return o, q
            ws[opts.index(o)] = 0.0
            if alt is not None:
                alt[opts.index(o)] = 0.0
            self.reach_drops += 1
        return None, None

    def pick_complete(self, n, opts, weights, key, alt=None):
        """pick, restricted to the atom starts that completable admits: a picked start that it refuses is dropped and the
        pick repeats over the rest, as in pick_reach, so only picked starts are searched. Returns (None, None) where no
        start can complete. q is the start's share of the starts left."""
        ws = list(weights)
        alt = list(alt) if alt is not None else None
        self.alt_q = None
        while sum(ws) > 0:
            o, q = self.pick(opts, ws)
            if alt is not None:
                self.alt_q = self.alt_share(alt, opts.index(o)) if o in opts else 0.0
            if self.force is not None or not COMPLETE or o in M.CMP or self.completable(n, o, key):
                return o, q
            ws[opts.index(o)] = 0.0
            if alt is not None:
                alt[opts.index(o)] = 0.0
            self.complete_drops += 1
        return None, None

    def rel_name(self, tok):
        if self.fr.KIND[tok] == 'relation':
            return 'declared'
        name = self.V.name(tok)
        return OPS.get(name, name)

    def joinable(self, root, opts, scope_types, key):
        """The relation tokens among opts with some column whose binder can be an existing label: by the column types
        (featlib's for a lib, macro or fact relation, the prefix tables' for a declared one) against the types in scope,
        else (a column with no one type) by the decoder one step ahead, cached by (token, types in scope). With Ident sources on,
        a relation with an Ident column goes to the decoder too while the scope holds an Ident, because the types alone do not
        tell the sources apart: its cache key adds key (the clause's tokens) and join_context (the key group's, which fix the sources
        of the key's labels), and the step ahead also looks at the first token of each field of a record column."""
        fr = self.fr
        out, pending = set(), []
        tset = frozenset(scope_types)
        by_source = IDENT_SOURCE and 'Ident' in tset
        for o in opts:
            if o == M.NOT or o in M.CMP:
                continue
            if fr.KIND[o] == 'relation':
                ts = self.decl_types.get(M.slot_no(self.V.name(o)))
            else:
                ts = self.types.get(self.V.name(o)) if fr.KIND[o] in ('lib relation', 'relation macro', 'fact relation') else None
            if ts is not None and by_source and any(str(t) == 'Ident' for t in ts):
                pending.append((o, True))
            elif ts is not None:
                if compat_any(tset, tuple(ts)):
                    out.add(o)
            else:
                pending.append((o, False))
        for o, sourced in pending:
            ck = (o, tset, (key, self.join_context)) if sourced else (o, tset)
            hit = self.jcache.get(ck)
            if hit is None:
                hit = False
                c = fr.child(root, o)
                self.lookahead_forks += 1
                if c is not None:
                    for col in fr.admitted(c):
                        v = fr.child(c, col)
                        self.lookahead_forks += 1
                        if v is not None and self.label_ahead(v, sourced):
                            hit = True
                            break
                self.jcache[ck] = hit
            if hit:
                out.add(o)
        return out

    def label_ahead(self, v, fields):
        """Whether the decoder admits a label at node v, a column's value: directly, or, where fields, as the value of a
        field of the column, at the first token of the field's site."""
        fr = self.fr
        no_label = lambda t: fr.KIND[t] != 'label'  # noqa: E731
        if any(True for _ in fr.admitted(v, no_label)):
            return True
        if fields:
            for f in fr.admitted(v, lambda t: fr.KIND[t] != 'column'):
                w = fr.child(v, f)
                self.lookahead_forks += 1
                if w is not None and any(True for _ in fr.admitted(w, no_label)):
                    return True
        return False

    def has_type(self, o, types):
        """Whether relation token o has a column of one of the types (by the prefix tables for a declared relation and
        featlib's interfaces for a lib, macro or fact relation)."""
        if self.fr.KIND[o] == 'relation':
            ts = self.decl_types.get(M.slot_no(self.V.name(o)))
        else:
            ts = self.types.get(self.V.name(o)) if self.fr.KIND[o] in ('lib relation', 'relation macro', 'fact relation') else None
        return bool(ts) and any(str(t) in types for t in ts)

    def col_needed(self, o, pos, field=None):
        """Whether column pos of relation token o (its field `field` where the column is a record) has a type in
        self.need, by the types that has_type reads."""
        if not self.need:
            return False
        if self.fr.KIND[o] == 'relation':
            ts, cols = None, self.colmap.get(M.slot_no(self.V.name(o)), {})
        else:
            ts = self.types.get(self.V.name(o)) if self.fr.KIND[o] in ('lib relation', 'relation macro', 'fact relation') else None
            cols = None
        return column_type(ts, cols, pos, field) in self.need

    def col_wanted(self, o, pos, field=None):
        """Whether column pos of relation token o has a type that a wanted label can fill (want_types), by the types that
        col_needed reads."""
        if not self.want_types:
            return False
        if self.fr.KIND[o] == 'relation':
            ts, cols = None, self.colmap.get(M.slot_no(self.V.name(o)), {})
        else:
            ts = self.types.get(self.V.name(o)) if self.fr.KIND[o] in ('lib relation', 'relation macro', 'fact relation') else None
            cols = None
        ty = column_type(ts, cols, pos, field)
        return ty is not None and compat_any(self.want_types, (ty,))

    def zero_ok(self, rel, last):
        """Whether the binder prior gives a literal 0 any mass at this column."""
        names = self.reg.get(rel)
        col = names[last] if names and 0 <= last < len(names) else None
        c = self.c
        if col is not None and sum(c['ckind'][(rel, col, x)] for x in ('fresh', 'join', 'rep', 'zero')) > 0:
            return c['ckind'][(rel, col, 'zero')] > 0
        return c['kind'][(rel, 'zero')] > 0

    def completable(self, root, o, key):
        """Whether an atom that starts with token o can reach its end through binders the prior gives mass, by a
        bounded depth-first search (a search past its budget counts as completable). The search reads root's decoder
        state, which the clause's tokens so far (key) fix, and root's phase. A True is cached by (o, phase, whether the
        clause has a label) and holds at every later state: a stale True only makes atom() redraw. A False is cached by
        (o, phase, key, join_context), because a stale False removes the relation's mass."""
        ck_true, ck_false = ('complete', o, root.phase, root.labs > 0), ('complete', o, root.phase, (key, self.join_context))
        if ck_true in self.jcache:
            return True
        if ck_false in self.jcache:
            return False
        fr = self.fr
        budget = [COMPLETE_BUDGET]
        rel = self.rel_name(o) if o != M.NOT else None

        def dfs(n):
            if budget[0] <= 0:
                return True
            budget[0] -= 1
            if fr.is_leaf(n):
                return True
            skip = (lambda t: t == M.CARET or (t == M.ZERO and not self.zero_ok(rel, n.last))) if n.phase in ('val', 'fval') else None
            for t in fr.admitted(n, skip):
                ch = fr.child(n, t)
                if ch is not None and dfs(ch):
                    return True
            return False
        ch = fr.child(root, o)
        hit = ch is not None and dfs(ch)
        self.jcache[ck_true if hit else ck_false] = hit
        return hit

    def reach(self, n):
        """Whether the atom can end below node n through binders the prior gives mass, by a bounded depth-first
        search. A search past its budget counts as reachable; results are memoized on the nodes only where no search
        ran past its budget."""
        if n in self.reached:
            return self.reached[n]
        fr = self.fr
        budget, cut = [COMPLETE_BUDGET], [False]
        rel = self.rel_name(n.rtok) if n.rtok is not None else None

        def dfs(m):
            if m in self.reached:
                return self.reached[m]
            if budget[0] <= 0:
                cut[0] = True
                return True
            budget[0] -= 1
            if fr.is_leaf(m):
                self.reached[m] = True
                return True
            if m.phase in ('val', 'fval'):
                skip = lambda t: t == M.CARET or (t == M.ZERO and not self.zero_ok(rel, m.last))  # noqa: E731
            elif m.phase == 'op':
                skip = lambda t: t in (M.STAR, M.CARET)  # noqa: E731
            else:
                skip = None
            for t in fr.admitted(m, skip):
                ch = fr.child(m, t)
                if ch is not None and dfs(ch):
                    if not cut[0]:
                        self.reached[m] = True
                    return True
            if not cut[0]:
                self.reached[m] = False
            return False
        return dfs(n)

    def reachable(self, n, opts):
        """The options at n whose child can still reach the atom's end. Only a column token is tested: skipping a
        column can strand the atom, while a value the decoder admits at a site rarely does. Whether a column can reach the
        atom's end depends on the decoder's state (the labels in scope and their types), so a result is cached by REACH_KEY."""
        out = []
        for o in opts:
            if self.fr.KIND[o] != 'column':
                out.append(o)
                continue
            key = (n.rtok, n.neg, n.phase, n.last, n.need, o)
            if REACH_KEY == 'state':
                key += (self.root_key, n.toks)
            elif REACH_KEY == 'labs':
                key += (n.labs,)
            v = self.reach_cache.get(key)
            self.reach_stats['hit' if v is not None else 'miss'] += 1
            if v is not None and REACH_CHECK:
                ch = self.fr.child(n, o)
                if (ch is not None and self.reach(ch)) != v:
                    self.reach_stats['stale'] += 1
            if v is None:
                ch = self.fr.child(n, o)
                v = ch is not None and self.reach(ch)
                if ch is not None:
                    self.reach_cache[key] = v
            if v:
                out.append(o)
        return out

    prog_names = {}  # '&rN' -> the program's name of a derived relation
    place = None  # the kind of body: RULE, DET, or an INIT's key or port (live.py sets it)
    key_ident_offered = False  # a key body's atom start offered a declared relation with an Ident column where no Ident label was in scope (a count of live.py's, not a draw)
    key_rel_m = 1.0  # KEY_IDENT rel: the factor on the weight of a declared relation with an Ident column at an atom start of a key body that has no Ident label in scope (live.py sets it)
    p_k, p_scope, p_key, p_last = 1, (), (), ()  # the atom's index, the types in scope, the clause's tokens before it, the last atom's

    def last_atom(self):
        """STRUCT_B: the last atom's relation name ('NOT' for a negated atom) and the types of the columns it gives a
        fresh label (a record's fields left out)."""
        t = self.p_last
        if not t:
            return None, set()
        if t[0] == M.NOT:
            return 'NOT', set()
        name, ts = self.V.name(t[0]), self.rel_types(t[0]) or []
        made = set()
        for a, b in zip(t[1:], t[2:]):
            if self.fr.KIND[a] == 'column' and b == M.STAR and 0 <= self.fr.colpos[a] < len(ts):
                made.add(str(ts[self.fr.colpos[a]]))
        return name, made

    def b_terms(self, o, ts, scope, last, made):
        """STRUCT_B's terms of relation option o (column types ts) as {REL_WB key: value}."""
        name = self.V.name(o)
        if name not in INPUT_SLOTS:
            return {}
        ready = all(any(_sub(t, slot) for t in scope) for slot in INPUT_SLOTS[name])
        enum = last is not None and (last.endswith('_elem') or last in ('axis_of', 'opposite', 'perp', 'diag_dirs'))
        return dict(b_listed=1.0, b_ready=float(ready), b_boxpos=float(ready and 'Box' in scope and 'Position' in scope),
                    b_follows_crop=float(last == 'inside' and name in FOLLOWS_INSIDE),
                    b_follows_relative=float(last == 'relative' and name in FOLLOWS_RELATIVE),
                    b_repeat=float(last == name and name in REPEATS),
                    b_fits_enum=float(enum and any(_sub(m, t) for m in made for t in ts)))

    def rel_types(self, o):
        if self.fr.KIND[o] == 'relation':
            return self.decl_types.get(M.slot_no(self.V.name(o)))
        return self.types.get(self.V.name(o))

    def struct_rel(self, os, ws, key):
        """STRUCT_P's relation weights at an atom start from P's count weights ws."""
        k1, scope, W = self.p_k == 1, set(self.p_scope), REL_WB if STRUCT_B else REL_W
        last, made = self.last_atom() if STRUCT_B else (None, set())
        prev = set(key)
        slots = [M.slot_no(self.V.name(o)) for o in os if self.fr.KIND[o] == 'relation']
        top = max(slots) if slots else 0
        out = []
        for o, w in zip(os, ws):
            if w <= 0:
                out.append(0.0)
                continue
            kind = 'op' if o == M.NOT or o in M.CMP else 'derived' if self.fr.KIND[o] == 'relation' else 'lib'
            ts = [str(t) for t in (self.rel_types(o) or [])] if kind != 'op' else []
            hit = sum(t in scope for t in ts)
            rec = top - M.slot_no(self.V.name(o)) if kind == 'derived' else None
            z = (W[kind] + (W[kind + '_k1'] if k1 else 0.0) + W['in_scope'] * hit + W['in_scope_frac'] * (hit / len(ts) if ts else 0.0)
                 + (W['none_in_scope'] if ts and hit == 0 and not k1 else 0.0) + W['arity'] * len(ts) + (W['repeat'] if o in prev else 0.0)
                 + (W['recency0'] if rec == 0 else 0.0) + (W['recency_log'] * math.log1p(rec) if rec is not None else 0.0)
                 + (W['no_types'] if not ts else 0.0))
            if STRUCT_B and kind == 'lib':
                z += sum(W[x] * v for x, v in self.b_terms(o, ts, list(self.p_scope), last, made).items())
            out.append(w ** W['logp'] * math.exp(z))
        return out

    def struct_val(self, n, os, ws):
        """STRUCT_P's value weights at a column from P's count weights ws."""
        W, fr = VAL_W, self.fr
        ctype = None
        if n.phase == 'val' and n.rtok is not None:
            ts = self.rel_types(n.rtok)
            ctype = str(ts[n.last]) if ts and 0 <= n.last < len(ts) else None
        idx = {o: int(self.V.name(o)[1:]) for o in os if fr.KIND[o] == 'label' and self.V.name(o)[1:].isdigit()}
        top = max(idx.values()) if idx else 0
        by_num = None  # under P_DAG: the type in scope of each label number, by the label's name in the prefix
        if P_DAG and self.p_labels is not None:
            pre = self.rel_prefix(fr, self.p_key, self.p_k)
            if pre is not None:
                stype = dict(zip(self.p_labels, self.p_scope))
                by_num = [stype.get(x) for x in dict.fromkeys(STAR_NAME.findall(' '.join(pre)))]
        out = []
        for o, w in zip(os, ws):
            if w <= 0:
                out.append(0.0)
                continue
            i = idx.get(o)
            if P_DAG:
                lt = by_num[i] if by_num is not None and i is not None and i < len(by_num) else None
            else:
                lt = self.p_scope[i] if i is not None and i < len(self.p_scope) else None
            z = (W['fresh'] if o == M.STAR else W['zero'] if o == M.ZERO else W['label'] if i is not None else
                 W['field'] if fr.KIND[o] == 'column' else 0.0)
            if i is not None:
                z += (W['newest'] if i == top else 0.0) + W['recency_log'] * math.log1p(top - i)
                if lt is not None and ctype is not None:
                    z += W['type_same'] if lt == ctype else W['type_differs']
                if re.search(r'\b%s\b' % re.escape(self.V.name(o)), n.text):
                    z += W['in_atom']
            out.append(w ** W['logp'] * math.exp(z))
        return out

    on_value = None  # with a function here, a forced value pick calls it with (k, frontier, node, options, gold's token)
    choices = None  # with a list here, each forced pick after an atom's relation adds its options and pick to it (CHOICE_ROWS)

    def col_type(self, rtok, pos, field=None):
        """The type of column pos of relation token rtok (its field `field` where the column is a record), without the type's
        parameters, as col_needed reads it; None where unknown."""
        if rtok is None:
            return None
        if self.fr.KIND[rtok] == 'relation':
            ts, cols = None, self.colmap.get(M.slot_no(self.V.name(rtok)), {})
        else:
            ts = self.types.get(self.V.name(rtok)) if self.fr.KIND[rtok] in ('lib relation', 'relation macro', 'fact relation') else None
            cols = None
        t = column_type(ts, cols, pos, field)
        return None if t is None else str(t).split('(')[0]

    def row_rtypes(self, rtok):
        """A CHOICE_ROWS row's rtypes: the type of each column of relation token rtok by column position, without the type's
        parameters (None where unknown, and at a position with no column). A derived relation's come from colmap, as col_type
        reads them, with 'Record' for a record column; the others' from rel_types."""
        if rtok is None:
            return None
        if self.fr.KIND[rtok] == 'relation':
            cols = self.colmap.get(M.slot_no(self.V.name(rtok)))
            if not cols:
                return None
            out = [None] * (1 + max(p for p, _ in cols))
            for (p, f), t in cols.items():
                if f is None:
                    out[p] = str(t).split('(')[0]
                elif out[p] is None:
                    out[p] = 'Record'
            return out
        ts = self.rel_types(rtok)
        return [str(t).split('(')[0] for t in ts] if ts else None

    def prior_uses(self, rtok, key):
        """A CHOICE_ROWS row's prior_uses: the earlier atoms of relation token rtok, oldest first, those of the clauses before the
        clause and then those of the clause's tokens key; [] without a relation."""
        if rtok is None:
            return []
        return self.hist.get(rtok, []) + [dict(same_clause=True, cols=c) for t, c in atom_uses(self.V, key) if t == rtok]

    def choice_row(self, k, n, popts, rel, joined, leaf, gold, stop=None, key=()):
        """A CHOICE_ROWS row (without the fields of the point): gold's pick at node n among popts, with P's shares (times 1 - stop
        where the atom could stop there, and a STOP option of share stop). The steer builds it with gold None. key: the clause's
        tokens before the atom."""
        ws = self.weights(n, popts, rel, joined, leaf, False)
        tot = sum(ws) or 1.0
        go = 1.0 - stop if stop is not None else 1.0
        kind = {M.STAR: 'fresh', M.ZERO: 'zero', M.END: 'end', M.CARET: 'caret'}
        names = self.reg.get(rel)
        opts = []
        for o, w in zip(popts, ws):
            d = dict(tok=self.V.name(o), kind=kind.get(o, self.fr.KIND[o]), p=round(go * w / tot, 6))
            if n.phase == 'cols' and d['kind'] == 'column':  # the column's type, and its name where the relation is a lib one
                pos = self.fr.colpos[o]
                nm = names[pos] if names and 0 <= pos < len(names) else None
                d.update(ctype=self.col_type(n.rtok, pos), name=nm, key=None if nm is None else nm == 'key')
            opts.append(d)
        if stop is not None:
            opts.append(dict(tok='STOP', kind='stop', p=round(stop, 6)))
        col = names[n.last] if n.phase in ('val', 'fval') and names and 0 <= n.last < len(names) else None
        return dict(k=k, phase=n.phase, neg=bool(n.neg), rel=rel, rtok=self.V.name(n.rtok) if n.rtok is not None else None,
                    rkind=self.fr.KIND[n.rtok] if n.rtok is not None else None, col=col,
                    ctype=self.col_type(n.rtok, n.last, n.need if n.phase == 'fval' else None) if n.phase in ('val', 'fval') else None,
                    rtypes=self.row_rtypes(n.rtok), text=n.text, gold=gold, options=opts, point_group=self.row_pg,
                    prior_uses=self.prior_uses(n.rtok, key))

    def choice(self, k, n, popts, rel, joined, leaf, gold, stop=None, fr=None):
        """A CHOICE_ROWS row of a forced pick; with a sink and fr, the row that STEER_CHOICE scores at that pick goes to the sink."""
        if self.sink is not None and self.force is not None and fr is not None:
            row = self.choice_consult_row(fr, n, popts, k, rel, joined, leaf, stop, self.p_key, self.rel_prefix(fr, self.p_key, k))
            if row is not None:
                self.sink('choice', row, gold)
        if self.choices is None or self.force is None:
            return
        self.choices.append(self.choice_row(k, n, popts, rel, joined, leaf, gold, stop, self.p_key))

    def stop_row(self, k, toks, rel, text, h, gold=None, key=()):
        """A CHOICE_ROWS row of the stop after atom k (its tokens toks, relation rel, text), without the fields of the point and the
        clause: P's hazard h and the atom. The row's prefix and scope include the atom, and its prior_uses (of the atom's relation)
        do not. key: the clause's tokens before the atom."""
        tok = toks[1] if toks[0] == M.NOT else toks[0]
        return dict(k=k, phase='atom stop', neg=toks[0] == M.NOT, rel=rel, rkind=None if tok in M.CMP else self.fr.KIND[tok],
                    rtypes=None if tok in M.CMP else self.row_rtypes(tok), text=text, arity=self.atom_arity(toks, rel),
                    ncols=top_cols(text), gold=gold,
                    options=[dict(tok='STOP', kind='stop', p=round(h, 6)), dict(tok='GO', kind='stop', p=round(1 - h, 6))],
                    point_group=self.row_pg, prior_uses=None if tok in M.CMP else self.prior_uses(tok, key))

    def choice_on(self, name):
        """Whether STEER_CHOICE steers phase `name` ('stop' for the atom stop): it is in STEER_CHOICE_PHASES and the model was trained on it."""
        return bool(STEER_CHOICE) and name in STEER_CHOICE_PHASES and name in choice_scorer().phases

    def stop_consult_row(self, dec, key, k, toks, rel, text, tb, h):
        """The row that STEER_CHOICE scores at the stop after an atom (stop_shift's arguments), else None where the clause cannot close. It is
        the row that CHOICE_ROWS writes."""
        if self.rel_text:
            pre = list(self.p_text or ()) + [text]
        else:
            pf = self.rel_closed(dec, 1)
            if pf is None:
                return None
            pre = body_atoms(pf.split('\n')[self.rel_base])
        row = self.stop_row(k, toks, rel, text, h, None, key[:len(key) - len(toks)])
        row.update(prefix=pre, scope_labels=list(tb['labels']) if tb and tb.get('labels') is not None else None,
                   scope_types=[str(t) for t in tb['types']] if tb else [])
        return row

    def stop_shift(self, dec, key, k, toks, rel, text, tb, h):
        """STEER_CHOICE at the stop after an atom (decoder dec after its tokens toks; key: the clause's tokens with them; tb: the prefix
        table with the atom): beta * (f_STOP - f_GO) on the row that CHOICE_ROWS writes, the shift of the log odds of q's stop hazard (0
        where the steer is off). Cached per point by (key, k, text). P's hazard h stays."""
        if self.sink is not None and 0 < h < 1:  # the row goes to the sink, whether the steer is on or not; the caller then gives its gold
            row = self.stop_consult_row(dec, key, k, toks, rel, text, tb, h)
            if row is not None:
                self.sink('stop', row, None)
        if not self.choice_on('stop') or self.rel_off or not 0 < h < 1:
            return 0.0
        ck = (key, 'atom stop', k, text)
        got = self.choice_cache.get(ck)
        self.choice_stats['calls'] += 1
        if got is None:
            c0 = time.process_time()
            self.choice_stats['misses'] += 1
            got = 0.0
            row = self.stop_consult_row(dec, key, k, toks, rel, text, tb, h)
            if row is not None:
                c1 = time.process_time()
                self.choice_stats['s_row'] += c1 - c0
                if CHOICE_CHECK:
                    with open(CHOICE_CHECK, 'a') as f_:
                        f_.write(json.dumps(dict(row, id=self.rel_id)) + '\n')
                try:
                    fs, fg = choice_scorer().f(row)
                    got = max(-20.0, min(20.0, STEER_CHOICE_BETA * (fs - fg)))
                except Exception as e_:  # noqa: BLE001
                    print('STEER_CHOICE: scoring failed: %s: %s' % (type(e_).__name__, str(e_)[:200]), file=sys.stderr, flush=True)
                self.choice_stats['s_score'] += time.process_time() - c1
            if len(self.choice_cache) >= self.cache_cap:
                self.choice_cache.clear()
            self.choice_cache[ck] = got
        return got

    def atom_arity(self, toks, rel):
        """The number of columns of the relation of an atom's tokens (a lib relation's by the registry's names), None where unknown."""
        tok = toks[1] if toks[0] == M.NOT else toks[0]
        ts = None if tok in M.CMP else self.rel_types(tok)
        return len(ts) if ts else len(self.reg.get(rel) or []) or None

    def choice_consult_row(self, fr, n, popts, k, rel, joined, leaf, stop, key, pre):
        """The row that STEER_CHOICE scores at a pick of phase n.phase (prefix pre): CHOICE_ROWS' row with gold None, and the atom's scope. Where pre is
        None (the clause cannot close), None."""
        if pre is None:
            return None
        row = self.choice_row(k, n, popts, rel, joined, leaf, None, stop, key)
        row.update(prefix=pre, scope_labels=list(self.p_labels) if self.p_labels is not None else None, scope_types=list(self.p_scope))
        return row

    def choice_factors(self, fr, n, popts, k, rel, joined, leaf, stop, key):
        """STEER_CHOICE: (exp(STEER_CHOICE_BETA * f) for each option of popts, the same for the stop) at node n, f from the model of
        STEER_CHOICE on the row that CHOICE_ROWS would write (P's shares unsteered). Cached per point by (key, phase, k, NOT, atom text)."""
        ck = (key, n.phase, k, n.neg, n.text)  # n.text does not say NOT: '(margin (:0' is the text of a NOT atom and of a plain one
        got = self.choice_cache.get(ck)
        self.choice_stats['calls'] += 1
        if got is None:
            c0 = time.process_time()
            self.choice_stats['misses'] += 1
            got = ([1.0] * len(popts), 1.0)
            pre = None if self.rel_off else self.rel_prefix(fr, key, k)
            if pre is not None:
                row = self.choice_consult_row(fr, n, popts, k, rel, joined, leaf, stop, key, pre)
                c1 = time.process_time()
                self.choice_stats['s_row'] += c1 - c0
                if CHOICE_CHECK:  # debug: the rows that the steer scores, one JSON line each
                    with open(CHOICE_CHECK, 'a') as f_:
                        f_.write(json.dumps(dict(row, id=self.rel_id)) + '\n')
                try:
                    f = choice_scorer().f(row)
                    e = [math.exp(max(-20.0, min(20.0, STEER_CHOICE_BETA * x))) for x in f]
                    got = (e[:len(popts)], e[len(popts)] if stop is not None else 1.0)
                except Exception as e_:  # noqa: BLE001
                    print('STEER_CHOICE: scoring failed: %s: %s' % (type(e_).__name__, str(e_)[:200]), file=sys.stderr, flush=True)
                self.choice_stats['s_score'] += time.process_time() - c1
            if len(self.choice_cache) >= self.cache_cap:
                self.choice_cache.clear()
            self.choice_cache[ck] = got
        return got

    def steer_choice(self, fr, n, popts, opts, k, rel, joined, leaf, stop, key):
        """STEER_CHOICE at a pick of phase n.phase: ({option: factor}, the stop chance under the steer), or (None, stop) where the
        steer is off. At a column pick where the atom may stop, the stop and the columns are one softmax of weights, so q's stop chance is
        the stop's share of the steered weights (q's column weights, normalised, taking the place of P's)."""
        if not popts or not self.choice_on(n.phase) or (self.force is not None and not self.gq):
            return None, stop
        cf, sf = self.choice_factors(fr, n, popts, k, rel, joined, leaf, stop if n.phase == 'cols' and leaf else None, key)
        fm = dict(zip(popts, cf))
        if n.phase == 'cols' and leaf and opts:
            ws = self.weights(n, opts, rel, joined, leaf, True)
            tw = sum(ws)
            if tw > 0:
                sw = sum(w * fm[o] for o, w in zip(opts, ws)) / tw
                stop = stop * sf / (stop * sf + (1 - stop) * sw)
        return fm, stop

    relrows = None  # with a list here, a forced atom's start adds its options and pick to it (REL_ROWS)

    def option_info(self, o, share):
        """An atom-start option for REL_ROWS: token, kind, program name, columns and types where known, and P's share."""
        name, kind = self.V.name(o), self.fr.KIND[o]
        if o == M.NOT or o in M.CMP:
            return dict(tok=name, kind='op', name=OPS.get(name, name), p=share)
        if kind == 'relation':
            ts = self.decl_types.get(M.slot_no(name))
            return dict(tok=name, kind='derived', name=self.prog_names.get(name, name), p=share,
                        types=[str(t) for t in ts] if ts else None)
        ts = self.types.get(name)
        return dict(tok=name, kind='lib', name=name, p=share, columns=self.reg.get(name),
                    types=[str(t) for t in ts] if ts else None)

    parts = None  # with a Counter here, a forced atom adds each pick's log p to it by decision (`part`)

    def part(self, name, lp):
        if self.force is not None and self.parts is not None:
            self.parts[name] += lp

    def col_rates(self, n, rel, os):
        """With COL_FREQ, each column option's rate in gold atoms of rel (named / atoms), smoothed; None where rel has no
        gold atoms or a column has no registry name. With ORDER_FREE col, a derived relation's columns take COL_TYPE's rate
        for the column's kind (col_kind, from colmap), by place and by whether the kind is in scope, at the atom n."""
        if 'col' in ORDER_FREE and rel == 'declared':
            rt = self.row_rtypes(n.rtok)
            out = []
            for o in os:
                c = self.fr.colpos[o]
                t = col_kind(self.col_type(n.rtok, c), rt, c)
                scoped = t in self.p_scope
                out.append(COL_TYPE.get((self.place, t, scoped), COL_TYPE_DEFAULT[self.place, scoped]))
            return out
        names = self.reg.get(rel)
        uses = sum(v for (r_, _), v in self.c['nsites'].items() if r_ == rel)
        if not COL_FREQ or not names or uses < 3:
            return None
        out = []
        for o in os:
            pos = self.fr.colpos[o]
            if not 0 <= pos < len(names):
                return None
            named = sum(self.c['ckind'][(rel, names[pos], x)] for x in ('fresh', 'join', 'rep', 'zero'))
            out.append(min(max((named + 0.1) / (uses + 0.5), 0.02), 0.98))
        return out

    def col_base(self, n, os, rel, leaf):
        """P's count weight of each column option in os at cols node n, before STRUCT_C."""
        fr = self.fr
        fwd = [o for o in os if fr.colpos[o] > n.last]
        back = [o for o in os if fr.colpos[o] <= n.last]
        rates = self.col_rates(n, rel, fwd) if fwd else None
        if rates is not None:
            w = dict(zip(fwd, self.col_weights(rates)[0]))
        else:
            w = {o: (0.5 if leaf else 0.2) ** i for i, o in enumerate(fwd)}
        top = max(w.values()) if w else 1.0
        w.update({o: BACK_COL * top for o in back})
        return w

    def struct_col(self, n, os, w, stop=None):
        """STRUCT_C at cols node n: the weight of each column option in os from P's weights w (a dict), and, given P's
        chance to stop here, the new chance to stop (a softmax over the columns and the stop). With ORDER_FREE col, a derived relation's
        weights and stop stay as they are."""
        W, fr = COL_W, self.fr
        ts = [str(t) for t in (self.rel_types(n.rtok) or [])] if n.rtok is not None else []
        st = list(self.p_scope)
        name = self.V.name(n.rtok) if n.rtok is not None else ''
        derived, inp, k1 = name.startswith('&r'), name == 'input', self.p_k == 1
        if derived and 'col' in ORDER_FREE:  # the coins of col_rates are a product over the columns: a softmax over the options would break it
            return {o: w[o] for o in os}, stop
        named = [int(x) for x in re.findall(r'\(:(\d+)', n.text)]
        last = named[-1] if named else -1
        tot = sum(w[o] for o in os) or 1.0
        go = 1.0 - stop if stop is not None else 1.0
        z, left = {}, 0
        for o in os:
            c = fr.colpos[o]
            t = ts[c] if c < len(ts) else None
            m = st.count(t) if t else 0
            left += m > 0
            if w[o] <= 0:
                continue
            z[o] = (W['logp'] * math.log(go * w[o] / tot) + W['col0'] * (c == 0) + W['pos_log'] * math.log1p(c)
                    + W['type_in_scope'] * (m > 0) + W['type_count_log'] * math.log1p(m) + W['type_unknown'] * (t is None)
                    + W['derived'] * derived + W['input'] * inp + W['k1'] * k1 + W['back'] * (c < last)
                    + W['after_gap'] * (c > last + 1))
        if stop is not None and stop > 0:
            z[None] = (W['logp'] * math.log(stop) + W['stop'] + W['stop_named'] * math.log1p(len(named))
                       + W['stop_named0'] * (not named) + W['stop_left_in_scope'] * (left > 0) + W['stop_derived'] * derived
                       + W['stop_k1'] * k1)
        mx = max(z.values()) if z else 0.0
        e = {o: math.exp(v - mx) for o, v in z.items()}
        ws = {o: e.get(o, 0.0) for o in os}
        return ws, (e[None] / sum(e.values()) if None in e else stop)

    def col_weights(self, rates):
        """The chance that each column is the next one named, and the chance that none is: rate times the misses of the
        columns before it."""
        ws, miss = [], 1.0
        for p in rates:
            ws.append(miss * p)
            miss *= 1 - p
        return ws, miss

    def weights(self, n, os, rel, joined, leaf, steer, jset=None, must_join=False):
        """The weight of each option in os at node n: its weight under the count prior P, or with steer its weight in the
        proposal, which multiplies in the boosts for the needed types (NEED_BOOST), the joinable relations
        (JOINABLE_BOOST), the first label join (JOIN_BOOST), the wanted labels (WANT_BOOST) and the forms that no kept form
        reads (UNREAD_BETA), and where must_join zeroes
        the options that cannot join a label. jset is the joinable relations at an atom start."""
        fr, c = self.fr, self.c
        if n.phase in ('root', 'root2'):
            nrel = sum(1 for o in os if fr.KIND[o] == 'relation') or 1
            ws, base = [], []
            for o in os:
                if o == M.NOT:
                    base.append(sum(v for r_, v in c['neg'].items() if r_ not in OPS.values()) + ALPHA)  # no negated constraint
                    continue
                r = self.rel_name(o)
                w = c['rel'][r] + ALPHA
                if r == 'declared':
                    w = (c['rel']['declared'] + self.port_rel) / nrel + ALPHA
                if n.phase == 'root2':
                    w = c['neg'][r] + ALPHA
                base.append(w)
            if STRUCT_P:  # a function of the atom start (the clause so far) and its options alone, which many draws share
                ck = (n.phase, self.p_key, self.p_k, self.p_scope, self.p_last, tuple(os))
                got = self.srel_cache.get(ck)
                if got is None:
                    if len(self.srel_cache) >= MEMO_CAP:
                        self.srel_cache.clear()
                    got = self.srel_cache[ck] = self.struct_rel(os, base, self.p_key)
                base = got
            for o, w in zip(os, base):
                if not steer and jset is not None and o in jset:
                    w *= JOIN_P
                if steer:
                    if self.need and o not in M.CMP and self.has_type(o, self.need):
                        w *= self.need_boost
                    if o in self.unread:
                        w *= UNREAD_BOOST
                    if jset is not None and o in jset:
                        w *= JOINABLE_BOOST
                    elif jset and must_join and o != M.NOT and o not in M.CMP:
                        w = 0.0
                ws.append(w)
            if steer and self.tilt and (self.force is None or self.gq):
                ws = [w * math.exp(t) if w > 0 else w for w, t in zip(ws, self.tilt_root(n, os))]
            return ws
        if n.phase == 'cols':
            w = self.col_base(n, os, rel, leaf)
            if STRUCT_C:
                w = self.struct_col(n, os, w)[0]
            return [w[o] * (self.need_boost if steer and self.col_needed(n.rtok, fr.colpos[o]) else 1.0) *
                    (self.want_boost if steer and self.col_wanted(n.rtok, fr.colpos[o]) else 1.0) for o in os]
        if n.phase == 'fcol':
            return [0.6 if o == M.END else 0.4 * 0.5 ** i for i, o in enumerate(os)] if M.END in os else [0.5 ** i for i in range(len(os))]
        if n.phase == 'op':
            return [0.1 if o == M.ZERO else (0.0 if o in (M.STAR, M.CARET) else 1.0) for o in os]
        names = self.reg.get(rel)  # 'val', 'fval'
        col = names[n.last] if n.phase == 'val' and names and 0 <= n.last < len(names) else None
        if col is not None and sum(c['ckind'][(rel, col, x)] for x in ('fresh', 'join', 'rep', 'zero')) > 0:
            fresh = c['ckind'][(rel, col, 'fresh')] + ALPHA
            join = c['ckind'][(rel, col, 'join')] + c['ckind'][(rel, col, 'rep')] + ALPHA
            zero = c['ckind'][(rel, col, 'zero')] + ZERO_FLOOR
        else:
            fresh = c['kind'][(rel, 'fresh')] + ALPHA
            join = c['kind'][(rel, 'join')] + c['kind'][(rel, 'rep')] + ALPHA
            zero = max(c['kind'][(rel, 'zero')] * 0.1, ZERO_FLOOR)  # a relation that gold never wrote with a 0 has the floor too, as a column with counts does
        labs = [o for o in os if fr.KIND[o] == 'label']
        newest = max(labs, key=lambda t: int(self.V.name(t)[1:])) if labs else None
        ws = []
        for o in os:
            if o == M.STAR:
                ws.append(fresh * (self.need_boost if steer and self.col_needed(n.rtok, n.last, n.need if n.phase == 'fval' else None) else 1.0))
            elif o == M.ZERO:
                ws.append(zero)
            elif o == M.CARET:
                ws.append(0.0)
            elif fr.KIND[o] == 'column':  # a field: the column is record-valued
                ws.append((fresh + join) * 0.5 ** fr.colpos[o])
            else:
                boost = JOIN_BOOST if steer and not joined else 1.0
                share = 1.0 / len(labs) if P_DAG else 1.0 if len(labs) == 1 else (0.5 if o == newest else 0.5 / (len(labs) - 1))
                ws.append(boost * join * share * (self.want_boost if steer and o in self.want else 1.0))
        if STRUCT_P and n.phase in ('val', 'fval'):
            ws = self.struct_val(n, os, ws)
        if steer and self.tilt and (self.force is None or self.gq):
            kind = 'der' if rel == 'declared' else 'cmp:' + TILT_CMP[rel] if rel in TILT_CMP else 'lib:' + str(rel)
            f, j = TILT_BETA * TILT_SCALE * self.tilt.get('fresh:' + kind, 0.0), TILT_BETA * TILT_SCALE * self.tilt.get('join:' + kind, 0.0)
            ws = [w * (math.exp(f) if o == M.STAR else math.exp(j) if fr.KIND[o] == 'label' else 1.0) for o, w in zip(os, ws)]
        if steer and must_join and not joined and labs:
            ws = [w if fr.KIND[o] in ('label', 'column') else 0.0 for o, w in zip(os, ws)]
        return ws

    def tilt_kind(self, o):
        if o in M.CMP:
            return 'cmp:' + self.V.name(o)
        return 'der' if self.fr.KIND[o] == 'relation' else 'lib:' + self.V.name(o)

    def tilt_root(self, n, os):
        """The log tilt of each atom-start option os at root or root2 node n: beta times the thetas of the atom's relation kind
        (k), its place (pos) and its predecessor (bi). Under NOT (root2) the kind is N-prefixed. The NOT option takes the
        mean over the relations of the tilts they would have under NOT, so the tilt of a negated atom is split between its
        two picks."""
        T, b = self.tilt, TILT_BETA * TILT_SCALE
        i, prev, neg = min(self.p_k - 1, 3), self.t_prev, n.phase == 'root2'

        def one(o, neg):
            nk = ('N' if neg else '') + self.tilt_kind(o)
            return b * (T.get('k:' + nk, 0.0) + T.get('pos:%d:%s' % (i, nk), 0.0) + T.get('bi:%s>%s' % (prev, nk), 0.0))
        out = [0.0 if o == M.NOT else one(o, neg) for o in os]
        if M.NOT in os:
            ts = [one(o, True) for o in os if o != M.NOT and o not in M.CMP]
            if ts:
                m = max(ts)
                out[os.index(M.NOT)] = m + math.log(sum(math.exp(t - m) for t in ts) / len(ts))
        return out

    def share(self, n, popts, rel, joined, leaf, o, jset=None):
        """o's share of the P weights of the options popts at node n; 0 where o is not among them. jset: the joinable
        relations among popts at an atom start, for JOIN_P."""
        ws = self.weights(n, popts, rel, joined, leaf, False, jset)
        tot = sum(ws)
        return ws[popts.index(o)] / tot if o in popts and tot > 0 else 0.0

    def rel_prefix(self, fr, key, k):
        """The atoms before atom k in the format of a relrows row's `prefix` (body_atoms of the closed clause, as gold's clause is
        rendered), else None where the clause cannot be closed."""
        if k <= 1:
            return []
        if self.rel_text:
            return list(self.p_text or ())
        if key not in self.rel_pre:
            pf = self.rel_closed(fr.root.dec, 1)
            self.rel_pre[key] = body_atoms(pf.split('\n')[self.rel_base]) if pf is not None else None
            if pf is None and 'branch' in STEER_COVER and self.p_text is not None:  # the clause cannot close at a later branch's first atom
                self.rel_pre[key] = list(self.p_text)
        return self.rel_pre[key]

    def rel_dag_fill(self, row, key):
        """The fields that REL_ROWS adds to a row (score_gold): the row's prefix_bases and prefix_depth, from the tokens key before
        the atom, and a derived option's `dag`. The read graph of the forms before the point is built once per Drawer."""
        if self.rel_dag is None:
            c0 = time.process_time()
            try:
                self.rel_dag = dag_info(point_forms(self.rel_dag_src[0]), self.rel_dag_src[1])
            except Exception:
                self.rel_dag = False
            self.rel_stats['s_dag_point'] += time.process_time() - c0
        if not self.rel_dag:
            return
        dag, adj = self.rel_dag
        base_of = lambda tok: (self.prog_names.get(tok) or '').split('.')[0] or None  # noqa: E731
        fields = lambda b: self.rel_dag_f.setdefault(b, dag(b))  # noqa: E731
        pre_bases = frozenset(b for t in key if (b := base_of(self.V.name(t))))
        row['prefix_bases'] = sorted(pre_bases)
        row['prefix_depth'] = max([fields(b)['depth'] for b in pre_bases], default=0)
        for o in row['options']:
            b = base_of(o['tok']) if o['kind'] == 'derived' else None
            if b:
                if (pre_bases, b) not in self.rel_dag_p:
                    self.rel_dag_p[pre_bases, b] = dag_path(adj, pre_bases, b) if pre_bases else None
                o['dag'] = dict(fields(b), base=b, method=o.get('name', '') != b, sibling=b in pre_bases, path=self.rel_dag_p[pre_bases, b])

    def rel_row(self, fr, n, popts, k, scope_types, key, rel, joined, leaf, pre):
        """The row that STEER_REL scores at an atom start of phase n.phase (prefix pre): the options with P's shares, and the DAG fields where the
        model reads them. It is the row that REL_ROWS writes."""
        c1 = time.process_time()
        pj = self.joinable(n, popts, scope_types, key) if JOIN_P != 1 and k > 1 and n.phase == 'root' else None
        pw = self.weights(n, popts, rel, joined, leaf, False, pj)
        tot = sum(pw) or 1.0
        self.rel_stats['s_weights'] += time.process_time() - c1
        row = dict(k=k, phase=n.phase, scope=list(scope_types), prefix=pre, point_group=self.rel_pg,
                   options=[self.option_info(x, round(w / tot, 6)) for x, w in zip(popts, pw)])
        d0 = time.process_time()
        if REL_CHECK or self.sink is not None or ('dag' in rel_scorer().groups if STEER_REL else False):  # the DAG fields, where the model reads them (or the check compares them)
            self.rel_dag_fill(row, key)
        self.rel_stats['s_dag'] += time.process_time() - d0  # includes s_dag_point, the graph's build; s_score leaves both out
        return row

    def group_steer(self, opts, ws, rf):
        """STEER_REL_GROUPS: the steered weights ws[o] * rf[o], scaled within each group (the derived relations, and the other options) to the group's
        total of ws, so that the steer keeps P's split between the groups."""
        derived = [self.fr.KIND[o] == 'relation' for o in opts]
        out = [w * e for w, e in zip(ws, rf)]
        for g in (True, False):
            idx = [i for i, d in enumerate(derived[:len(out)]) if d == g]
            t0, t1 = sum(ws[i] for i in idx), sum(out[i] for i in idx)
            if t1 > 0:
                for i in idx:
                    out[i] *= t0 / t1
        return out

    def derived_steer(self, n, opts, ws, alt, rf, k, scope_types, key):
        """STEER_DERIVED: (ws, alt) after the steer. The derived relations with ws above 0 are D and the other options B. Of the total T of a list, D gets sigma * T, shared
        by exp of the model's score, and B gets (1 - sigma) * T in the steered shape ws * rf. alt takes the same scores and sigma, over its own totals. The scores and sigma
        are cached per (key, phase, k, scope, D)."""
        c0 = time.process_time()
        DERIVED_STATS['calls'] += 1
        is_d = [self.fr.KIND[o] == 'relation' for o in opts]
        d_idx = [i for i, d in enumerate(is_d) if d and ws[i] > 0]
        e, sigma = [0.0] * len(opts), 0.0
        if d_idx:
            dopts = [opts[i] for i in d_idx]
            ck = ('derived', key, n.phase, k, tuple(scope_types), self.p_scope, tuple(dopts))
            got = self.rel_cache.get(ck)
            if got is None:
                DERIVED_STATS['misses'] += 1
                gate_x, opt_x = self.derived_facts(n, dopts, key)
                got = derived_model().score(gate_x, opt_x)
                if len(self.rel_cache) >= self.cache_cap:
                    self.rel_cache.clear()
                self.rel_cache[ck] = got
            sigma, ms = got
            top = max(ms)
            for i, m in zip(d_idx, ms):
                e[i] = math.exp(m - top)
        ws = self.derived_split(is_d, ws, rf, e, sigma)
        if alt is not None:
            alt = self.derived_split(is_d, alt, rf, [x if a > 0 else 0.0 for x, a in zip(e, alt)], sigma)
        DERIVED_STATS['cpu'] += time.process_time() - c0
        return ws, alt

    @staticmethod
    def derived_split(is_d, w, rf, e, sigma):
        """STEER_DERIVED: the weights w with total T where the derived relations (is_d) with e above 0 share T * sigma by e, and the other options share T * (1 - sigma) by
        w * rf. Where no e is above 0, the other options share T, and the derived relations keep w. Where no other option has w * rf above 0, they keep w."""
        out = list(w)
        d_idx, b_idx = [i for i, d in enumerate(is_d) if d], [i for i, d in enumerate(is_d) if not d]
        total, zd, zb = sum(w), sum(e[i] for i in d_idx if w[i] > 0), sum(w[i] * rf[i] for i in b_idx)
        if zd > 0:
            for i in d_idx:
                out[i] = total * sigma * e[i] / zd if w[i] > 0 else 0.0
            total *= 1.0 - sigma
        if zb > 0:
            for i in b_idx:
                out[i] = total * w[i] * rf[i] / zb
        return out

    def derived_base(self, name):
        """(head, j) of the derived relation named name in the names of the scope's forms, j None for a head relation."""
        head, _, sub = self.prog_names.get(name, name).partition('.')
        return head, int(sub) if sub.isdigit() else (sub or None)

    def derived_scope(self):
        """The DerivedScope of the program that this Drawer's body is in, built at the first ask and kept in scope_facts, which the Drawers of one scope share."""
        pg = self.pg
        at = pg.before, len(pg.forms)
        got = self.scope_facts.get('derived')
        if got is None or got[0][0] is not at[0] or got[0][1] != at[1]:
            got = self.scope_facts['derived'] = at, DerivedScope(pg.forms, {self.derived_base('&r%d' % s): t for s, t in pg.rel_tabs.items()})
        return got[1]

    def derived_facts(self, n, dopts, key):
        """STEER_DERIVED: (the gate's facts, a list of each derived option's facts) at an atom start, as dicts of name to value (feats.gate_facts, feats.option_facts). The
        derived relations and the builtin relations among the tokens of key are the drawn ones; no fact reads the order of the forms, of the atoms or of the build."""
        drawn, builtin = set(), False
        for t in key:
            try:
                kind = self.fr.KIND[t]
            except (IndexError, KeyError, TypeError):
                continue
            if kind == 'relation':
                if re.fullmatch(r'&r\d+', self.V.name(t) or ''):
                    drawn.add(self.derived_base(self.V.name(t)))
            elif kind in DERIVED_BUILTIN:
                builtin = True
        st = dict(hk=DERIVED_KIND.get(self.kind, self.kind), pl=self.place if self.place in DERIVED_PLACES else 'other', ph=n.phase,
                  sty=frozenset(map(str, self.p_scope)), dd=drawn, bd=builtin)
        sc = self.derived_scope()
        return sc.gate_facts(st, len(dopts)), sc.option_facts(st, [self.derived_base(self.V.name(t)) for t in dopts])

    def rel_factors(self, fr, n, popts, k, scope_types, key, rel, joined, leaf):
        """STEER_REL: exp(STEER_REL_BETA * f) for each option of popts at a root-phase atom start, f from the model of
        STEER_REL on the row that relrows would write (P's shares unsteered). Cached per point by (key, phase, k, scope)."""
        ck = (key, n.phase, k, tuple(scope_types))
        got = self.rel_cache.get(ck)
        self.rel_stats['calls'] += 1
        if got is None:
            c0 = time.process_time()
            self.rel_stats['misses'] += 1
            got = [1.0] * len(popts)
            pre = None if self.rel_off else self.rel_prefix(fr, key, k)
            c1 = time.process_time()
            self.rel_stats['s_prefix'] += c1 - c0
            if pre is not None:
                row = self.rel_row(fr, n, popts, k, scope_types, key, rel, joined, leaf, pre)
                c2 = time.process_time()
                if REL_CHECK:  # debug: the rows that the steer scores, one JSON line each
                    with open(REL_CHECK, 'a') as f_:
                        f_.write(json.dumps(dict(row, id=self.rel_id)) + '\n')
                try:
                    f = rel_scorer().f(row)
                    got = [math.exp(max(-20.0, min(20.0, STEER_REL_BETA * x))) for x in f]
                except Exception as e:  # noqa: BLE001
                    print('STEER_REL: scoring failed: %s: %s' % (type(e).__name__, str(e)[:200]), file=sys.stderr, flush=True)
                self.rel_stats['s_score'] += time.process_time() - c2
            if len(self.rel_cache) >= self.cache_cap:
                self.rel_cache.clear()
            self.rel_cache[ck] = got
        return got

    def atom(self, fr, k, scope_types=(), key=()):
        """One atom by descent from fr.root; ((node, log q, rel, text, joined, must_join, log p), None) or (None, reason).
        log p is the atom's log probability under the count prior P: at each pick, the share of the chosen option among the
        weights (`weights` with steer off) of all the options the decoder allows, before the reach filter and before the
        picks that drop options. The must_join draw is a proposal device: P ignores it, and q stays conditional on it.
        With self.force (a deque of tokens), the atom takes those tokens, draws nothing and stops where they end; q is then
        the first-pick share of each token."""
        n, lq, lp, rel, joined = fr.root, 0.0, 0.0, None, False
        must_join = k > 1 and self.force is None and self.rng.random() >= UNJOINED
        coin_on = k > 1 and ((EXACT_COIN and self.force is None) or self.gq)
        lj = lf = 0.0  # EXACT_COIN: log q of the path given must_join, and given not

        def done(res):  # the result with log q the mixture over the coin; res[1] is log q given the drawn coin
            if not coin_on:
                return res, None
            terms = [math.log(UNJOINED) + lf]
            if res[4] or self.p_k <= 1:  # an unjoined atom where must_join was drawn is redrawn by the caller
                terms.append(math.log1p(-UNJOINED) + lj)
            m = max(terms)
            mix = m + math.log(sum(math.exp(t - m) for t in terms)) if m > -math.inf else -math.inf
            out = (res[0], mix) + res[2:]
            if len(self.deltas) > 100000:
                self.deltas.clear()
            self.deltas[id(out)] = (mix - res[1], lj, lf)
            if COIN_LOG:  # debug: [joined, must_join, p_k, mixture log q, log q given the drawn coin, lj, lf]
                with open(COIN_LOG, 'a') as f_:
                    f_.write(json.dumps([bool(res[4]), bool(res[5]), self.p_k, mix, res[1], lj, lf]) + '\n')
            return out, None

        while True:
            qa = None
            popts = fr.options(n)
            leaf = fr.is_leaf(n)
            opts = self.reachable(n, popts) if REACH and n.phase not in ('root', 'root2', 'done') else popts
            if n.phase in ('root', 'root2'):
                if not opts:
                    return None, 'no atom start'
                jset = self.joinable(n, opts, scope_types, key) if (k > 1 and n.phase == 'root') else None
                ws = self.weights(n, opts, rel, joined, leaf, True, jset, must_join)
                alt = self.weights(n, opts, rel, joined, leaf, True, jset, not must_join) if coin_on and jset else None
                ws0, alt0 = ws, alt
                if n.phase == 'root' and self.place == 'key' and self.rel_off and 'Ident' not in map(str, scope_types):  # also under self.force: the scores see the factor
                    ident = [self.fr.KIND[o] == 'relation' and self.has_type(o, IDENT) for o in opts]
                    self.key_ident_offered |= any(ident)
                    if self.key_rel_m != 1.0:
                        kf = [self.key_rel_m if x else 1.0 for x in ident]
                        ws = [w * e for w, e in zip(ws, kf)]
                        if alt is not None:
                            alt = [w * e for w, e in zip(alt, kf)]
                if STEER_REL and (self.force is None or self.gq):  # the steer only: P (share, pw) stays unsteered
                    rf = self.rel_factors(fr, n, popts, k, scope_types, key, rel, joined, leaf)
                    if STEER_DERIVED:
                        ws, alt = self.derived_steer(n, opts, ws, alt, rf, k, scope_types, key)
                    elif STEER_REL_GROUPS:
                        ws = self.group_steer(opts, ws, rf)
                        if alt is not None:
                            alt = self.group_steer(opts, alt, rf)
                    else:
                        ws = [w * e for w, e in zip(ws, rf)]
                        if alt is not None:
                            alt = [w * e for w, e in zip(alt, rf)]
                o, q = self.pick_complete(n, opts, ws, key, alt)
                if o is None:
                    return None, 'no completable start'
                qa = self.alt_q if alt is not None else None
                pj = self.joinable(n, popts, scope_types, key) if JOIN_P != 1 and k > 1 and n.phase == 'root' else None
                qp = self.share(n, popts, rel, joined, leaf, o, pj)
                if self.gq:
                    i_ = opts.index(o) if o in opts else None  # gold's relation that the decoder does not allow here: q 0
                    ls = lambda v: None if i_ is None or v is None or not sum(v) or not v[i_] else round(math.log(v[i_] / sum(v)), 4)  # noqa: E731
                    self.gq_rel.append(dict(phase=n.phase, p=round(math.log(qp), 4) if qp else None, free0=ls(ws0), free=ls(ws), join0=ls(alt0), join=ls(alt)))
                if self.sink is not None and self.force is not None:
                    pre = self.rel_prefix(fr, key, k)
                    if pre is not None:
                        self.sink('rel', self.rel_row(fr, n, popts, k, scope_types, key, rel, joined, leaf, pre), self.V.name(o))
                if self.relrows is not None and self.force is not None:
                    pw = self.weights(n, popts, rel, joined, leaf, False, pj)
                    tot = sum(pw) or 1.0
                    self.relrows.append(dict(k=k, phase=n.phase, scope=list(scope_types), gold=self.V.name(o),
                                             options=[self.option_info(x, round(w / tot, 6)) for x, w in zip(popts, pw)]))
                rpart = 'relation ' + ('op' if o == M.NOT or o in M.CMP else 'declared' if fr.KIND[o] == 'relation' else 'lib')
                if o != M.NOT:
                    rel = self.rel_name(o)
            elif n.phase == 'cols':
                j = n.text.count('(:')
                at_j = self.c['nsites'][(rel, j)] + 0.05
                at_least = sum(v for (r_, i), v in self.c['nsites'].items() if r_ == rel and i >= j) + 0.1
                stop = min(at_j / at_least, 0.98)
                if (rates := self.col_rates(n, rel, [o for o in popts if fr.colpos[o] > n.last])) is not None:
                    stop = min(max(self.col_weights(rates)[1], 0.02), 0.98)
                if STRUCT_C and leaf and popts:
                    stop = min(max(self.struct_col(n, popts, self.col_base(n, popts, rel, leaf), stop)[1], 0.01), 0.99)
                fm, stq = self.steer_choice(fr, n, popts, opts, k, rel, joined, leaf, stop, key)  # q's stop chance; P's stays stop
                if leaf and (not opts or (self.rng.random() < stq if self.force is None else
                                          not self.force or fr.KIND[self.force[0]] != 'column')):
                    self.part('column stop', math.log(stop if popts else 1.0))
                    if popts:
                        self.choice(k, n, popts, rel, joined, leaf, 'STOP', stop, fr)
                    if coin_on:  # the stop does not depend on the coin
                        lj += math.log(stq if opts else 1.0)
                        lf += math.log(stq if opts else 1.0)
                    return done((n, lq + math.log(stq if opts else 1.0), rel, fr.render(n), joined, must_join,
                                 lp + math.log(stop if popts else 1.0)))
                if not opts:
                    return None, 'atom cannot close'
                ws = self.weights(n, opts, rel, joined, leaf, True)
                if fm:
                    ws = [w * fm[o_] for o_, w in zip(opts, ws)]
                o, q = self.pick(opts, ws)
                qp = self.share(n, popts, rel, joined, leaf, o)
                if leaf:  # the draw did not stop
                    self.part('column stop', math.log1p(-stop))
                    q *= 1 - stq
                    qp *= 1 - stop
            elif n.phase == 'fcol':
                if not opts:
                    return None, 'record cannot close'
                ws = self.weights(n, opts, rel, joined, leaf, True)
                fm, _ = self.steer_choice(fr, n, popts, opts, k, rel, joined, leaf, None, key)
                if fm:
                    ws = [w * fm[o_] for o_, w in zip(opts, ws)]
                o, q = self.pick_reach(n, opts, ws)
                if o is None:
                    return None, 'record cannot close'
                qp = self.share(n, popts, rel, joined, leaf, o)
            elif n.phase in ('val', 'fval'):
                ws = self.weights(n, opts, rel, joined, leaf, True, None, must_join)
                if sum(ws) == 0:
                    return None, 'no value'
                alt = self.weights(n, opts, rel, joined, leaf, True, None, not must_join) if coin_on else None
                fm, _ = self.steer_choice(fr, n, popts, opts, k, rel, joined, leaf, None, key)
                if fm:
                    ws = [w * fm[o_] for o_, w in zip(opts, ws)]
                    if alt is not None:
                        alt = [w * fm[o_] for o_, w in zip(opts, alt)]
                o, q = self.pick_reach(n, opts, ws, alt)
                if o is None:
                    return None, 'no value can close'
                qa = self.alt_q if alt is not None else None
                qp = self.share(n, popts, rel, joined, leaf, o)
            elif n.phase == 'done':
                return done((n, lq, rel, fr.render(n), True, must_join, lp))
            elif n.phase == 'op':
                ws = self.weights(n, opts, rel, joined, leaf, True)
                if not opts or sum(ws) == 0:
                    return None, 'no operand'
                fm, _ = self.steer_choice(fr, n, popts, opts, k, rel, joined, leaf, None, key)
                if fm:
                    ws = [w * fm[o_] for o_, w in zip(opts, ws)]
                o, q = self.pick_reach(n, opts, ws)
                if o is None:
                    return None, 'no operand can close'
                qp = self.share(n, popts, rel, joined, leaf, o)
            else:
                return None, 'phase %s' % n.phase
            if n.phase not in ('root', 'root2'):
                self.choice(k, n, popts, rel, joined, leaf, self.V.name(o), stop if n.phase == 'cols' and leaf else None, fr)
            if n.phase in ('val', 'fval') and self.on_value is not None and self.force is not None:
                self.on_value(k, fr, n, popts, self.V.name(o))
            lq += log0(q)
            lp += log0(qp)
            if coin_on:  # a pick whose weights do not read must_join has the same share under both coin values
                qa = q if qa is None else qa
                lj += log0(q if must_join else qa)
                lf += log0(qa if must_join else q)
            if n.phase == 'cols' and leaf:
                self.part('column', log0(qp) - math.log1p(-stop))
            else:
                self.part(rpart if n.phase in ('root', 'root2') else {'cols': 'column', 'fcol': 'field', 'val': 'value',
                           'fval': 'value', 'op': 'operand'}[n.phase], log0(qp))
            if n.phase in ('val', 'fval') and fr.KIND[o] == 'label':
                joined = True
            ch = fr.child(n, o)
            if ch is None:
                return None, 'refused %s' % self.V.name(o)
            n = ch


# ---------------------------------------------------------------- one point

@functools.cache
def online_scorer(task, case, point, mode='1'):
    sys.path.insert(0, P.STUDY)
    os.environ.setdefault('FSTORE_POINTS', FSTORE.rstrip('/'))  # the scorer reads each point from the sampler's feature store
    import online_score
    if mode == 'norows':
        return online_score.PointScorer(task, case, list(point), rules=None, soft=online_score.SOFT_NOROWS)
    return online_score.PointScorer(task, case, list(point))


@functools.cache
def cut_scorer(task, case, point):
    sys.path.insert(0, P.STUDY)
    os.environ.setdefault('FSTORE_POINTS', FSTORE.rstrip('/'))
    import cut_score
    return cut_score.CutScorer(task, case, list(point))


class DerivedModel:
    """STEER_DERIVED's model, the export of the derived-pick fit, a pickle of plain numbers: for the option logit, logit_names with logit_mean, logit_scale and logit_beta,
    coltypes (a column type fact ct:T of a T not among them counts as ct:other) and logit_ignore (facts that the logit leaves out); for the gate, gate_names with
    gate_mean, gate_scale and gate_coef, gate_intercept, and the calibration temp and bias on the gate's logit; version."""

    def __init__(self, path):
        with open(path, 'rb') as f:
            d = pickle.load(f)
        self.version, self.coltypes, self.ignore = d['version'], set(d['coltypes']), set(d['logit_ignore'])
        self.w = {n: b / s for n, b, s in zip(d['logit_names'], d['logit_beta'], d['logit_scale'])}
        self.w0 = -sum(b * m / s for b, m, s in zip(d['logit_beta'], d['logit_mean'], d['logit_scale']))
        self.gw = {n: c / s for n, c, s in zip(d['gate_names'], d['gate_coef'], d['gate_scale'])}
        self.g0 = d['gate_intercept'] - sum(c * m / s for c, m, s in zip(d['gate_coef'], d['gate_mean'], d['gate_scale']))
        self.temp, self.bias = d['temp'], d['bias']

    def logit(self, facts):
        """The score of one option from its facts, a dict of name to value. A name that the model does not know is an error."""
        s = self.w0
        for name, v in facts.items():
            if name in self.ignore:
                continue
            if name.startswith('ct:') and name[3:] not in self.coltypes and name != 'ct:other':
                name = 'ct:other'
            s += self.w[name] * v
        return s

    def score(self, gate_x, opt_x):
        """(sigma, [s for each option]): the gate's share of P's total for the derived relations, and each option's score. gate_x are the gate's facts but lse and mx, which come
        from the scores."""
        ms = [self.logit(x) for x in opt_x]
        top = max(ms)
        lse = top + math.log(sum(math.exp(m - top) for m in ms))
        z = self.g0
        for name, v in dict(gate_x, lse=lse - math.log(len(ms)), mx=top - lse).items():
            z += self.gw[name] * v
        z = z * self.temp + self.bias
        return 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, z)))), ms


_DERIVED = []


def derived_model():
    if not _DERIVED:
        _DERIVED.append(DerivedModel(STEER_DERIVED))
    return _DERIVED[0]


DERIVED_FORMS = ('RULE', 'DET', 'INIT', 'RIGID_DET', 'DEMONSTRATED')
DERIVED_KIND = dict(RIGID_DET='DET', DEMONSTRATED='INIT')  # a sparse kind -> the kind whose facts it takes: a DEMONSTRATED form is a DemonstrationConsistency instance
DERIVED_PLACES = ('RULE', 'DET', 'port', 'key', 'other')
DERIVED_BUILTIN = ('lib relation', 'relation macro', 'fact relation')
class RelTable:
    """The AssignmentSummaries of one table at a query's end, kept for STEER_DERIVED. facts() gives the TableHash of each, the column types, the row counts of the table's
    TableVector (lmean, lmax and share, over its train entries and its assignments), whether a column label is blank and whether the table has no TableHash (a table past the work
    cap). It reads no rows."""
    NONE = dict(key=None, types=[], lmean=0.0, lmax=0.0, share=0.0, blank=False, nt=True)

    def __init__(self, rows):
        self.rows, self.got = rows, None

    def facts(self):
        if self.got is None:
            rs = self.rows
            if not rs or any(r.hash is None for r in rs):
                self.got = self.NONE
            else:
                if TA.pooled(rs, 'n_train'):
                    lmean, lmax, share = (TA.pooled(rs, k) for k in ('lmean', 'lmax', 'share'))
                else:  # a task-wide table has no train entries, and the TableVector's row counts are over train entries: its counts are those of its examples (ExampleKey.rows)
                    nr = [k[3] for r in rs for k in r.examples]
                    lmean, lmax, share = math.log1p(sum(nr) / len(nr)) if nr else 0.0, math.log1p(max(nr)) if nr else 0.0, sum(1 for x in nr if x > 0) / len(nr) if nr else 0.0
                self.got = dict(key=tuple(sorted(r.hash for r in rs)), types=list(rs[0].types), lmean=lmean, lmax=lmax, share=share, blank='' in rs[0].labels, nt=False)
            self.rows = None
        return self.got


class DerivedScope:
    """STEER_DERIVED: what a pick reads of a program's forms and tables. forms: the parsed forms before the clause, with the heads that the decoder gives them; tabs: (head, j) ->
    RelTable. A form's parents are the forms that its text reads. Its depth is 1 more than its parents' largest. The facts are the derived-pick fit's (feats.Scope, option_facts and
    gate_facts of its code), from sets and flags of the forms and the atoms drawn, none from an order."""

    def __init__(self, forms, tabs):
        self.kind, reads = {}, {}
        for f in forms:
            if f and f[0] in DERIVED_FORMS and len(f) > 1 and isinstance(f[1], str):
                self.kind[f[1]] = DERIVED_KIND.get(f[0], f[0])
                reads[f[1]] = strata.reads_of(f[2:], set()) - {f[1]}
        self.parents = {h: rs & self.kind.keys() for h, rs in reads.items()}
        self.depth, self.anc = {}, {}

        def walk(h):
            if h not in self.depth:
                self.anc[h] = set()
                for p in self.parents[h]:
                    walk(p)
                    self.anc[h] |= {p} | self.anc[p]
                self.depth[h] = 1 + max((self.depth[p] for p in self.parents[h]), default=0)
        for h in self.parents:
            walk(h)
        self.maxdepth = max(self.depth.values(), default=1)
        self.readers = collections.Counter(p for ps in self.parents.values() for p in ps)
        self.nforms, self.tabs, self.rels = len(self.kind), tabs, {}
        self.nrel = collections.Counter(h for h, _ in tabs if h in self.kind)

    def rel(self, base):
        """The facts of the relation base, (head, j), that the options read about it; None where its form is not in the scope."""
        r = self.rels.get(base)
        if r is None and base[0] in self.kind:
            t, h = self.tabs[base].facts() if base in self.tabs else RelTable.NONE, base[0]
            r = self.rels[base] = dict(
                head=h, sub=base[1] is not None, key=t['key'], types=tuple(sorted(t['types'])), nt=int(t['nt']), arity=len(t['types']), ct=collections.Counter(t['types']),
                lmean=t['lmean'], lmax=t['lmax'], share=t['share'],
                blank=int(t['blank']), depth=self.depth[h], leaf=int(self.readers[h] == 0), root=int(not self.parents[h]), lread=math.log1p(self.readers[h]),
                lnrel=math.log(max(self.nrel[h], 1)))
        return r

    def option_facts(self, st, bases):
        """The facts of the derived options at bases ((head, j) each), a dict of name to value each with the facts that are 0 left out. st: hk (head kind), pl (place), ph (phase),
        sty (the label types in scope), dd (the set of derived relations drawn), bd (whether a builtin relation was drawn)."""
        hk, pl, drawn, stys = st['hk'], st['pl'], st['dd'], st['sty']
        rs = [self.rel(b) for b in bases]
        same_types = collections.Counter(r['types'] for r in rs if r is not None)
        same_key = collections.Counter(r['key'] for r in rs if r is not None and r['key'] is not None)
        drel = [r for r in map(self.rel, drawn) if r is not None]
        dkeys = collections.Counter(r['key'] for r in drel if r['key'] is not None)
        dtypes = set().union(*[r['types'] for r in drel])
        dfids = {d[0] for d in drawn}
        danc = set().union(*[self.anc.get(f, ()) for f in dfids])
        dsib = collections.Counter(d[0] for d in drawn)
        out = []
        for b, r in zip(bases, rs):
            f = {}
            if r is None:  # an option whose form is not in the scope: no fact but the flags
                f['notab'], f['nosc'] = 1.0, float(not stys)
                out.append({k: v for k, v in f.items() if v})
                continue
            h, a, me = r['head'], r['arity'], b in drawn
            f['ar%d' % min(max(a, 1), 4)] = 1.0 if a else 0.0
            f['lmean'], f['lmax'], f['share'] = r['lmean'], r['lmax'], r['share']
            for t, c in r['ct'].items():
                f['ct:' + t] = float(c)
            f['blank'], f['notab'] = float(r['blank']), float(r['nt'])
            tin = sum(c for t, c in r['ct'].items() if t in stys)
            f['tin'], f['tinf'] = float(tin), tin / a if a else 0.0
            f['nosc'] = float(not stys)
            f['dupt'] = math.log1p(same_types[r['types']] - 1)
            f['dupk'] = float(r['key'] is not None and same_key[r['key']] > 1)
            f['d%d' % min(r['depth'], 4)] = 1.0
            f['dmax'] = float(r['depth'] - self.maxdepth)
            f['deep'] = float(r['depth'] == self.maxdepth)
            f['leaf'], f['root'], f['lread'] = float(r['leaf']), float(r['root']), r['lread']
            f['kk:%sx%s' % (self.kind[h], hk)] = 1.0
            f['sub'], f['lnrel'] = float(r['sub']), r['lnrel']
            f['dr_self'] = float(me)
            f['dr_sib'] = float(dsib[h] > me)
            f['dr_anc'] = float(h in danc)
            f['dr_desc'] = float(bool(dfids & self.anc.get(h, set())))
            f['dr_par'] = float(any(df != h and self.parents[df] & self.parents[h] for df in dfids if df in self.parents))
            f['dr_key'] = float(r['key'] is not None and dkeys[r['key']] > me)
            f['dr_type'] = float(bool(set(r['types']) & dtypes))
            if not drawn:
                f['x_nod_leaf'], f['x_nod_deep'], f['x_nod_tin'] = f['leaf'], f['deep'], f['tin']
            f['x_%s_leaf' % pl], f['x_%s_sub' % pl], f['x_%s_dmax' % pl] = f['leaf'], f['sub'], f['dmax']
            if st['ph'] == 'root2':
                f['x_r2_self'], f['x_r2_leaf'] = f['dr_self'], f['leaf']
            out.append({k: round(v, 4) for k, v in f.items() if v})
        return out

    def gate_facts(self, st, n_d):
        """The gate's facts at an atom start with n_d derived options, as option_facts gives its facts; the gate's two facts of the scores, lse and mx, are left to the model."""
        dd = bool(st['dd'])
        f = {'hk:' + st['hk']: 1.0, 'pl:' + st['pl']: 1.0, 'lnD': math.log(max(n_d, 1)), 'lnf': math.log(max(self.nforms, 1)), 'r2': float(st['ph'] == 'root2'),
             'dd': float(dd), 'bd': float(st['bd']), 'both': float(dd and st['bd']), 'nosc': float(not st['sty'])}
        return {k: round(v, 4) for k, v in f.items() if v}


@functools.cache
def rel_scorer():
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import relsteer
    return relsteer.Scorer(STEER_REL, STEER_REL_MODEL)


@functools.cache
def choice_scorer():
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import choicefeat
    return choicefeat.Scorer(STEER_CHOICE)


@functools.cache
def steer_model():
    from rulecheck import SoftScore
    return SoftScore(STEER_MODEL)


def settings():
    kw = dict(rule_tests=False,
              table_work_cap=int(os.environ.get('WORK_CAP', 1048576 * 2)))  # gold passes at every dev point (runG2)
    if STATIC_MASK:
        kw['static_pruning'] = True
    return arclog.DecodeSettings(**kw)


class Prefix:
    """Gold's program of a task and case, stepped token by token with its tables; the points of one program share it."""

    def __init__(self, spec):
        self.task, self.case = spec['task'], spec['case']
        self.st = settings()
        self.sess = arclog.Session(arclog.Task.from_json(open(TASKS + self.task + '.json').read(), arclog.World.Closed), self.st, session_bytes=SESSION_BYTES)
        gp = arclog.StudyProgram.from_sexp(spec['gold_sexp'], self.st)
        self.original = None  # the original gold program (an INIT port's whole INIT program), for point_info
        try:
            np_ = self.original = arclog.StudyProgram.from_sexp(spec['written_sexp'], self.st) if spec.get('written_sexp') else (
                arclog.StudyProgram.from_sexp(spec['port']['full_sexp'], self.st) if spec.get('port') else gp)
            nm = json.loads(np_.relation_source_names_json(GEN, self.task, self.case))  # it refuses a program in any other form order
            self.names = {'&r%d' % r['relation_slot']: r['display_name'] for r in nm['relations']}
            if spec.get('written_sexp'):
                self.names = moved_names(nm['relations'], spec['port']['full_sexp'] if spec.get('port') else spec['gold_sexp'])
        except Exception as e:  # noqa: BLE001
            self.names = {'_error': '%s: %s' % (type(e).__name__, str(e)[:200])}
        try:
            self.native_rel = native_relations(gp)
            self.native = native_types(self.native_rel)
        except Exception:  # noqa: BLE001
            self.native_rel, self.native = [], {}
        self.ids, self.model, self.paths = gp.decode_stream()
        self.dec = self.sess.decoder()
        self.V = self.dec.vocabulary
        self.before, self.decl_types, self.decl_slots, self.pos = None, {}, {}, 0

    def point_info(self, fp):
        """{body_path, clause_path, kind} of the point fp in the original program's points()."""
        return point_info(self.original, list(fp))

    def first(self, point):
        return list(M.atoms_of(self.paths, self.ids, self.model, point).values())[0][0]

    def advance(self, first):
        for i in range(self.pos, first):
            if self.model[i]:
                self.dec.step(self.ids[i])
                self.before = b = TA.export(self.dec, self.task, self.case, self.before, rows=False)
                T = b.tables
                rel = M.col(b, 'tables', 'relation') if isinstance(T['relation'], (bytes, bytearray, memoryview)) else T['relation']
                for j in range(len(T['form'])):
                    if rel[j] >= 0:
                        self.decl_types[int(rel[j])] = [str(t) for t in T['column_types'][j]]
                        self.decl_slots[int(rel[j])] = [int(c) for c in T['column_slots'][j]]
        self.pos = max(self.pos, first)


def run_point(spec, draws, seconds, counts, hazard, regcols, pre=None, make_samples=False, engine_stats=False):
    task, case, point = spec['task'], spec['case'], spec['point']
    t0, c0 = time.time(), time.process_time()
    if engine_stats:  # info['engine'] gets the point's CPU ms per engine phase; the collection costs time
        arclog.engine_stats(reset=True, collect=True)
    pre = pre or Prefix(spec)
    rc = RuleCheck(spec['point_dir'], warm=False)  # the feature study's checks at this point; each call names its functions
    if spec.get('written_sexp'):  # the checks read the same prefix as the decoder
        rc.state.prefix = spec['prefix_lines']
        rc.state.point = [len(spec['prefix_lines'])] + list(rc.state.point[1:])
    sp_keys = [k for k in rc.rules if rc.classes.get(k) in PREFIX_CLASSES and k != 'h3_repeated_test.dup' and k not in SP_CUT_EXEMPT]
    sp_functions = sorted({k.split('.', 1)[0] for k in sp_keys} | {'h3_repeated_test'})
    regtypes = lib_types(rc, regcols)
    st, sess, names = pre.st, pre.sess, pre.names
    ids, model, paths, V = pre.ids, pre.model, pre.paths, pre.V
    PRUNE_SESSIONS['sess'] = sess
    if GC_TUNE:
        import gc
        gc.set_threshold(100000, 50, 100)  # no gc.freeze: a frozen cycle that a later point drops is never collected
    by = M.atoms_of(paths, ids, model, point)
    first = list(by.values())[0][0]
    port = spec.get('port')  # gold_sexp holds the port's body as a RULE in its INIT's place; X is its table projected on the head
    pre.advance(first)
    dec, before, decl_types = pre.dec.fork(), pre.before, dict(pre.decl_types)
    base_forms = n_forms(dec.program_form())
    END = M.END
    seed_point, written_point = spec.get('seed_point', point), spec.get('written_point', point)
    rng = random.Random(M.seed_of(task, case, seed_point, SEED_TAG))
    ndecl = 1 + max([M.slot_no(V.name(ids[i])) for i in range(first)
                     if not model[i] and V.kind(ids[i]) == 'relation'] + [-1])
    for s, ts in pre.native.items():  # an INIT port's relation that no prefix table typed
        if s < ndecl:
            decl_types.setdefault(s, ts)
    entries = {sl: list(zip(c, pre.decl_types[sl])) for sl, c in pre.decl_slots.items() if c}
    for e in pre.native_rel:  # (logical slot, type) of each physical column
        ws = sorted(e.get('column_witnesses') or [], key=lambda w: w['physical_column'])
        if e['relation_slot'] not in entries and e.get('column_witness_status') == 'complete' and ws and all(w.get('type') for w in ws):
            entries[e['relation_slot']] = [(w['logical_slot'], str(w['type'])) for w in ws]
    colmap = column_positions(dec, V, entries, ndecl)
    if port:  # gold's INIT line, relations by slot
        fids, fmodel, fpaths = arclog.StudyProgram.from_sexp(port['full_sexp'], st).decode_stream()
        g = sess.decoder()
        for i in range(len(fids)):
            if fpaths[i] and fpaths[i][0] > point[0]:
                break
            if fmodel[i]:
                g.step(fids[i])
        init_line = g.program_form().split('\n')[base_forms]
    port_need = []  # per typed head column of a port, the label types it takes
    for col, _ in (port or {}).get('head', ()):
        T = port['ctypes'].get(col)
        if T is not None and (T not in port['params'] or T == 'Point'):
            port_need.append({'Position', 'Box'} if T == 'Point' else next((set(f) for f in FAMILIES if T in f), {T}))
    ff = FastFrontier(V, ndecl, regcols)
    for t in range(len(V)):  # the positions are the table's columns, after an Example column the table may leave out
        if V.kind(t) == 'relation' and entries.get(M.slot_no(V.name(t))):
            ff.arity[t] = len({c for c, _ in entries[M.slot_no(V.name(t))]}) + 2
    dr = Drawer(V, counts, rng, regcols, ff, regtypes)
    dr.prog_names = names if isinstance(names, dict) else {}
    dr.decl_types, dr.colmap = decl_types, colmap
    rows = []
    tries = collections.Counter()
    gold_atoms = [[ids[i] for i in idx if model[i]] for idx in by.values()]
    group = (spec.get('point_group') or {}).get('point_group')
    steer_on = STEER_M > 1 and not port and (not STEER_GROUPS or group in STEER_GROUPS)  # STEER_M steers atoms k <= STEER_K here
    tilt_tab = (TILT_TABLE or {}).get(group)  # None: no tilt at this point (the output group has none)
    dr.tilt = tilt_tab['theta'] if tilt_tab else None

    xacc = [0.0, 0, 0.0]  # the draw's sum of -log A^ over its sites (EXACT), the number of sites, and the sum of the coin corrections (EXACT_COIN)
    picked = []  # [(head column, label)] that port_unread drew for the draw that is about to stop
    memo = {}  # (clause tokens before an atom, the atom's tokens) -> its closed program, repeat counts, table and static prune
    safes = {}  # the same key -> whether the clause can end after the atom (can_end, a full check of the closed clause)

    def head_cands(tb, T):
        """The columns of body table tb that a head column of type T can take."""
        return [i for i, t in enumerate(str(t) for t in tb['types']) if T is None or (
            (t in ('Position', 'Box') if T == 'Point' else True) if T in port['params'] else compat(t, T))]

    def port_x(tb, rule_line, is_gold):
        """(X, clause text, head) of a port whose body has table tb and RULE text rule_line: gold's head, or for a draw
        a label for each of gold's head columns of a type the component allows; the clause text is gold's INIT line
        with the port replaced."""
        if tb.get('counted'):
            return None, 'the body table has Count entries'
        bl = binders(M_sexprs(rule_line)[0][2:], [])
        types = [str(t) for t in tb['types']]
        m = dict(zip(binders(port['atoms'], []), bl))
        cols, head = [], []
        for col, glab in port['head']:
            T = port['ctypes'].get(col)
            if is_gold:
                if m.get(glab) not in tb['labels']:
                    return None, 'gold head label %s not in the body table' % glab
                i = tb['labels'].index(m[glab])
            else:
                cand = head_cands(tb, T)
                if not cand:
                    return None, 'no label for head column %s' % col
                want = dict(picked).get(col)  # the head that the stop gate drew
                i = tb['labels'].index(want) if want in tb['labels'] else rng.choice(cand)
            cols.append((col, i, T if T and T not in port['params'] else types[i]))
            head.append((col, tb['labels'][i]))
        return (project(tb, cols), port_text(rule_line, head), head), None

    def port_text(rule_line, head, keep=False):
        """Gold's INIT line with the port replaced by the body of RULE text rule_line under head [(column, label)]; the
        body's labels are renamed to names that the INIT line does not use. With keep, the label of each head column takes
        gold's label for that column (so the head text is gold's), and the other labels take names that no label of the
        INIT's other elements uses, as gold numbers repeated labels (P, P2, ...): a label stays where it collides with none.
        None where no renaming gives gold's head: a label under two columns that gold binds to different labels, or the reverse."""
        atoms = M_sexprs(rule_line)[0][2:]
        f = M_sexprs(init_line)[0]
        at = [j for j, x in enumerate(f) if j >= 3 and isinstance(x, list) and x and x[0] == port['name']]
        used = set(re.findall(r'(?<![:\w])[A-Za-z_]\w*', sx(f[:at[0]] + f[at[0] + 1:])) if keep else re.findall(r'[A-Za-z_]\w*', init_line))
        ren = {}
        if keep:
            for (_, lb), (_, glab) in zip(head, port['head']):
                if ren.setdefault(lb, glab) != glab or lb not in binders(atoms, []):
                    return None
            if len(set(ren.values())) < len(ren):
                return None
            used |= set(ren.values())
        for b in dict.fromkeys(binders(atoms, [])):
            if b in ren:
                continue
            if keep:
                new, base, k = b, b.rstrip('0123456789') or b, 2
                while new in used:
                    new, k = '%s%d' % (base, k), k + 1
            else:
                k = 0
                while 'Z%d' % k in used:
                    k += 1
                new = 'Z%d' % k
            ren[b] = new
            used.add(new)
        f[at[0]] = [port['name'], [[':' + c, ren.get(lb, lb)] for c, lb in head]] + renamed(atoms, ren)
        return sx(f)

    def can_end(d):
        try:
            d.forced(END)
            return True
        except arclog.Refusal:
            return False

    def closed_program(d, ends):
        """The program text that decoder d gives when `ends` END tokens close it, or None where the decoder refuses."""
        f = d.fork()
        try:
            for _ in range(ends):
                f.step(END)
        except arclog.Refusal:
            return None
        return f.program_form()

    dr.rel_closed, dr.rel_base, dr.rel_pg, dr.rel_off = closed_program, base_forms, spec.get('point_group'), bool(port)
    dr.rel_id = [task, case, list(written_point)]
    head, dr.hist = prior_history(V, ids, model, paths, point[0])
    dr.row_pg = dict(kind='INIT' if port else head)  # the clause's head; whether OUT reads a RULE is not known before OUT
    dr.rel_dag_src = (spec, point[0])

    def static_hit(pf, path):
        """Whether the static prune of program text pf (a closed program, or None) matches the node at path: the atom that
        was just taken. Where the program cannot be closed, there is no match. The prune reads whole programs, so an atom in
        an OR branch is tested only in the last branch, which one more END closes."""
        if pf is None:
            return False
        js, _ = static_prune(pf, base_forms, st)
        return bool(js) and any(m['path'] == path and m.get('class') != 'valid' for m in js['matches'])

    def clause_value(clause, key):
        """the feature study's value `key` ('<function>.<key>') on clause text, with the relation slots (`&r2`) written as
        the program's names; None where the function raised (rc.errors counts those)."""
        return rc.values(rename_relations(clause, names), NO_ROWS, functions=[key.split('.')[0]]).get(key)

    def stop_gate(draw, clause):
        """Why the output clause may not stop with table draw['x'] and draw['x_rows'] (the draw's own keys): 'out columns'
        or 'same every example', where the feature study's q5b_output_columns or q5a_output_tables fires, or 'fewer cells'
        (CELLS_GATE), where q5c_output_cells.fewer_cells_f1 fires; else None."""
        clause = rename_relations(clause, names)
        fns = ['q5b_output_columns', 'q5a_output_tables'] + (['q5c_output_cells'] if CELLS_GATE else [])
        v = rc.values(clause, rc.draw_x(draw, clause), functions=fns, out_reads=True)
        return ('out columns' if v.get('q5b_output_columns.out_columns_f0') else
                'same every example' if v.get('q5a_output_tables.same_every_example_g') else
                'fewer cells' if CELLS_GATE and v.get('q5c_output_cells.fewer_cells_f1') else None)

    def steer_score(got, key, cnt=None):
        """The cut score of the clause cut after a candidate atom ((res, tb), memo key): its closed clause with the table
        tb, scored as a draw is; STEER_FLOOR where there is no clause or table, or the score raises (cnt counts the errors
        and, for STEER_ONLINE=cut, the nan scores; the draw's dtries where None)."""
        cnt = dtries if cnt is None else cnt
        (res, tb), m = got, memo.get(key) or {}
        pf = m['pf'] if 'pf' in m else closed_program(res[0].dec, 1)
        if pf is None or tb is None:
            return STEER_FLOOR
        try:
            if STEER_ONLINE == 'cut':  # the cut as a cuts.jsonl row (no X rows: the scorer reads none), a log-odds; nan where it has no score
                sc = cut_scorer(task, case, tuple(written_point)).score([dict(clause=pf.split('\n')[base_forms], x=summary(tb), x_rows=[], fail=None,
                                                                    out_reads=bool(out_reads))], names)[0]
                if sc != sc:
                    cnt['steer nan'] += 1
                    return STEER_FLOOR
                return sc
            if STEER_ONLINE:  # a cut that fails a hard rule gets the floor
                ps = online_scorer(task, case, tuple(written_point), STEER_ONLINE)
                r = ps.score(dict(clause=pf.split('\n')[base_forms], x=summary(tb), fail=None,
                                  x_rows=rows_with_models(tb, X_ROWS_CAP) if getattr(ps, 'needs_rows', True) else []), names)
                return r['soft_score'] if r.get('passes') is True and r.get('soft_score') is not None else STEER_FLOOR
            clause = rename_relations(pf.split('\n')[base_forms], names)
            draw = dict(x=summary(tb), x_rows=rows_with_models(tb, X_ROWS_CAP))
            return steer_model().score(rc, clause, rc.draw_x(draw, clause), out_reads=rc.gold_out_reads(clause))
        except Exception as e:  # noqa: BLE001
            cnt['steer error: %s' % type(e).__name__] += 1
            return STEER_FLOOR

    def dup_count(pf):
        """(dup, dup_cmp, sp) on the clause that ends program text pf: dup and dup_cmp of h3_repeated_test (the atoms that
        repeat another atom of their conjunction or of an enclosing one, and the comparison atoms among those counted again
        by dup_cmp), and sp, the sum of the other hard keys of class SP (fixed once the atom that completes them is
        placed); (0, 0, 0) where pf has no clause at the point."""
        if base_forms >= n_forms(pf):
            return 0, 0, 0
        v = rc.values(rename_relations(pf.split('\n')[base_forms], names), NO_ROWS, functions=sp_functions)
        return (v.get('h3_repeated_test.dup') or 0, v.get('h3_repeated_test.dup_cmp') or 0,
                sum(1 if v.get(k) is True else v.get(k) for k in sp_keys if isinstance(v.get(k), (int, float)) and v.get(k) > 0))

    def port_unread(d):
        """The labels of the port body that d closes with END that are unread (g3_unread on the INIT line), once a head is
        drawn for it (kept in picked); 0 where the body has no table."""
        f = d.fork()
        try:
            f.step(END)
            tb = parse_table(TA.export(f, task, case, before))
        except Exception:  # noqa: BLE001
            return 0
        head = []
        for col, _ in port['head']:
            cand = head_cands(tb, port['ctypes'].get(col))
            if not cand:
                return 0
            head.append((col, tb['labels'][rng.choice(cand)]))
        picked[:] = head
        return clause_value(port_text(f.program_form().split('\n')[base_forms], head), 'g3_unread.unread') or 0

    def evaluate(cur, toks, atoms_text, lg, prefix, is_gold, extra):
        rec = dict(task=task, case=case, point=point, draw=len(rows), gold=is_gold, atoms=atoms_text, n_atoms=len(atoms_text),
                   logq=lg.q, logp=lg.p, logq_full=lg.q + lg.x, fail=None, **extra)
        f = cur.fork()
        try:
            f.step(END)
        except arclog.Refusal as e:
            rec['fail'] = 'end refused: %s' % e
            return rec
        header = None
        try:  # X from the table of the clause's relation at its END: it holds the labels an OR or IF exports
            tb, err = parse_table(TA.export(f, task, case, before)), None
        except M.Fail as e:
            tb, err = None, str(e)
            header = getattr(e, 'header', None)
        except (Exception, BaseException) as e:  # noqa: BLE001
            if isinstance(e, (KeyboardInterrupt, SystemExit)):
                raise
            tb, err = None, '%s: %s' % (type(e).__name__, e)
        if port and tb is not None:
            pf = f.program_form()
            got, perr = port_x(tb, pf.split('\n')[base_forms], is_gold)
            if got is None:
                rec['fail'] = 'port: ' + perr
                return rec
            rec['body_x'] = summary(tb)
            tb, rec['port_clause'], rec['port_head'] = got
        rec['x'] = summary(tb)
        rec['x_err'] = err
        rec['_x_table'] = tb
        rec['x_rows'] = rows_with_models(tb, None if is_gold else X_ROWS_CAP) if tb else None
        if tb is None and header is not None:  # a Count entry: X's header with no rows (x_rows []), and x_err says why
            rec['x'] = dict(header, entries=None, empty_all=None, empty_inputs=None)
            rec['x_rows'] = []
        sums = [summary(t) or {} for t in prefix]
        rec['prefix_empty'] = [x.get('empty_all') for x in sums]
        rec['prefix_rows'] = [x.get('entries') for x in sums]  # per atom: [kind, index, row count] per entry of its prefix's table
        pf = f.program_form()
        rec['clause'] = pf.split('\n')[base_forms] if base_forms < n_forms(pf) else None
        if 'port_clause' in rec:
            rec['rule_clause'], rec['clause'] = rec['clause'], rec.pop('port_clause')
        rec['own_depth'] = strata.point_fields(strata.sexprs('\n'.join(pf.split('\n')[:base_forms] + [rec['clause']])), base_forms)['depth'] if rec['clause'] else None
        rec['stream'] = toks + [END]
        js, perr = static_prune(pf, base_forms, st)
        rec['static'] = js
        rec['static_err'] = perr
        return rec

    def cut_rows(toks, cuts, text, prefix, safe, is_gold, draw):
        """The clause of a draw cut after each atom k before its last where it can end, evaluated as a draw is: rows
        with prefix_of (the draw) and prefix_k (k)."""
        out = []
        for k in range(1, len(cuts)):
            if not safe[k - 1]:
                continue
            f = dec.fork()
            for t in toks[:cuts[k - 1]]:
                f.step(t)
            r = evaluate(f, toks[:cuts[k - 1]], text[:k], Logs(), prefix[:k], is_gold, dict(prefix_of=draw, prefix_k=k))
            r.pop('_x_table', None)
            r['draw'] = draw * 1000 + k  # unique at the point
            out.append(r)
        return out

    prefix_rows = []
    rel_rows = []
    choice_rows = []
    valcut_rows, prefcut_rows = [], []
    cutopt_rows, cut_info = [], dict(truncated=False, c0=time.process_time())
    # gold first, through the same evaluation
    cur = dec.fork()
    gtoks, gtext, gprefix, gsafe = [], [], [], []
    try:
        for a in gold_atoms:
            for x in a:
                cur.step(x)
            gtoks += a
            gtext.append(' '.join(V.name(x) for x in a))
            tb, _ = body_table(dr.frontier(cur), task, case, cur, before)
            gprefix.append(tb)
            gsafe.append(can_end(cur))
        rows.append(evaluate(cur, gtoks, gtext, Logs(), gprefix, True, dict(prefix_safe=gsafe)))
        if PREFIX_DRAWS:
            prefix_rows += cut_rows(gtoks, list(itertools.accumulate(len(a) for a in gold_atoms)), gtext, gprefix, gsafe, True, 0)
        rows[0].update(logp=None, logq_full=None)  # score_gold gives them
    except Exception as e:  # noqa: BLE001
        rows.append(dict(task=task, case=case, point=point, draw=0, gold=True, logp=None, logq_full=None,
                         fail='gold: %s: %s' % (type(e).__name__, e)))
    head = re.match(r'\(RULE (&r\d+)', rows[0].get('clause') or '')
    pg = spec.get('point_group')  # the point's fields, where the point came from pick_groups: it tells whether OUT reads the clause
    pkind = pg.get('kind') if isinstance(pg, dict) else None
    out_reads = pg['output'] if isinstance(pg, dict) and 'output' in pg else head is not None and names.get(head[1]) == '&output'
    is_output = OUTPUT_GATE and out_reads
    if is_output:
        dr.need_boost, dr.want_boost = NEED_BOOST_OUT, WANT_BOOST_OUT

    def need_at(scope):
        """The column types to favour at an atom start after a prefix whose table has the types scope."""
        return out_need(scope) if is_output else set().union(*[n for n in port_need if not n & set(scope)])
    cc = counts.get('compound') if COMPOUND else None
    if cc is not None:
        shapes = sorted((k[1], v) for k, v in cc.items() if k[0] == 'shape' and v > 0)
        blen = collections.Counter({k[1]: v for k, v in cc.items() if k[0] == 'blen' and v > 0})
        bhazard = {j: (blen[j] + 0.5) / (sum(v for n, v in blen.items() if n >= j) + 1.0) for j in range(1, MAX_BRANCH + 1)}
        p_neg1 = (cc[('neg1',)] + 0.5) / (cc[('later',)] + 1.0)

    def fresh_types(atom_toks, nlab0):
        """{label number: type} of the labels an atom's tokens make, numbered from nlab0: the column type from the
        decoder's column positions for a declared relation (column_positions) and from featlib for a lib, macro or
        fact relation, else None."""
        if not atom_toks or atom_toks[0] == M.NOT or atom_toks[0] in M.CMP:
            return {}
        rel = atom_toks[0]
        ts = None if V.kind(rel) == 'relation' else regtypes.get(V.name(rel))
        cols = colmap.get(M.slot_no(V.name(rel)), {}) if V.kind(rel) == 'relation' else None
        out, i, j = {}, nlab0, 1
        while j + 1 < len(atom_toks):
            c_, v_ = atom_toks[j], atom_toks[j + 1]
            if V.kind(v_) == 'column':  # a record site: field and value pairs until END
                p_ = dr.fr.colpos.get(c_)
                j += 1
                while j + 1 < len(atom_toks) and atom_toks[j] != END:
                    if atom_toks[j + 1] == M.STAR:
                        f_ = dr.fr.colpos.get(atom_toks[j])
                        out[i] = column_type(ts, cols, p_, f_) if p_ is not None and f_ is not None else None
                        i += 1
                    j += 2
                j += 1
                continue
            if v_ == M.STAR:
                p_ = dr.fr.colpos.get(c_)
                out[i] = column_type(ts, cols, p_) if p_ is not None else None
                i += 1
            j += 2
        return out

    def negation_of(d, atom_toks, local):
        """(decoder, tokens, text) of NOT of a first-branch atom at d, keeping the sites that read a label from outside
        the branch (or 0) and dropping the rest; None where the atom has a record site, no site is kept, or the decoder
        refuses."""
        rel, rest = atom_toks[0], atom_toks[1:]
        if V.kind(rel) not in ('relation', 'lib relation', 'relation macro', 'fact relation') or len(rest) % 2:
            return None
        keep = []
        for c_, v_ in zip(rest[::2], rest[1::2]):
            if V.kind(c_) != 'column' or V.kind(v_) == 'column':
                return None
            if v_ == M.ZERO or (V.kind(v_) == 'label' and int(V.name(v_)[1:]) not in local):
                keep += [c_, v_]
        if not keep:
            return None
        out = [M.NOT, rel] + keep
        f = d.fork()
        try:
            for t_ in out:
                f.step(t_)
        except arclog.Refusal:
            return None
        if not part_can_close(f):
            return None
        sites = ' '.join('(%s %s)' % (V.name(c_), V.name(v_)) for c_, v_ in zip(keep[::2], keep[1::2]))
        return f, out, '(NOT (%s %s))' % (V.name(rel), sites)

    def p_comp(k):
        return (cc[('comp', is_output, k)] + 0.1) / (cc[('reach', is_output, k)] + 1.0)

    def part_can_close(d):
        for t in (ALSO_TOK, END):
            try:
                d.forced(t)
                return True
            except arclog.Refusal:
                pass
        return False

    def draw_compound(cur, toks, text, scope, k, dtries, ltypes, pre=None):
        """A final OR after k - 1 atoms (texts in text): (decoder, tokens, text, Logs) or (None, reason). Each branch's
        atoms come from the atom grammar, and a branch may stop only where it can close. A branch atom that repeats an atom
        of text or of its own branch is redrawn. The labels that the first branch makes and does not read again are
        exported, and so is each label that it reads again with probability P_REEXPORT, or with probability 1 where the
        output clause needs its type (a Position or Box, or a Color, that is not in scope and that no unread label has). A
        later branch favours at its sites the exported labels and the labels it made and has not read, and closes where it
        binds every exported label and reads every label it makes; its relation choice favours relations that can join
        their types. Where the hazard ends a later branch
        that breaks one of those two rules, it closes anyway with probability P_UNNAMED (it binds not every exported label;
        never at the output clause) or P_UNREAD_LOCAL (it makes a label it does not read), and the labels it does not bind
        are no longer exported. A later branch that cannot close is drawn again from its start, up to BRANCH_TRIES times. At
        the output clause, the first branch may stop only where the prefix's types and the types of all the labels it makes
        hold a Position or a Box, and a Color. The engine gives no table inside a branch, so a branch's rows are not
        tested. The shape, the negation draws, the stops of a branch and the re-export draws have the same rate in P and in q,
        so Logs.both adds them; a branch that stops with one rule broken counts the P_UNNAMED or P_UNREAD_LOCAL draw in both
        (as q's chance to stop), and a branch that goes on counts q's chance to go on, whether the hazard or that draw
        said so. A redrawn branch drops the factors of its failed tries.
        With pre (gold_q's estimate of the chance that a try of a later branch fails), the draw resumes at branch pre['b'], from
        the state pre holds (d, ctoks, exported, first, first_made, dup_base, nparts), makes one try of it and returns after it:
        (None, reason) where the try fails, else the usual result with the parts of that branch only."""
        if pre is None:
            ors = [(x, v) for x, v in shapes if x.startswith('OR')]
            shape, q = dr.pick([x for x, _ in ors], [v for _, v in ors])
            kind, nparts = shape[:2], int(shape[2:])
            d = cur.fork()
            head = M.OR if kind == 'OR' else IF_TOK
            d.step(head)
            ctoks, parts, clg = [head], [], Logs(math.log(q), math.log(q))
            exported, first = None, []
            dup_base = (0, 0, 0)  # repeats and SP keys in the clause so far: the atoms drawn before are free of them, the negation of an else branch may not be
            b0 = 0
        else:
            b0, kind, nparts, d, ctoks, parts, clg = pre['b'], 'OR', pre['nparts'], pre['d'], list(pre['ctoks']), [], Logs()
            exported, first, first_made, dup_base = set(pre['exported']), [list(x) for x in pre['first']], set(pre['first_made']), pre['dup_base']
        for b in range(b0, nparts):
            d0, n0, clg0, lt0, dup0, x0 = d, len(ctoks), clg.copy(), dict(ltypes), dup_base, list(xacc)
            n_ok, snap = 0, None
            for attempt in range((BRANCH_N if EXACT else BRANCH_TRIES) if b and pre is None else 1):
                if attempt:  # a later branch that could not close, again from its start; the failed atoms' log q is dropped
                    dtries['part retry'] += 1
                    d, clg, dup_base = d0, clg0.copy(), dup0
                    del ctoks[n0:]
                    ltypes.clear()
                    ltypes.update(lt0)
                    xacc[:] = x0
                ptext, bound, made, read, closed, err = [], set(), [], collections.Counter(), b == 0, None
                j0 = 1
                neg = False
                if b > 0 and first and rng.random() < p_neg1:  # the else branch: NOT of a first-branch atom
                    got_n = negation_of(d, first[int(rng.random() * len(first))], first_made)
                    if got_n is not None:
                        neg = True
                        d, ntoks, ntext = got_n
                        ctoks += ntoks
                        ptext.append(ntext)
                        read.update(int(x) for x in re.findall(r'(?<![*\w])L(\d+)', ntext))
                        dtries['else negation'] += 1
                        j0 = 2
                        pf = closed_program(d, 2)
                        if pf is not None:
                            dup_base = dup_count(pf)
                if b > 0 and first:  # a negation that the decoder refuses counts as a branch with no negation
                    clg.both(math.log(p_neg1 / len(first)) if neg else math.log1p(-p_neg1))
                for j in range(j0, MAX_BRANCH + 1):
                    if b == 0 and is_output:
                        dr.need = out_need(set(scope) | {ltypes.get(x) for x in made})
                    wanted = exported - bound if exported else set()
                    if b > 0:  # and the labels the branch made and has not read
                        wanted |= {x for x in made if not read[x]}
                    dr.want = {dr.fr.label_tok[i] for i in wanted if i in dr.fr.label_tok}
                    wtypes = [ltypes[i] for i in wanted if ltypes.get(i)]
                    dr.want_types = frozenset(wtypes)
                    nlab0 = (toks + ctoks).count(M.STAR)
                    fr = dr.frontier(d, nlab0)
                    got, free = None, 0
                    dr.deltas.clear()
                    for n_try in range(0 if EXACT else ATOM_TRIES + CHEAP_TRIES):
                        if n_try - free >= ATOM_TRIES:
                            break
                        dr.p_k, dr.p_scope, dr.p_key, dr.p_last = k - 1 + j, tuple(scope), tuple(toks + ctoks), ()
                        res, why = dr.atom(fr, max(k - 1 + j, 2) if wtypes else k - 1 + j, wtypes or scope, tuple(toks + ctoks))
                        if res is None:
                            dtries['part construct:' + re.sub(r'refused .*', 'refused', why)] += 1
                            continue
                        if not part_can_close(res[0].dec):
                            dtries['part unsafe'] += 1
                            continue
                        if k - 1 + j > 1 and not res[4] and res[5]:
                            dtries['part unjoined'] += 1
                            free += 1
                            continue
                        pf = closed_program(res[0].dec, 2)
                        if pf is None:
                            dtries['part repeat untested'] += 1
                        elif sum(dups := dup_count(pf)) > sum(dup_base):
                            dtries['prefix key' if dups[2] > dup_base[2] else 'repeat'] += 1
                            if dups[2] <= dup_base[2] and dups[0] <= dup_base[0]:
                                dtries['repeat via dup_cmp'] += 1
                            free += 1
                            continue
                        if STATIC_ATOM and b == nparts - 1 and static_hit(pf, [base_forms, 0, len(text), b, len(ptext)]):
                            dtries['part static'] += 1
                            continue
                        got = res
                        break
                    if EXACT:
                        def draw_part():
                            dr.p_k, dr.p_scope, dr.p_key, dr.p_last = k - 1 + j, tuple(scope), tuple(toks + ctoks), ()
                            res, why = dr.atom(fr, max(k - 1 + j, 2) if wtypes else k - 1 + j, wtypes or scope, tuple(toks + ctoks))
                            return [res, why, None]  # the closed program is set by cheap_part

                        def cheap_part(c):
                            res = c[0]
                            if res is None:  # a draw that cannot be built has no atom for these checks: it fails the expensive stage
                                return True
                            if k - 1 + j > 1 and not res[4] and res[5]:
                                dtries['part unjoined'] += 1
                                return False
                            c[2] = pf = closed_program(res[0].dec, 2)
                            if pf is None:
                                dtries['part repeat untested'] += 1
                            elif sum(dups := dup_count(pf)) > sum(dup_base):
                                dtries['prefix key' if dups[2] > dup_base[2] else 'repeat'] += 1
                                if dups[2] <= dup_base[2] and dups[0] <= dup_base[0]:
                                    dtries['repeat via dup_cmp'] += 1
                                return False
                            return True

                        def costly_part(c):
                            res, why, pf = c
                            if res is None:
                                dtries['part construct:' + re.sub(r'refused .*', 'refused', why)] += 1
                                return None
                            if not part_can_close(res[0].dec):
                                dtries['part unsafe'] += 1
                                return None
                            if STATIC_ATOM and b == nparts - 1 and static_hit(pf, [base_forms, 0, len(text), b, len(ptext)]):
                                dtries['part static'] += 1
                                return None
                            return res
                        got, la = exact_two_stage(EXACT_N1, EXACT_N2, draw_part, cheap_part, costly_part, dtries)
                        if got is not None:
                            clg.x -= la
                            xacc[0] -= la
                            xacc[1] += 1
                    if got is None:
                        err = 'part %d atom %d: no atom in %d tries' % (b + 1, j, ATOM_TRIES)
                        break
                    if EXACT_COIN:
                        xacc[2] += dr.deltas.get(id(got), (0.0,))[0]
                    node, alq, _, atext, _, _, alp = got
                    d = node.dec
                    ltypes.update(fresh_types(list(node.toks), nlab0))
                    ctoks += list(node.toks)
                    ptext.append(atext)
                    clg.q += alq
                    clg.p += alp
                    fresh = [int(x) for x in re.findall(r'\*L(\d+)', atext)]
                    joins = [int(x) for x in re.findall(r'(?<![*\w])L(\d+)', atext)]
                    made += fresh
                    read.update(joins)
                    if b == 0 and not atext.startswith('(NOT'):
                        first.append(list(node.toks))
                    bound |= set(fresh) | (set(joins) & (exported or set()))
                    soft = None  # (rule, probability) where one rule alone holds the branch open
                    if b == 0:
                        closed = not is_output or not out_need(set(scope) | {ltypes.get(x) for x in made})
                    else:
                        named, local = exported <= bound, all(read[x] for x in made)
                        closed = named and local
                        if named != local:
                            soft = ('unread', P_UNREAD_LOCAL) if named else None if is_output else ('unnamed', P_UNNAMED)
                    if closed or soft:
                        h, s = bhazard.get(j, 1.0), 1.0 if closed else soft[1]  # s: the chance that the branch may close at a stop
                        if rng.random() < h and (closed or rng.random() < soft[1]):
                            clg.both(math.log(h * s))
                            if not closed:
                                dtries['soft close ' + soft[0]] += 1
                                closed = True
                            break
                        clg.p += math.log1p(-h)
                        clg.x += math.log1p(-h * s)
                    elif BRANCH_GATE_P:  # the stop is refused, so q goes on with probability 1 and P's chance to go on is 1 - h
                        clg.p += math.log1p(-bhazard.get(j, 1.0))
                dr.want = set()
                dr.want_types = frozenset()
                dr.need = set()
                if err is None and not closed:
                    err = ('part 1 exports no Position and Color' if b == 0 else
                           'part %d binds not every exported label' % (b + 1) if not exported <= bound else
                           'part %d leaves a label it makes unread' % (b + 1))
                if err is None:
                    if not EXACT:
                        break
                    n_ok += 1  # EXACT: all of the branch draws are made; the first that closes is picked
                    if snap is None:
                        snap = (d, clg, dup_base, ctoks[n0:], dict(ltypes), ptext, bound, made, read, closed, list(xacc))
            if EXACT and b:
                if snap is None:
                    xacc[:] = x0
                else:
                    d, clg, dup_base, tail, lt_, ptext, bound, made, read, closed, xs = snap
                    del ctoks[n0:]
                    ctoks += tail
                    ltypes.clear()
                    ltypes.update(lt_)
                    xacc[:] = xs
                    err = None
                    la = math.log(n_ok / BRANCH_N)
                    clg.x -= la
                    xacc[0] -= la
                    xacc[1] += 1
            if err:
                if ' no atom in ' in err:  # no atom could be drawn at the site (ATOM_TRIES)
                    dtries['cfail p%d no atom at atom %d' % (b + 1, j)] += 1
                elif err.startswith('part %d ' % (b + 1)):  # the branch used its MAX_BRANCH atoms and could not close: which rule broke, by how much
                    dtries['cfail p%d cap %s' % (b + 1, 'miss ' + '+'.join(sorted(out_need(set(scope) | {ltypes.get(x) for x in made})))
                                                 if b == 0 else 'unbound %d unread %d' % (len(exported - bound), sum(1 for x in made if not read[x])))] += 1
                return None, err
            if b == 0:
                exported = {x for x in made if not read[x]}
                for x in made:  # a label that the branch reads again is exported at random, or forced where the output clause needs its type
                    if read[x]:
                        if rng.random() < P_REEXPORT:
                            exported.add(x)
                            clg.both(math.log(P_REEXPORT))
                        else:
                            clg.both(math.log1p(-P_REEXPORT))
                have = set(scope) | {ltypes.get(x) for x in exported}
                for x in made:
                    if is_output and read[x] and ltypes.get(x) in out_need(have):
                        exported.add(x)
                        have.add(ltypes.get(x))
                        dtries['forced export'] += 1
                first_made = set(made)
            else:
                exported &= bound
            sep = END if (kind == 'IF' or b == nparts - 1) else ALSO_TOK
            try:
                d.step(sep)
            except arclog.Refusal:
                return None, 'part %d cannot close' % (b + 1)
            ctoks.append(sep)
            parts.append(ptext)
            if pre is not None:
                break
        return (d, ctoks, '(%s %s)' % (kind, ' '.join('(%s)' % ' '.join(p) for p in parts)), clg), None

    def fresh_atom(fr, o, cap=200):
        return complete_atom(fr, fr.child(fr.root, o), cap)

    def complete_atom(fr, start, cap=200):
        """The frontier node of relation option o's atom with every column named, each given a fresh label where the decoder
        takes one, else (an unbounded column) the newest label in scope, else 0, else its record's fields; found depth
        first over those choices, with at most cap nodes; None where no such atom closes."""
        budget = [cap]

        def prefer(n, opts):
            if n.phase == 'cols':
                return opts[:1] + ([None] if fr.is_leaf(n) else [])  # name the next column; stop only at the last
            if n.phase in ('val', 'fval'):
                labs = sorted((x for x in opts if fr.KIND[x] == 'label'), key=lambda t: -int(V.name(t)[1:]))
                return ([M.STAR] if M.STAR in opts else []) + labs + ([M.ZERO] if M.ZERO in opts else []) + \
                    [x for x in opts if fr.KIND[x] == 'column']
            if n.phase == 'fcol':
                return [x for x in opts if x != M.END][:1] + ([M.END] if M.END in opts else [])
            return []

        def dfs(n):
            if n is None or budget[0] <= 0:
                return None
            budget[0] -= 1
            if n.phase == 'done':
                return n
            opts = fr.options(n)
            if n.phase == 'cols' and not opts:
                return n if fr.is_leaf(n) else None
            for t in prefer(n, opts):
                if t is None:
                    return n
                got = dfs(fr.child(n, t))
                if got is not None:
                    return got
            return None
        return dfs(start)

    def cut_eval(fr, n, base):
        """A cut row: base with the clause closed after frontier node n's atom, evaluated as a cut row is."""
        if n is None:
            return dict(base, fail='no fresh atom')
        pf = closed_program(n.dec, 1)
        if pf is None:
            return dict(base, fail='cannot end')
        try:
            tb = body_table(fr, task, case, n.dec, before)[0]
        except Exception as e:  # noqa: BLE001
            return dict(base, fail='table: %s: %s' % (type(e).__name__, str(e)[:120]))
        return dict(base, atom=fr.render(n), clause=pf.split('\n')[base_forms], x=summary(tb),
                    x_rows=rows_with_models(tb, X_ROWS_CAP) if tb else None)

    def prefix_cut(k, d):
        """A PREFIX_CUTS row: gold's clause cut before its atom k (decoder d after its first k - 1 atoms)."""
        base = dict(task=task, case=case, point=point, point_group=spec.get('point_group'), k=k, tok=None, gold=True, fail=None)
        if k == 1:
            return dict(base, fail='empty prefix')
        pf = closed_program(d, 1)
        if pf is None:
            return dict(base, fail='cannot end')
        tb = gprefix[k - 2]
        return dict(base, clause=pf.split('\n')[base_forms], x=summary(tb), x_rows=rows_with_models(tb, X_ROWS_CAP) if tb else None)

    def value_cuts(k, fr, n, popts, gold_tok):
        """VAL_CUTS rows at a value pick of gold (node n): each option's atom completed and evaluated."""
        if cut_info['truncated']:
            return
        for o in popts:
            if time.process_time() - cut_info['c0'] > CUT_OPTS_SECONDS:
                cut_info['truncated'] = True
                return
            base = dict(task=task, case=case, point=point, point_group=spec.get('point_group'), k=k, phase=n.phase,
                        text=n.text, tok=V.name(o), gold=V.name(o) == gold_tok, fail=None)
            valcut_rows.append(cut_eval(fr, complete_atom(fr, fr.child(n, o)), base))

    def option_cuts(fr, gtoks, k, gold_tok, c0):
        """CUT_OPTS rows at an atom start of gold: each lib or derived option's one-atom cut, evaluated as a cut row."""
        out = []
        opts = fr.options(fr.root)
        if CUT_OPTS_TOP > 0:
            ws = dr.weights(fr.root, opts, None, False, False, False)
            opts = [o for _, i, o in sorted(((-w, i, o) for i, (o, w) in enumerate(zip(opts, ws))))[:CUT_OPTS_TOP]]
        for o in opts:
            if o == M.NOT or o in M.CMP:
                continue
            if time.process_time() - c0 > CUT_OPTS_SECONDS:
                return out, True
            base = dict(task=task, case=case, point=point, point_group=spec.get('point_group'), k=k, tok=V.name(o),
                        name=dr.prog_names.get(V.name(o), V.name(o)), gold=V.name(o) == gold_tok, fail=None)
            n = fresh_atom(fr, o)
            if n is None:
                out.append(dict(base, fail='no fresh atom'))
                continue
            pf = closed_program(n.dec, 1)
            if pf is None:
                out.append(dict(base, fail='cannot end'))
                continue
            try:
                tb = body_table(fr, task, case, n.dec, before)[0]
            except Exception as e:  # noqa: BLE001
                out.append(dict(base, fail='table: %s: %s' % (type(e).__name__, str(e)[:120])))
                continue
            out.append(dict(base, atom=fr.render(n), clause=pf.split('\n')[base_forms], x=summary(tb),
                            x_rows=rows_with_models(tb, X_ROWS_CAP) if tb else None))
        return out, False

    order_no, order_clause = None, None  # the order that score_gold is on (ROW_ORDERS), and its closed clause; None: the written order

    def order_rng():
        """The rng of a clause's orders, seeded by the task and the clause's atoms as a set."""
        return random.Random(M.seed_of(task, sorted(x.replace('*', '') for x in body_atoms(rows[0]['clause'])), 'orders'))

    def order_state(atoms, tables):
        """An order's {atoms, prefix, safe, clause, same}, with atoms as reorder gives them; None where the decoder refuses them. With
        tables, also its prefix tables, and same: whether the clause's table at END has gold's rows (an order keeps the clause's rows)."""
        d = dec.fork()
        try:
            for x in itertools.chain(*atoms):
                d.step(x)
            d.step(END)
        except arclog.Refusal:
            return None
        st_ = dict(atoms=atoms, prefix=None, safe=None, clause=d.program_form().split('\n')[base_forms], same=None)
        if tables:
            cur_, st_['prefix'], st_['safe'] = dec.fork(), [], []
            for a in atoms:
                for x in a:
                    cur_.step(x)
                st_['prefix'].append(body_table(dr.frontier(cur_), task, case, cur_, before)[0])
                st_['safe'].append(can_end(cur_))
            gx_ = rows[0].get('body_x') or rows[0].get('x')
            try:
                st_['same'] = gx_ is None or (summary(parse_table(TA.export(d, task, case, before))) or {}).get('entries') == gx_['entries']
            except M.Fail:
                st_['same'] = False
        return st_

    def score_orders():
        """ROW_ORDERS: the rows of score_gold for ROW_ORDERS random valid orders of gold's clause. rows[0]['row_orders'] counts the orders
        tried and why each one left out was left out: the NOT and comparison rule, the decoder, a table, or score_gold."""
        nonlocal gold_atoms, gprefix, gsafe, order_no, order_clause
        if any(a[0] in (M.OR, IF_TOK) for a in gold_atoms):  # score_gold writes no rows for a compound
            return
        kept, sites = (gold_atoms, gprefix, gsafe), label_sites(V, gold_atoms)
        tally_ = rows[0]['row_orders'] = collections.Counter()
        tries_ = 0
        try:
            for o in random_orders(range(len(kept[0])), order_rng()):
                tries_ += 1
                atoms = reorder(kept[0], sites, o, dr.fr.label_tok)
                if atoms is None:
                    tally_['guard'] += 1
                    continue
                st_ = order_state(atoms, True)
                if st_ is None:
                    tally_['refused'] += 1
                elif not st_['same'] or any(t is None for t in st_['prefix']):
                    tally_['table'] += 1
                else:
                    gold_atoms, gprefix, gsafe, order_clause, order_no = atoms, st_['prefix'], st_['safe'], st_['clause'], tally_['kept']
                    if score_gold() is None:
                        tally_['unscored'] += 1
                    else:
                        tally_['kept'] += 1
                        if tally_['kept'] == ROW_ORDERS:
                            break
        finally:
            gold_atoms, gprefix, gsafe = kept
            order_no, order_clause = None, None
        tally_['tries'] = tries_
        rows[0]['row_orders'] = dict(tally_)

    def score_gold():
        """(log p, log q_full) of gold's path, with its atoms' tokens forced through atom (no rng call, no steering by
        unread labels, no must_join) and the stop after each atom; None where an atom is a compound, which is not scored.
        The caches that atom fills are put back, so the draws that follow are those of a run that does not score gold."""
        if any(a[0] in (M.OR, IF_TOK) for a in gold_atoms):
            return None
        saved = dict(dr.jcache), dict(dr.reach_cache), dr.lookahead_forks, dr.reach_drops, dr.complete_drops
        gcur, gt, lg = dec.fork(), [], Logs()
        dr.parts = parts = collections.Counter()
        rows_on = order_no is not None or not ROW_ORDERS  # with ROW_ORDERS the rows come from the orders alone
        dr.relrows = [] if REL_ROWS and rows_on else None
        dr.choices = [] if CHOICE_ROWS and rows_on else None
        dr.on_value = value_cuts if VAL_CUTS and order_no is None else None
        cut_info['c0'] = time.process_time()
        try:
            for k, a in enumerate(gold_atoms, 1):
                if cc is not None:
                    lg.both(math.log1p(-p_comp(k)))
                    parts['no compound'] += math.log1p(-p_comp(k))
                before = sum(v for x, v in parts.items() if not x.startswith('atom '))
                scope = [str(t) for t in gprefix[k - 2]['types']] if k > 1 and gprefix[k - 2] else ()
                dr.p_labels = gprefix[k - 2].get('labels') if k > 1 and gprefix[k - 2] else None
                fr = dr.frontier(gcur, gt.count(M.STAR))
                if PREFIX_CUTS and order_no is None:
                    prefcut_rows.append(prefix_cut(k, gcur))
                if k <= CUT_OPTS and not cut_info['truncated'] and order_no is None:
                    got, cut_info['truncated'] = option_cuts(fr, gt, k, V.name(a[1] if a[0] == M.NOT else a[0]), cut_info['c0'])
                    cutopt_rows.extend(got)
                dr.want, dr.need, dr.force = set(), need_at(scope), collections.deque(a)
                dr.p_k, dr.p_scope, dr.p_key, dr.p_last = k, tuple(scope), tuple(gt), tuple(gold_atoms[k - 2]) if k > 1 else ()
                res, why = dr.atom(fr, k, scope, tuple(gt))
                if res is None or dr.force:
                    return None
                gcur, gt = res[0].dec, gt + list(a)
                lg.q += res[1]
                lg.p += res[6]
                if gsafe[k - 1]:
                    h = 1.0 if k >= MAX_ATOMS else hazard.get(k, hazard[max(hazard)] if hazard else 1.0)  # past the table: its last stop rate
                    lg.both(math.log(h) if k == len(gold_atoms) else log0(1 - h))
                    parts['atom stop'] += math.log(h) if k == len(gold_atoms) else log0(1 - h)
                    if dr.choices is not None:
                        dr.choices.append(dr.stop_row(k, a, res[2], res[3], h, 'STOP' if k == len(gold_atoms) else 'GO', tuple(gt[:len(gt) - len(a)])))
                parts['atom %d' % min(k, 4)] += sum(v for x, v in parts.items() if not x.startswith('atom ')) - before
            if order_no is None:
                rows[0]['logp_parts'] = {x: round(v, 4) if math.isfinite(v) else None for x, v in parts.items()}  # None: P gives gold's pick 0
            gclause = order_clause or rows[0]['clause']
            if dr.relrows is not None:
                gb = body_atoms(gclause)
                try:  # DAG fields of each derived option: its base relation in the read graph of the forms before the point
                    dag, adj = dag_info(point_forms(spec), point[0])
                except Exception:
                    dag = None
                base_of = lambda tok: (dr.prog_names.get(tok) or '').split('.')[0] or None  # noqa: E731
                for r in dr.relrows:
                    r.update(task=task, case=case, point=point, point_group=spec.get('point_group'), clause=gclause,
                             prefix=gb[:r['k'] - 1], gold_atom=gb[r['k'] - 1] if r['k'] <= len(gb) else None)
                    if order_no is not None:
                        r['order'] = order_no
                    if dag is None:
                        continue
                    pre_bases = {b for a in gold_atoms[:r['k'] - 1] for t in a if (b := base_of(V.name(t)))}
                    r['prefix_bases'] = sorted(pre_bases)
                    r['prefix_depth'] = max([dag(b)['depth'] for b in pre_bases], default=0)
                    for o in r['options']:
                        b = base_of(o['tok']) if o['kind'] == 'derived' else None
                        if b:
                            o['dag'] = dict(dag(b), base=b, method=o.get('name', '') != b, sibling=b in pre_bases,
                                            path=dag_path(adj, pre_bases, b) if pre_bases else None)
                rel_rows.extend(dr.relrows)
            if dr.choices is not None:
                gb = body_atoms(gclause)
                scope_of = lambda k: (gprefix[k - 2] or {}) if k > 1 else {}  # noqa: E731
                for r in dr.choices:
                    after = r['phase'] == 'atom stop'  # the stop reads the clause with its atom
                    sc = scope_of(r['k'] + after)
                    r.update(task=task, case=case, point=point,
                             prefix=gb[:r['k'] - 1 + after], gold_atom=gb[r['k'] - 1] if r['k'] <= len(gb) else None,
                             scope_labels=sc.get('labels'), scope_types=[str(t) for t in sc.get('types') or []])
                    if order_no is not None:
                        r['order'] = order_no
                choice_rows.extend(dr.choices)
            return lg.p, lg.q + lg.x
        finally:
            dr.parts = dr.relrows = dr.choices = dr.on_value = None
            dr.want, dr.need, dr.force = set(), set(), None
            dr.want_types = frozenset()
            dr.jcache, dr.reach_cache, dr.lookahead_forks, dr.reach_drops, dr.complete_drops = saved

    if rows[0].get('clause'):
        try:
            rows[0]['logp'], rows[0]['logq_full'] = score_gold() or (None, None)
        except Exception as e:  # noqa: BLE001
            rows[0]['gold_score_error'] = '%s: %s' % (type(e).__name__, str(e)[:200])
        if ROW_ORDERS:
            try:
                score_orders()
            except Exception as e:  # noqa: BLE001
                rows[0]['row_orders_error'] = '%s: %s' % (type(e).__name__, str(e)[:200])
    gx = rows[0].pop('_x_table', None)
    if is_output and gx is not None:  # gold's X: the probe table of an OR or IF atom drops the labels it exports
        rows[0]['output_gate'] = stop_gate(rows[0], rows[0]['clause']) if rows[0].get('clause') else None

    empty_gate = EMPTY_ATOM and not (rows[0].get('x') or {}).get('empty_inputs')  # a guard clause (gold's X is empty on every input) may be empty
    gq_none = []  # why gold_q last returned None

    def gold_compound(k, a, gcur, gt, gtexts, scope, prev_need, part):
        """Log q of gold's compound atom a (the OR that is gold's atom k) under the proposal the draws use; -inf where the draws cannot
        make it (the reason is in part['comp']['zero']); Unscored where a step cannot be scored. The factors are in part['comp'].

        What a draw makes of a compound (the main loop and draw_compound), and what q takes for each decision:
        1. At atom site k it makes a compound with probability p_comp(k), else a plain atom (the caller counts 1 - p_comp for each site before k).
           Known: log p_comp(k). The clause ends after a compound (no stop factor), so a compound that gold's atoms follow, an IF (the shapes
           drawn are OR shapes) and COMPOUND=0 have q 0.
        2. It picks the shape OR<n> by the counts of the other tasks' golds. Known.
        3. Branch 0 is one try, branch b > 0 up to BRANCH_TRIES tries (BRANCH_N with EXACT). A try fails where no atom passes the checks in
           the tries or the branch uses its MAX_BRANCH atoms without a close. A failed try at branch 0 fails the draw, so it is no factor
           on a path that gold has. A failed try at branch b > 0 is drawn again from the branch's start, with the failed try's factors
           dropped. So q(branch b) = q(a try gives gold's branch) * (1 + f + ... + f^(T - 1)), T the number of tries and f the chance that a
           try fails. Estimated: f from GQ_BRANCH_N tries of the branch from its start (draw_compound with pre) on gold_q's rng.
        4. A try of branch b > 0 first draws the else negation with probability p_neg1 (it negates one of the first branch's atoms, picked
           uniformly), which is j = 1 of the branch; a negation the decoder refuses counts as none. Known, from the first branch's atoms. Gold's
           first atom can be that negation or an atom drawn by the grammar; q sums both routes, which differ in what the branch has bound
           (the negation binds nothing) and so in the branch's later factors. A branch that is its negation alone is not drawn (the
           stop is first asked after j = 2).
        5. Each atom j of a try comes from the atom grammar (Drawer.atom with the branch's want, want_types and need, so with the tilt and the
           STEER_REL and STEER_CHOICE steers); the draw redraws it until it passes the construct, can-close, unjoined, repeat and (last
           branch) static checks. Known: the forced atom's q (the coin mixture, as for a plain atom). Estimated: log A^, the acceptance, by the
           two stages of gold_q on its rng, with the branch's checks. An atom that fails them has q 0.
        6. After atom j the branch stops with probability hazard(j) * s, where s is 1 if it can close (first branch: the output clause's
           missing types are in; later: it binds every exported label and reads every label it made), P_UNNAMED or P_UNREAD_LOCAL if one
           of the two rules is broken (never P_UNNAMED at the output clause), else 0 (the stop is refused and q goes on with probability
           1). Known: gold stops where its branch ends and goes on elsewhere; q 0 where the stop is refused. At j = MAX_BRANCH a branch
           that can close ends either way, so its factor is 1.
        7. After branch 0 each label it made and read again is exported with probability P_REEXPORT, and (output clause) a label whose type
           the clause needs is exported anyway; the labels it made and did not read are exported. Gold's tokens do not say which labels
           were exported, and the later branches' want, closing rules and stops depend on it, so q sums over the sets (grouped by the
           exported set that the rule gives): known weights, one replay of the later branches for each set. The set shrinks to the
           labels a later branch binds.
        8. A separator (ALSO, END) closes a branch; the decoder may refuse it (q 0).
        9. The compound is dropped, and the draw makes a plain atom, where at an INIT port no atom reads a derived relation (known from
           gold's atoms) or the port body leaves more than MAX_UNREAD labels unread (port_unread picks the head at random: its pass rate
           over 8 picks). A draw whose final clause cannot end fails; gold's can.
        Not counted: EXACT's A^ of a plain atom is the same estimate as without EXACT."""
        comp = part['comp'] = {}
        rd = lambda v: round(v, 4) if isinstance(v, float) and math.isfinite(v) else None if isinstance(v, float) else v  # noqa: E731
        steps = comp['steps'] = []

        def zero(why):
            comp['zero'] = why
            return -math.inf
        if cc is None:
            return zero('COMPOUND=0: the draws make no compound')
        if k < len(gold_atoms):
            return zero('atoms follow the compound: the draws end at a compound')
        if a[0] != M.OR:
            return zero('IF: the draws make OR shapes only')
        rng.seed(M.seed_of(task, case, seed_point, SEED_TAG + '/goldq/comp'))  # gold_q puts rng back
        sink = collections.Counter()
        dr.gq, dr.force = False, None
        # Pass 1: gold's atoms of each branch, split by the grammar (the forced atom stops where its tokens end) and the separators.
        d_head = gcur.fork()
        d_head.step(a[0])
        d = d_head.fork()
        rest, ctoks, gparts, gtext_parts, seps = collections.deque(a[1:]), [a[0]], [[]], [[]], []
        while True:
            if not rest:
                raise Unscored('compound has no atom in a branch')
            if rest[0] in (M.OR, IF_TOK):
                return zero('a compound in a branch: the draws make atoms there')
            n0, kk = len(rest), k + len(gparts[-1])
            dr.p_k, dr.p_scope, dr.p_key, dr.p_last = kk, tuple(scope), tuple(gt + ctoks), ()
            dr.force = rest
            res, why = dr.atom(dr.frontier(d, (gt + ctoks).count(M.STAR)), kk, scope, tuple(gt + ctoks))
            dr.force = None
            if res is None:
                raise Unscored('compound branch %d atom %d: forced atom failed: %s' % (len(gparts), len(gparts[-1]) + 1, why))
            gparts[-1].append(list(a[len(a) - n0:len(a) - len(rest)]))
            gtext_parts[-1].append(res[3])
            d, ctoks = res[0].dec, ctoks + gparts[-1][-1]
            if not rest:
                raise Unscored('compound ends inside a branch')
            if rest[0] not in (ALSO_TOK, END):
                continue
            seps.append(rest.popleft())
            d = d.fork()
            try:
                d.step(seps[-1])
            except arclog.Refusal:
                return zero('the separator of branch %d is refused' % len(gparts))
            ctoks.append(seps[-1])
            if not rest:
                break
            if seps[-1] == END:
                raise Unscored('tokens after the compound\'s END')
            gparts.append([])
            gtext_parts.append([])
        if seps[-1] != END:
            raise Unscored('compound has no final END')
        nparts, shape = len(gparts), 'OR%d' % len(gparts)
        if max(len(p) for p in gparts) > MAX_BRANCH:
            return zero('a branch of more than MAX_BRANCH atoms')
        ors = [(x, v) for x, v in shapes if x.startswith('OR')]
        if shape not in dict(ors):
            return zero('shape %s has no count' % shape)
        lpc, lshape, lgate = math.log(p_comp(k)), math.log(dict(ors)[shape] / sum(v for _, v in ors)), 0.0
        ctext = '(OR %s)' % ' '.join('(%s)' % ' '.join(p) for p in gtext_parts)
        if group in DERIVED_GROUPS and not reads_derived(gtexts + [ctext]):
            return zero('gate: no derived read')
        if group == 'INIT port':
            ok_ = sum(port_unread(d) <= MAX_UNREAD for _ in range(8))
            if not ok_:
                return zero('gate: port unread')
            lgate = math.log(ok_ / 8)
        comp.update(shape=shape, atoms=[len(p) for p in gparts], lq_pc=rd(lpc), lq_shape=rd(lshape), lq_gate=rd(lgate))
        acc, flt = {}, {}  # acceptance and try-failure estimates, by site and by branch start (hypotheses share them)
        T = BRANCH_N if EXACT else BRANCH_TRIES

        def fail_rate(b, st):
            """f: the share of GQ_BRANCH_N tries of branch b from state st that fail, drawn as the draws draw them."""
            fk = (b, st['exported'], st['dup_base'], tuple(st['ctoks']))
            if fk not in flt:
                n_fail = 0
                for _ in range(GQ_BRANCH_N):
                    dr.need = set(st['need'])
                    got_, _ = draw_compound(None, gt, gtexts, scope, k, sink, dict(st['ltypes']), dict(
                        b=b, nparts=nparts, d=st['d'], ctoks=st['ctoks'], exported=st['exported'], first=st['first'],
                        first_made=st['first_made'], dup_base=st['dup_base']))
                    n_fail += got_ is None
                flt[fk] = n_fail / GQ_BRANCH_N
            return flt[fk]

        def run_branch(b, st, hi):
            """[outcome per route] of branch b from state st: log q of a try that gives gold's branch, with its bookkeeping."""
            gatoms, exported = gparts[b], st['exported']
            routes = [(0.0, st['d'], [], [], collections.Counter(), 0, st['dup_base'])]  # log weight, decoder, tokens, texts, reads, atoms done, dup_base
            if b > 0 and st['first']:
                negs = [negation_of(st['d'], f_, st['first_made']) for f_ in st['first']]
                hit = [n_ for n_ in negs if n_ is not None and n_[1] == gatoms[0]]
                refused = sum(n_ is None for n_ in negs)
                routes[0] = (math.log(1 - p_neg1 + p_neg1 * refused / len(negs)),) + routes[0][1:]
                if hit and len(gatoms) > 1:
                    d_n, ntoks, ntext = hit[0]
                    pf_ = closed_program(d_n, 2)
                    routes.append((math.log(p_neg1 * len(hit) / len(negs)), d_n, ntoks, [ntext],
                                   collections.Counter(int(x) for x in re.findall(r'(?<![*\w])L(\d+)', ntext)), 1,
                                   dup_count(pf_) if pf_ is not None else st['dup_base']))
            outs = []
            for ri, (lw, d, ntoks, ptext, read, done, dup_base) in enumerate(routes):
                ctoks_, ltypes, bound, made, first_, ptext = st['ctoks'] + ntoks, dict(st['ltypes']), set(), [], [list(x) for x in st['first']], list(ptext)
                steps.append(dict(h=hi, b=b, route='neg' if ri else 'free', lq_route=rd(lw)))
                for j in range(done + 1, len(gatoms) + 1):
                    if b == 0 and is_output:
                        dr.need = out_need(set(scope) | {ltypes.get(x) for x in made})
                    wanted = exported - bound if exported else set()
                    if b > 0:
                        wanted |= {x for x in made if not read[x]}
                    dr.want = {dr.fr.label_tok[i] for i in wanted if i in dr.fr.label_tok}
                    wtypes = [ltypes[i] for i in wanted if ltypes.get(i)]
                    dr.want_types = frozenset(wtypes)
                    nlab0 = (gt + ctoks_).count(M.STAR)
                    key, kk = tuple(gt + ctoks_), k - 1 + j
                    ka, sc = (max(kk, 2) if wtypes else kk), (wtypes or scope)
                    fr = dr.frontier(d, nlab0)
                    dr.p_k, dr.p_scope, dr.p_key, dr.p_last = kk, tuple(scope), key, ()
                    dr.force, dr.gq, dr.gq_rel = collections.deque(gatoms[j - 1]), True, []
                    res, why = dr.atom(fr, ka, sc, key)
                    left, dr.force, dr.gq = bool(dr.force), None, False
                    if res is None or left:
                        raise Unscored('compound branch %d atom %d: forced atom %s' % (b + 1, j, 'failed: %s' % why if res is None else 'left tokens'))
                    _, lj, lf = dr.deltas.get(id(res), (0.0, None, res[1]))

                    def draw_c():
                        dr.p_k, dr.p_scope, dr.p_key, dr.p_last = kk, tuple(scope), key, ()
                        r_, w_ = dr.atom(fr, ka, sc, key)
                        return [r_, w_, None]

                    def cheap_c(c):  # as the draws of a branch's atom: unjoined, then a repeat
                        r_ = c[0]
                        if r_ is None:
                            return True
                        if kk > 1 and not r_[4] and r_[5]:
                            return False
                        c[2] = pf_ = closed_program(r_[0].dec, 2)
                        return pf_ is None or sum(dup_count(pf_)) <= sum(dup_base)

                    def costly_c(c):  # then can close, and the static prune in the last branch
                        r_, w_, pf_ = c
                        if r_ is None or not part_can_close(r_[0].dec):
                            return None
                        if STATIC_ATOM and b == nparts - 1 and static_hit(pf_, [base_forms, 0, len(gtexts), b, len(ptext)]):
                            return None
                        return r_
                    gc = [res, None, None]
                    if not (costly_c(gc) if cheap_c(gc) else None):
                        steps.append(dict(h=hi, b=b, j=j, rel=dr.gq_rel, lq_free=rd(lf), lq_join=rd(lj), lq_mix=rd(res[1]), gold_ok=False))
                        lw = -math.inf
                        break
                    ak = (key, kk, ka, tuple(sorted(dr.want)), tuple(wtypes), tuple(sorted(dr.need)), dup_base, len(ptext), b == nparts - 1)
                    if ak not in acc:
                        k1, n2c, k2 = two_stage_counts(EXACT_N1, EXACT_N2, draw_c, cheap_c, costly_c)
                        # a zero count takes half a candidate, as at a plain atom
                        acc[ak] = (k1, n2c, k2, math.log(max(k1, 0.5) / EXACT_N1) + (math.log(max(k2, 0.5) / n2c) if n2c else math.log(0.5)))
                    k1, n2c, k2, la = acc[ak]
                    lw += res[1] - la
                    node, atext = res[0], res[3]
                    d = node.dec
                    ltypes.update(fresh_types(list(node.toks), nlab0))
                    ctoks_ = ctoks_ + list(node.toks)
                    ptext.append(atext)
                    fresh = [int(x) for x in re.findall(r'\*L(\d+)', atext)]
                    joins = [int(x) for x in re.findall(r'(?<![*\w])L(\d+)', atext)]
                    made += fresh
                    read.update(joins)
                    if b == 0 and not atext.startswith('(NOT'):
                        first_.append(list(node.toks))
                    bound |= set(fresh) | (set(joins) & (exported or set()))
                    soft = None  # (rule, probability) where one rule alone holds the branch open
                    if b == 0:
                        closed = not is_output or not out_need(set(scope) | {ltypes.get(x) for x in made})
                    else:
                        named, local = exported <= bound, all(read[x] for x in made)
                        closed = named and local
                        if named != local:
                            soft = ('unread', P_UNREAD_LOCAL) if named else None if is_output else ('unnamed', P_UNNAMED)
                    h, s = bhazard.get(j, 1.0), 1.0 if closed else soft[1] if soft else 0.0  # s: the chance that the branch may close at a stop
                    if j == len(gatoms):  # gold stops here
                        lstop = 0.0 if closed and j == MAX_BRANCH else log0(h * s)  # at the cap a branch that can close ends whether it stops or not
                    else:
                        lstop = log0(1 - h * s)  # the stop is asked, and refused where s = 0
                    lw += lstop
                    steps.append(dict(h=hi, b=b, j=j, rel=dr.gq_rel, lq_free=rd(lf), lq_join=rd(lj), lq_mix=rd(res[1]), k1=k1, n2=n2c, k2=k2,
                                      la=rd(la), closed=closed, soft=soft and soft[0], lq_stop=rd(lstop)))
                    if lw == -math.inf:
                        break
                if lw > -math.inf:
                    outs.append(dict(lw=lw, d=d, ctoks=ctoks_, ltypes=ltypes, bound=bound, made=made, read=read, first=first_, dup_base=dup_base))
            return outs

        def lse(xs):
            m_ = max(xs, default=-math.inf)
            return m_ + math.log(sum(math.exp(x - m_) for x in xs)) if m_ > -math.inf else -math.inf

        def close(o, b):
            """Decoder and tokens of outcome o with the separator of branch b, None where the decoder refuses it."""
            d_ = o['d'].fork()
            try:
                d_.step(seps[b])
            except arclog.Refusal:
                return None
            return d_, o['ctoks'] + [seps[b]]
        dr.need = set(prev_need)
        st0 = dict(lw=0.0, d=d_head, ctoks=[a[0]], exported=None, first=[], first_made=frozenset(), ltypes={}, dup_base=(0, 0, 0), need=set(dr.need))
        # branch 0, then the export sets
        outs = run_branch(0, st0, 0)
        hyps = []
        if outs and close(outs[0], 0):
            o = outs[0]
            d_, ctoks_ = close(o, 0)
            exp0 = {x for x in o['made'] if not o['read'][x]}
            again = [x for x in o['made'] if o['read'][x]]
            if len(again) > 8:
                raise Unscored('branch 1 reads %d labels it made, too many export sets' % len(again))
            sets = collections.defaultdict(list)
            for mask in range(1 << len(again)):
                chosen = {x for i, x in enumerate(again) if mask >> i & 1}
                lw = sum(math.log(P_REEXPORT) if x in chosen else math.log1p(-P_REEXPORT) for x in again)
                ex = exp0 | chosen
                have = set(scope) | {o['ltypes'].get(x) for x in ex}
                for x in o['made']:  # the output clause exports a label it reads again where it holds a type the clause needs
                    if is_output and o['read'][x] and o['ltypes'].get(x) in out_need(have):
                        ex.add(x)
                        have.add(o['ltypes'].get(x))
                sets[frozenset(ex)].append(lw)
            for ex, lws in sets.items():
                hyps.append(dict(lw=o['lw'] + lse(lws), d=d_, ctoks=ctoks_, exported=ex, first=o['first'], first_made=frozenset(o['made']),
                                 ltypes=o['ltypes'], dup_base=o['dup_base'], need=set(dr.need)))
        for b in range(1, nparts):
            nxt = {}
            for hi, st in enumerate(hyps):
                dr.need = set(st['need'])
                outs = run_branch(b, st, hi)
                if not outs:
                    continue
                f = fail_rate(b, st) if T > 1 else 0.0
                fac = sum(f ** t for t in range(T))
                steps.append(dict(h=hi, b=b, f=rd(f), lq_retry=rd(math.log(fac)), n=GQ_BRANCH_N))
                for o in outs:
                    got = close(o, b)
                    if got is None:
                        continue
                    ex2 = st['exported'] & o['bound']
                    nk = (ex2, o['dup_base'])
                    nxt.setdefault(nk, []).append(dict(lw=st['lw'] + o['lw'] + math.log(fac), d=got[0], ctoks=got[1], exported=ex2, first=st['first'],
                                                       first_made=st['first_made'], ltypes=o['ltypes'], dup_base=o['dup_base'], need=st['need']))
            hyps = [dict(v[0], lw=lse([x['lw'] for x in v])) for v in nxt.values()]
        lq = lse([h_['lw'] for h_ in hyps])
        comp.update(tries=dict(sink), lq_branches=rd(lq), exports=[dict(set=sorted(h_['exported'] or ()), lw=rd(h_['lw'])) for h_ in hyps])
        dr.want, dr.need, dr.want_types = set(), set(), frozenset()
        return lpc + lshape + lgate + lq if lq > -math.inf else zero('no branch path of gold is drawn')

    def gold_q():
        """(log q of gold's path under the draws' proposal, [per-atom parts]); None where a step cannot be scored. Gold's tokens are forced
        through atom with the tilt and the coin mixture on (Drawer.gq); at each atom site log A^ comes from EXACT_N1 fresh candidates of
        a separate rng stream, with the two stages of EXACT; a gold atom that those stages reject has q 0. The stop after an atom has
        q's hazard hq, and where a gate would refuse the stop, q's chance to go on is 1 (a refused stop is no factor on a draw). A compound
        atom (gold's last) is scored by gold_compound. The caches, the rng and picked are put back, so the draws that follow are those of a
        run that does not score gold's q."""
        gq_none.clear()
        saved = (dict(dr.jcache), dict(dr.reach_cache), dr.lookahead_forks, dr.reach_drops, dr.complete_drops, dict(memo), dict(safes),
                 rng.getstate(), list(picked), dr.rng)
        dr.rng = random.Random(M.seed_of(task, case, seed_point, SEED_TAG + '/goldq'))
        yrng = random.Random(M.seed_of(task, case, seed_point, SEED_TAG + '/goldq/sir'))  # the rng of the SIR factor's Y draws
        sink = collections.Counter()
        gcur, gt, gtexts, parts, total = dec.fork(), [], [], [], 0.0
        try:
            for k, a in enumerate(gold_atoms, 1):
                part = dict(k=k)
                is_comp = a[0] in (M.OR, IF_TOK)
                if cc is not None and not is_comp:
                    total += math.log1p(-p_comp(k))
                scope = [str(t) for t in gprefix[k - 2]['types']] if k > 1 and gprefix[k - 2] else ()
                dr.p_labels = gprefix[k - 2].get('labels') if k > 1 and gprefix[k - 2] else None
                fr = dr.frontier(gcur, gt.count(M.STAR))
                prev_need = set(dr.need)  # a draw's compound starts with the need of the atom before it
                dr.want, dr.need = set(), need_at(scope)
                dr.t_prev = tilt_nk(gtexts[-1]) if dr.tilt and gtexts else '^'
                last_toks = tuple(gold_atoms[k - 2]) if k > 1 else ()
                dr.p_k, dr.p_scope, dr.p_key, dr.p_last = k, tuple(scope), tuple(gt), last_toks
                if is_comp:  # the draws end the clause at a compound: no stop factor
                    try:
                        total += gold_compound(k, a, gcur, gt, gtexts, scope, prev_need, part)
                    except Unscored as e:
                        gq_none.append(str(e))
                        return None
                    except Exception as e:  # noqa: BLE001
                        fr_ = traceback.extract_tb(e.__traceback__)[-1]
                        gq_none.append('compound atom: %s: %s (%s:%d in %s)' % (type(e).__name__, str(e)[:120], os.path.basename(fr_.filename), fr_.lineno, fr_.name))
                        return None
                    parts.append(part)
                    break
                dr.force, dr.gq, dr.gq_rel = collections.deque(a), True, []
                res, why = dr.atom(fr, k, scope, tuple(gt))
                left_toks, left, dr.force, dr.gq = list(dr.force), bool(dr.force), None, False
                part['rel'] = dr.gq_rel
                if res is None or left:
                    gq_none.append('atom %d: forced atom %s' % (k, 'failed: %s' % why if res is None else 'left tokens %s' % left_toks))
                    return None
                d_, lj, lf = dr.deltas.get(id(res), (0.0, None, res[1]))
                part.update(lp=res[6], lq_free=lf, lq_join=lj, lq_mix=res[1])

                def draw_c():
                    dr.p_k, dr.p_scope, dr.p_key, dr.p_last = k, tuple(scope), tuple(gt), last_toks
                    r_, w_ = dr.atom(fr, k, scope, tuple(gt))
                    return [r_, w_, None, None]

                def cheap_c(c):  # as cheap_main in the draw loop
                    r_ = c[0]
                    if r_ is None:
                        return True
                    if k > 1 and not r_[4] and r_[5]:
                        return False
                    c[2] = key_ = (tuple(gt), tuple(r_[0].toks))
                    m_ = memo.get(key_)
                    if m_ is None:
                        if len(memo) >= MEMO_CAP:
                            memo.clear()
                        m_ = memo[key_] = dict(pf=closed_program(r_[0].dec, 1))
                    c[3] = m_
                    if 'dups' not in m_:
                        m_['dups'] = dup_count(m_['pf']) if m_['pf'] is not None else None
                    return not (m_['pf'] is not None and any(m_['dups']))

                def costly_c(c):  # as costly_main in the draw loop
                    r_, w_, key_, m_ = c
                    if r_ is None:
                        return None
                    if SAFE_PREFIX:
                        if key_ not in safes:
                            if len(safes) >= MEMO_CAP:
                                safes.clear()
                            safes[key_] = m_['pf'] is not None
                        if not safes[key_]:
                            return None
                    if 'tb' not in m_:
                        m_['tb'] = body_table(fr, task, case, r_[0].dec, before)[0]
                    tb_ = m_['tb']
                    sm_ = summary(tb_)
                    if empty_gate and sm_ is not None and sm_['empty_inputs']:
                        return None
                    if 'static' not in m_:
                        m_['static'] = STATIC_ATOM and static_hit(m_['pf'], [base_forms, 0, k - 1])
                    return None if m_['static'] else ((r_, tb_), key_)

                gc = [res, None, None, None]
                gout = costly_c(gc) if cheap_c(gc) else None  # ((res, tb), key) of gold's atom
                part['gold_ok'] = gout is not None
                if part['gold_ok']:
                    k1, n2c, k2 = two_stage_counts(EXACT_N1, EXACT_N2, draw_c, cheap_c, costly_c)
                    part.update(k1=k1, n2=n2c, k2=k2)
                    # a zero count (the estimate says no candidate is accepted, yet gold is) takes half a candidate
                    la = math.log(max(k1, 0.5) / EXACT_N1) + (math.log(max(k2, 0.5) / n2c) if n2c else math.log(0.5))
                    part['la'] = la
                    q_site = res[1] - la
                    if steer_on and k <= STEER_K:
                        # SIR factor: the chance that the pick among m candidates is gold's atom a, per unit of q(a), is
                        # E[sum over a's position i of g(a) / (g(a) + g of the others the draw path has drawn)]. The draw path stops
                        # drawing at the first search that finds no atom (g = 0 for it and the rest), so a is reached at i <= f, f the
                        # position of the first such search among the m - 1 others Y, and the others are then Y[:f]. An 'end'
                        # candidate before the stop is picked by the draw path with no steering, so gold's atom gets 0 there (the
                        # EXACT sampler gives no 'end', so this holds for the draws as they are). With no search that fails it is
                        # m g(a) / (g(a) + sum g(Y)).
                        bsc, snan = {}, collections.Counter()

                        def beta_score(c):
                            if c[1] not in bsc:
                                bsc[c[1]] = STEER_BETA * steer_score(c[0], c[1], snan)
                            return bsc[c[1]]
                        sa, lfs = beta_score(gout), []
                        # The Y draws fill reach_cache (its key lacks the clause so far, so an entry from a draw at an early atom can refuse a
                        # later forced gold atom: 'atom cannot close') and take rng draws, so they run on their own rng and put the
                        # caches back, which leaves gold's atoms and the acceptance estimates as STEER_M=1 gives them.
                        yc = (dict(dr.reach_cache), dict(dr.jcache), dr.rng)
                        dr.rng = yrng
                        for _ in range(STEER_GQ_R):
                            ys = [exact_two_stage(EXACT_N1, EXACT_N2, draw_c, cheap_c, costly_c, sink)[0] for _ in range(STEER_M - 1)]
                            f = next((j for j, y in enumerate(ys) if y is None), len(ys))
                            if any(y is not None and y[0] == 'end' for y in ys[:f]):
                                lfs.append(-math.inf)
                                continue
                            zs = [sa] + [beta_score(y) for y in ys[:f]]
                            mx = max(zs)
                            lfs.append(math.log(f + 1) + sa - mx - math.log(sum(math.exp(z - mx) for z in zs)))
                        dr.reach_cache, dr.jcache, dr.rng = yc
                        mx = max(lfs)
                        lf = mx + math.log(sum(math.exp(x - mx) for x in lfs)) - math.log(len(lfs)) if mx > -math.inf else -math.inf
                        fs = [math.exp(x) for x in lfs]
                        part.update(steer_lf=lf, steer_m=STEER_M, steer_r=len(lfs), steer_sd=statistics.stdev(fs) if len(fs) > 1 else None,
                                    steer_nan=snan['steer nan'])  # the distinct cuts scored nan (floored)
                        q_site += lf
                else:
                    q_site = -math.inf
                stop_q = stop_p = 0.0
                if gsafe[k - 1]:
                    h = 1.0 if k >= MAX_ATOMS else hazard.get(k, hazard[max(hazard)] if hazard else 1.0)
                    hq = h
                    if dr.tilt and 0 < h < 1 and k < MAX_ATOMS:
                        hq = h / (h + (1 - h) * math.exp(-tilt_stop_odds(tilt_tab, k)))
                    tb = gprefix[k - 1]
                    if STEER_CHOICE and k < MAX_ATOMS:  # as the draws: the odds of q's stop shifted by the model's, on the tilt's
                        d_ = dr.stop_shift(res[0].dec, tuple(gt) + tuple(a), k, list(a), res[2], res[3], tb, h)
                        hq = hq * math.exp(d_) / (1 - hq + hq * math.exp(d_))
                    gtexts.append(res[3])
                    gate = None
                    if is_output and tb is not None:
                        end_pf = closed_program(res[0].dec, 1)
                        if end_pf is not None:
                            gate = stop_gate(dict(x=summary(tb), x_rows=rows_with_models(tb, X_ROWS_CAP)), end_pf.split('\n')[base_forms])
                    if port_need and tb is not None and any(not n & {str(t) for t in tb['types']} for n in port_need):
                        gate = 'port head'
                    if gate is None and k == 1 and pkind in MIN2_KINDS and not out_reads and not one_call(dr, gtexts):
                        gate = 'one atom'
                    if gate is None and group in DERIVED_GROUPS and not reads_derived(gtexts):
                        gate = 'no derived read'
                    if gate is None and group == 'INIT port' and port_unread(res[0].dec) > MAX_UNREAD:
                        gate = 'port unread'
                    last = k == len(gold_atoms)
                    stop_p = math.log(h) if last else log0(1 - h)
                    stop_q = (-math.inf if gate else log0(hq)) if last else (0.0 if gate else log0(1 - hq))
                    part.update(gate=gate, stop_p=stop_p, stop_q=stop_q)
                else:
                    gtexts.append(res[3])
                total += q_site + stop_q
                parts.append({x: (round(v, 4) if isinstance(v, float) and math.isfinite(v) else None if isinstance(v, float) else v) for x, v in part.items()})
                if not math.isfinite(total):
                    break
                gcur, gt = res[0].dec, gt + list(a)
            return total, parts
        finally:
            dr.force, dr.gq, dr.rng = None, False, saved[9]
            dr.want, dr.need, dr.want_types = set(), set(), frozenset()
            dr.jcache, dr.reach_cache, dr.lookahead_forks, dr.reach_drops, dr.complete_drops = saved[:5]
            memo.clear()
            memo.update(saved[5])
            safes.clear()
            safes.update(saved[6])
            rng.setstate(saved[7])
            picked[:] = saved[8]
            dr.deltas.clear()

    def gold_orders():
        """GOLD_ORDERS: fields of gold's row: logq_orders, gold's log q summed over its valid orders, each order's q from gold_q. The scored
        orders are those with the compound last, where gold has a compound: with an atom after it the draws give q 0. At most 5 atoms:
        every order, an exact sum of the estimated q's. More atoms: GOLD_ORDER_CAP orders at random, and the sum is (number of orders) times the
        mean q, the number being count_orders' times the share of tried orders that the decoder takes. Two compounds have q 0 in every order."""
        nonlocal gold_atoms, gprefix, gsafe
        kept, sites = (gold_atoms, gprefix, gsafe), label_sites(V, gold_atoms)
        comps = [i for i, a in enumerate(kept[0]) if a[0] in (M.OR, IF_TOK)]
        n, exact = len(kept[0]), len(kept[0]) <= 5
        if len(comps) > 1:
            return dict(logq_orders=None, logq_orders_zero=True, orders_n=None, orders_drawn=0, orders_exact=exact, order_q=[])
        plain = [i for i in range(n) if i not in comps]
        scored, others, refused = [], 0, collections.Counter()
        try:
            if exact and comps:  # the orders with the compound elsewhere count in orders_n only
                for o in itertools.permutations(range(n)):
                    if o[-1] != comps[0]:
                        atoms = reorder(kept[0], sites, o, dr.fr.label_tok)
                        others += atoms is not None and order_state(atoms, False) is not None
            for o in random_orders(plain, order_rng()):
                o = tuple(o) + tuple(comps)
                atoms = reorder(kept[0], sites, o, dr.fr.label_tok)
                st_ = order_state(atoms, True) if atoms is not None else None
                if st_ is None or not st_['same']:
                    refused['guard' if atoms is None else 'decoder' if st_ is None else 'changed'] += 1
                    continue
                gold_atoms, gprefix, gsafe = st_['atoms'], st_['prefix'], st_['safe']
                got = gold_q()
                if got is None:
                    refused['unscored'] += 1
                    continue
                scored.append(dict(order=list(o), lq=got[0] if math.isfinite(got[0]) else None))
                if not exact and len(scored) >= GOLD_ORDER_CAP:
                    break
        finally:
            gold_atoms, gprefix, gsafe = kept
        lqs = [x['lq'] if x['lq'] is not None else -math.inf for x in scored]
        tried = len(scored) + refused['decoder'] + refused['changed'] + refused['unscored']
        nd = float(len(scored)) if exact else count_orders(kept[0], sites, plain) * len(scored) / max(tried, 1)
        total = (lse(lqs) if exact else math.log(nd) + lse(lqs) - math.log(len(lqs))) if lqs and nd else -math.inf
        return dict(logq_orders=total if math.isfinite(total) else None, logq_orders_zero=not math.isfinite(total), orders_n=others + len(scored) if exact else None,
                    orders_drawn=nd, orders_exact=exact, orders_left_out=dict(refused), order_q=scored)

    if GOLD_Q and rows[0].get('clause'):
        try:
            got = gold_q()
            if got is not None:
                rows[0]['logq_steer'] = got[0] if math.isfinite(got[0]) else None
                rows[0]['logq_steer_zero'] = not math.isfinite(got[0])
                rows[0]['logq_steer_parts'] = got[1]
            else:
                rows[0]['logq_steer_none'] = gq_none[0] if gq_none else 'unknown'
        except Exception as e:  # noqa: BLE001
            fr_ = traceback.extract_tb(e.__traceback__)[-1]
            rows[0]['logq_steer_error'] = '%s: %s (%s:%d in %s)' % (type(e).__name__, str(e)[:200], os.path.basename(fr_.filename), fr_.lineno, fr_.name)
        if GOLD_ORDERS:
            try:
                rows[0].update(gold_orders())
            except Exception as e:  # noqa: BLE001
                fr_ = traceback.extract_tb(e.__traceback__)[-1]
                rows[0]['logq_orders_error'] = '%s: %s (%s:%d in %s)' % (type(e).__name__, str(e)[:200], os.path.basename(fr_.filename), fr_.lineno, fr_.name)

    setup_cpu, c0 = round(time.process_time() - c0, 2), time.process_time()  # the budget is for draws: setup (the prefix's tables, gold) is outside it
    while len(rows) <= draws and time.process_time() - c0 < seconds:  # CPU seconds, so a loaded machine gives a point the same work
        cur = dec.fork()
        toks, text, lg, prefix, fail, safe, cuts = [], [], Logs(), [], None, [], []
        alqs, alps = [], []  # per atom of the main loop: its log q and log P (picks only, no stop factors)
        compound = False
        ltypes = {}
        dtries = collections.Counter()
        steer_log = []
        xacc[:] = [0.0, 0, 0.0]
        picked.clear()
        dr.t_prev = '^'
        steer = False  # the port stop gate found unread labels: the next atom favours the labels no token reads yet
        try:
            for k in range(1, MAX_ATOMS + 1):
                scope = [str(t) for t in prefix[-1]['types']] if prefix and prefix[-1] else ()
                dr.p_labels = prefix[-1].get('labels') if prefix and prefix[-1] else None
                pc = p_comp(k) if cc is not None else None
                comp_here = cc is not None and rng.random() < pc
                if comp_here:
                    ltypes0 = dict(ltypes)
                    got, why = draw_compound(cur, toks, text, scope, k, dtries, ltypes)
                    if got is None:
                        fail = 'compound: ' + why
                        lg.both(math.log(pc))
                        break
                    if group in DERIVED_GROUPS and not reads_derived(text + [got[2]]):
                        dtries['gate:no derived read'] += 1
                        ltypes = ltypes0
                        comp_here = False
                    elif group == 'INIT port' and port_unread(got[0]) > MAX_UNREAD:
                        dtries['gate:port unread'] += 1
                        steer = True
                        ltypes = ltypes0
                        comp_here = False
                if cc is not None:  # a compound that a gate drops counts as a step with no compound
                    lg.both(math.log(pc) if comp_here else math.log1p(-pc))
                if comp_here:
                    cur, ctoks, ctext, clg = got
                    toks += ctoks
                    text.append(ctext)
                    cuts.append(len(toks))
                    lg.add(clg)
                    compound = True
                    if not can_end(cur):
                        fail = 'compound: clause cannot end'
                    break
                fr = dr.frontier(cur, toks.count(M.STAR), tuple(toks))  # cur is stepped in place by nobody: evaluate, closed_program and port_unread fork it
                unread = [i for i in range(toks.count(M.STAR)) if fr.label_tok.get(i) not in (None, *toks)] if steer else []
                dr.want = {fr.label_tok[i] for i in unread}
                wtypes = [ltypes[i] for i in unread if ltypes.get(i)]
                dr.need = need_at(scope)
                n_cand = STEER_M if steer_on and k <= STEER_K else 1
                cands = []
                for _ in range(n_cand):
                  got, free, ex_la = None, 0, 0.0  # ex_la, and the coin delta below, belong to this candidate
                  dr.deltas.clear()
                  for n_try in range(0 if EXACT else ATOM_TRIES + CHEAP_TRIES):
                      if n_try - free >= ATOM_TRIES:
                          break
                      dr.p_k, dr.p_scope, dr.p_key = k, tuple(scope), tuple(toks)
                      dr.p_last = tuple(toks[(cuts[-2] if len(cuts) > 1 else 0):cuts[-1]]) if cuts else ()
                      res, why = dr.atom(fr, max(k, 2) if wtypes else k, wtypes or scope, tuple(toks))
                      if res is None:
                          dtries['construct:' + re.sub(r'refused .*', 'refused', why)] += 1
                          continue
                      key = (tuple(toks), tuple(res[0].toks))
                      m = memo.get(key)
                      if m is None:  # the closed program is None exactly where END is refused, which is can_end's test
                          if len(memo) >= MEMO_CAP:
                              memo.clear()
                          m = memo[key] = dict(pf=closed_program(res[0].dec, 1))
                      if SAFE_PREFIX:
                          if key not in safes:
                              if len(safes) >= MEMO_CAP:
                                  safes.clear()
                              safes[key] = m['pf'] is not None
                          if not safes[key]:
                              dtries['unsafe'] += 1
                              continue
                      if k > 1 and not res[4] and res[5]:
                          dtries['unjoined'] += 1
                          free += 1
                          continue
                      if 'dups' not in m:
                          m['dups'] = dup_count(m['pf']) if m['pf'] is not None else None
                      pf = m['pf']
                      if pf is not None and any(dups := m['dups']):
                          dtries['prefix key' if dups[2] else 'repeat'] += 1
                          if not dups[2] and not dups[0]:
                              dtries['repeat via dup_cmp'] += 1
                          free += 1
                          continue
                      if 'tb' not in m:
                          m['tb'] = body_table(fr, task, case, res[0].dec, before)[0]
                      tb = m['tb']
                      sm = summary(tb)
                      if empty_gate and sm is not None and sm['empty_inputs']:
                          dtries['empty'] += 1
                          continue
                      if 'static' not in m:
                          m['static'] = STATIC_ATOM and static_hit(pf, [base_forms, 0, len(text)])
                      if m['static']:
                          dtries['static'] += 1
                          continue
                      got = (res, tb)
                      break
                  if EXACT:
                      def draw_main():
                          dr.p_k, dr.p_scope, dr.p_key = k, tuple(scope), tuple(toks)
                          dr.p_last = tuple(toks[(cuts[-2] if len(cuts) > 1 else 0):cuts[-1]]) if cuts else ()
                          res, why = dr.atom(fr, max(k, 2) if wtypes else k, wtypes or scope, tuple(toks))
                          return [res, why, None, None]  # key and memo entry are set by cheap_main

                      def cheap_main(c):
                          res = c[0]
                          if res is None:  # a draw that cannot be built has no atom for these checks: it fails the expensive stage
                              return True
                          if k > 1 and not res[4] and res[5]:
                              dtries['unjoined'] += 1
                              return False
                          c[2] = key = (tuple(toks), tuple(res[0].toks))
                          m = memo.get(key)
                          if m is None:
                              if len(memo) >= MEMO_CAP:
                                  memo.clear()
                              m = memo[key] = dict(pf=closed_program(res[0].dec, 1))
                          c[3] = m
                          if 'dups' not in m:
                              m['dups'] = dup_count(m['pf']) if m['pf'] is not None else None
                          if m['pf'] is not None and any(dups := m['dups']):
                              dtries['prefix key' if dups[2] else 'repeat'] += 1
                              if not dups[2] and not dups[0]:
                                  dtries['repeat via dup_cmp'] += 1
                              return False
                          return True

                      def costly_main(c):
                          res, why, key, m = c
                          if res is None:
                              dtries['construct:' + re.sub(r'refused .*', 'refused', why)] += 1
                              return None
                          if SAFE_PREFIX:
                              if key not in safes:
                                  if len(safes) >= MEMO_CAP:
                                      safes.clear()
                                  safes[key] = m['pf'] is not None
                              if not safes[key]:
                                  dtries['unsafe'] += 1
                                  return None
                          if 'tb' not in m:
                              m['tb'] = body_table(fr, task, case, res[0].dec, before)[0]
                          tb = m['tb']
                          sm = summary(tb)
                          if empty_gate and sm is not None and sm['empty_inputs']:
                              dtries['empty'] += 1
                              return None
                          if 'static' not in m:
                              m['static'] = STATIC_ATOM and static_hit(m['pf'], [base_forms, 0, len(text)])
                          if m['static']:
                              dtries['static'] += 1
                              return None
                          return (res, tb), key
                      r_, ex_la = exact_two_stage(EXACT_N1, EXACT_N2, draw_main, cheap_main, costly_main, dtries)
                      got, key = r_ if r_ is not None else (None, None)
                  if got is None:
                      break
                  cands.append((got, key, ex_la, dr.deltas.get(id(got[0]), (0.0,))[0] if EXACT_COIN and got != 'end' else 0.0))
                  if got == 'end':
                      break
                got = None
                if n_cand == 1 or any(c == 'end' for c, *_ in cands):
                    got, key, ex_la, cdelta = cands[-1] if cands else (None, None, 0.0, 0.0)
                elif cands:  # a search that found no atom is a candidate with g = 0
                    ss = [steer_score(c, ckey) for c, ckey, *_ in cands]
                    top = max(ss)
                    gs = [math.exp(STEER_BETA * (x - top)) for x in ss]
                    pick = rng.choices(range(len(cands)), weights=gs)[0]
                    got, key, ex_la, cdelta = cands[pick]  # the picked candidate's A^ and coin delta
                    lg.x += math.log(gs[pick]) - math.log(sum(gs) / n_cand)
                    steer_log.append([k, [round(x, 3) for x in ss], pick])
                if got is None:
                    fail = 'atom %d: no atom in %d tries' % (k, ATOM_TRIES)
                    break
                if got == 'end':
                    dtries['forced end'] += 1
                    break
                if EXACT:
                    lg.x -= ex_la
                    xacc[0] -= ex_la
                    xacc[1] += 1
                if EXACT_COIN:
                    xacc[2] += cdelta
                (node, alq, rel, atext, _, _, alp), tb = got
                if dr.tilt:
                    dr.t_prev = tilt_nk(atext)
                cur = node.dec
                ltypes.update(fresh_types(list(node.toks), toks.count(M.STAR)))
                toks += list(node.toks)
                text.append(atext)
                cuts.append(len(toks))
                lg.q += alq
                lg.p += alp
                alqs.append(round(alq, 4))
                alps.append(round(alp, 4))
                prefix.append(tb)
                ok = safes[key] if SAFE_PREFIX and key in safes else can_end(cur)
                safe.append(ok)
                h = 1.0 if k >= MAX_ATOMS else hazard.get(k, hazard[max(hazard)] if hazard else 1.0)  # past the table: its last stop rate  # the stop factors count only where the clause can end
                hq = h  # q's stop hazard: h, shifted in odds by the tilt of the clause length
                if dr.tilt and 0 < h < 1 and k < MAX_ATOMS:
                    hq = h / (h + (1 - h) * math.exp(-tilt_stop_odds(tilt_tab, k)))
                if ok and k < MAX_ATOMS and STEER_CHOICE:  # STEER_CHOICE: the odds of q's stop shifted by the model's, on the tilt's
                    d_ = dr.stop_shift(cur, tuple(toks), k, list(node.toks), rel, atext, tb, h)
                    hq = hq * math.exp(d_) / (1 - hq + hq * math.exp(d_))
                if ok and (k >= MAX_ATOMS or rng.random() < hq):
                    why = None
                    if is_output and tb is not None:
                        end_pf = closed_program(cur, 1)
                        if end_pf is not None:
                            why = stop_gate(dict(x=summary(tb), x_rows=rows_with_models(tb, X_ROWS_CAP)), end_pf.split('\n')[base_forms])
                    if port_need and tb is not None and any(not n & {str(t) for t in tb['types']} for n in port_need):
                        why = 'port head'
                    if why is None and k == 1 and pkind in MIN2_KINDS and not out_reads and not one_call(dr, text):
                        why = 'one atom'
                    if why is None and group in DERIVED_GROUPS and not reads_derived(text):
                        why = 'no derived read'
                    if why is None and group == 'INIT port' and port_unread(cur) > MAX_UNREAD:
                        why = 'port unread'
                        steer = True
                    if why is None:
                        lg.p += math.log(h)
                        lg.x += math.log(hq)
                        break
                    lg.p += log0(1 - h)  # the gate is fixed given the state, so q goes on with probability 1
                    dtries['gate:' + why] += 1
                elif ok:
                    lg.p += math.log1p(-h)
                    lg.x += math.log1p(-hq)
                if k >= MAX_ATOMS:
                    fail = why if ok and why in ('no derived read', 'port unread') else (
                        'output gate at %d atoms' if ok else 'not safe at %d atoms') % k
            tries.update(dtries)
            extra = dict(tries=dict(dtries), prefix_safe=safe, compound=compound, steer=steer_log or None, atom_lq=alqs, atom_lp=alps)
            if EXACT:
                extra['exact'] = [xacc[0], xacc[1]]
            if EXACT_COIN:
                extra['coin'] = xacc[2]
            if fail:
                rows.append(dict(task=task, case=case, point=point, draw=len(rows), gold=False, atoms=text, n_atoms=len(text),
                                 logq=lg.q, logp=lg.p, logq_full=lg.q + lg.x, fail=fail, **extra))
            else:
                rows.append(evaluate(cur, toks, text, lg, prefix, False, extra))
                rows[-1].pop('_x_table', None)
                if PREFIX_DRAWS and rows[-1]['fail'] is None:
                    prefix_rows += cut_rows(toks, cuts, text, prefix, safe, False, rows[-1]['draw'])
        except Exception as e:  # noqa: BLE001
            rows.append(dict(task=task, case=case, point=point, draw=len(rows), gold=False, atoms=text,
                             fail='error: %s: %s (%s:%d)' % (type(e).__name__, str(e)[:200], os.path.basename(traceback.extract_tb(e.__traceback__)[-1].filename), traceback.extract_tb(e.__traceback__)[-1].lineno)))
    fp = spec.get('fstore_point', point)  # a port's point in fstore; it was drawn at [clause, 0]
    for r in itertools.chain(rel_rows, choice_rows, cutopt_rows, valcut_rows, prefcut_rows, prefix_rows):
        r['point'] = fp
    for r in rows:
        for k in ('logq', 'logp', 'logq_full'):  # a path P or q gives probability 0 (a gate refusing a stop of hazard 1)
            if isinstance(r.get(k), float) and not math.isfinite(r[k]):
                r[k], r[k + '_zero'] = None, True
    sample_error, gold_line, samples, left_out, pt = None, None, [], 0, dict(body_path=None, clause_path=None, kind=None)
    try:
        if make_samples:
            gold_line, pt = original_point(spec, st)
            samples, left_out = sample_records(spec, rows, names, gold_line, pt, port_text if port else None)
        else:
            pt = pre.point_info(fp)
    except Exception as e:  # noqa: BLE001
        sample_error = '%s: %s' % (type(e).__name__, str(e)[:200])
    for r in rows:
        r['point'], r['point_group'], r['out_reads'] = fp, spec.get('point_group'), bool(out_reads)
        r['body_path'], r['clause_path'], r['point_kind'] = pt['body_path'], pt['clause_path'], pt['kind']
        r.setdefault('own_depth', None)
    return dict(task=task, case=case, point=fp, point_group=spec.get('point_group'), seconds=round(time.time() - t0, 2), cpu=round(time.process_time() - c0, 2), setup_cpu=setup_cpu, draws=len(rows) - 1,
                tries=dict(tries), lookahead_forks=dr.lookahead_forks, reach_stats=dict(dr.reach_stats), reach_drops=dr.reach_drops, complete_drops=dr.complete_drops, rc_errors=dict(rc.errors),
                names=names, sample_error=sample_error, gold_line=gold_line, samples=samples, samples_left_out=left_out, prefix_rows=prefix_rows, rel_rows=rel_rows, choice_rows=choice_rows, valcut_rows=valcut_rows, prefcut_rows=prefcut_rows, cutopt_rows=cutopt_rows, cutopts_truncated=cut_info['truncated'] if CUT_OPTS or VAL_CUTS else None,
                engine={k: round(v['ns'] / 1e6, 1) for k, v in arclog.engine_stats().items() if v['ns']} if engine_stats else None,
                rel_steer={k: round(v, 3) for k, v in dr.rel_stats.items()} if STEER_REL else None,
                choice_steer={k: round(v, 3) for k, v in dr.choice_stats.items()} if STEER_CHOICE else None,
                maxrss_mb=round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 2 ** 20)), rows


# ---------------------------------------------------------------- samples

def form_spans(text):
    """[(start, end)] of each top-level form of program text, numbered as M_sexprs numbers them."""
    spans, depth = [], 0
    for m in re.finditer(r'\(|\)|"(?:[^"\\]|\\.)*"|[^\s()]+', text):
        if m.group() == '(':
            if depth == 0:
                start = m.start()
            depth += 1
        elif m.group() == ')':
            depth -= 1
            if depth == 0:
                spans.append((start, m.end()))
        elif depth == 0:
            spans.append((m.start(), m.end()))
    return spans


def display_text(text, names):
    """Program text with each form's relations written as program names (rename_relations reads one form)."""
    out, pos = [], 0
    for start, end in form_spans(text):
        out += [text[pos:start], rename_relations(text[start:end], names)]
        pos = end
    return ''.join(out) + text[pos:]


def original_point(spec, st):
    """(gold line, {body_path, clause_path, kind}) of a spec's original gold program (an INIT port's whole INIT program, not
    the rewritten one) and of the point in its points(). The gold's text is the engine's own: the evaluator's program from the
    original's stream, relations by slot (`&r2`), as decoder programs write them."""
    prog = arclog.StudyProgram.from_sexp(spec['port']['full_sexp'] if spec.get('port') else spec['gold_sexp'], st)
    ids, model, _ = prog.decode_stream()
    text = arclog.StudyTaskEvaluator(spec['task'], TASKS.rstrip('/'), st).from_stream(ids, model).sexp()
    return (dict(task=spec['task'], case=spec['case'], text=text, stream=dict(ids=list(ids), model=list(model))),
            point_info(prog, list(spec.get('fstore_point', spec['point']))))


def point_info(prog, fp):
    """{body_path, clause_path, kind} of the point with body path fp in the points() of program prog."""
    mp = next(p for p in prog.points() if list(p.body_path) == fp)
    return dict(body_path=fp, clause_path=list(mp.clause_path), kind=mp.kind)


def sample_records(spec, rows, names, gold, pt, port_text=None):
    """([study-sample-v1 record], draws left out) of the draws of one point that have a clause and no fail: the gold's text
    with the form at the point replaced by the draw's clause, relations by slot; proposal.display_text writes them as program names. The stream
    is kept at RULE and DET points, whose rows are tokens in the id space of the original program. At an INIT port,
    port_text(rule clause, head, True) gives the INIT line in the original's slots with gold's head, and a row with no port
    clause (no table) is left out; so is a draw whose head no renaming gives gold's (port_text gives None), which is counted."""
    if '_error' in names:
        raise ValueError('names: ' + names['_error'])
    sha = hashlib.sha256(open(TASKS + spec['task'] + '.json', 'rb').read()).hexdigest()
    start, end = form_spans(gold['text'])[pt['body_path'][0]]
    records, left_out = [], 0
    for r in rows:
        if not r.get('clause') or r.get('fail') or (port_text and 'rule_clause' not in r):
            continue
        clause = port_text(r['rule_clause'], r['port_head'], True) if port_text else r['clause']
        if clause is None:
            left_out += 1
            continue
        cand = dict(kind='body_replacement', text=gold['text'][:start] + clause + gold['text'][end:], clause=clause, source_revision=SOURCE_REVISION)
        if not spec.get('port'):
            cand['stream'] = dict(ids=list(r['stream']), model=[1] * len(r['stream']))
        records.append(sl.sample_record(task=spec['task'], task_sha256=sha, case=spec['case'], gold=gold, point=pt, candidate=cand,
                                        proposal=dict(logq=r['logq'], logp=r['logp'], logq_full=r['logq_full'], tries=r.get('tries') or {}, gold=bool(r['gold']), draw=r['draw'],
                                                      display_text=display_text(cand['text'], names)))[0])
    return records, left_out


# ---------------------------------------------------------------- driver

FSTORE_INDEX = os.path.join(P.SAMPLER_DATA, 'fstore_index-%s.json.gz' % hashlib.sha256(FSTORE.encode()).hexdigest()[:8])


def fstore_points():
    """{point directory name: (its point.json's case, its point, its gold.arclog text)} of every point in FSTORE. FSTORE_INDEX
    keeps each point's entry with its directory's modification time; only points that are new or whose directory changed
    are read again."""
    names = sorted(d for d in os.listdir(FSTORE) if not d.endswith('.building'))  # a point directory still being built has no point.json yet
    old, old_golds = {}, []
    try:
        with gzip.open(FSTORE_INDEX, 'rt') as f:
            c = json.load(f)
        old, old_golds = c['points'], c['golds']
    except (OSError, ValueError, KeyError):
        pass
    gid, points, read = {}, {}, 0
    for d in names:
        try:  # a point the store moves aside while this reads it is left out
            mt = os.stat(FSTORE + d).st_mtime_ns
            e = old.get(d)
            if e is not None and len(e) == 4 and e[3] == mt:
                case, point, gold = e[0], e[1], old_golds[e[2]]
            else:
                pj = json.load(open(FSTORE + d + '/point.json'))
                case, point, gold = pj['case'], pj['point'], open(FSTORE + d + '/gold.arclog').read()
                read += 1
        except OSError:
            continue
        points[d] = (case, point, gid.setdefault(gold, len(gid)), mt)
    if read or len(points) != len(old):
        tmp = '%s.%d' % (FSTORE_INDEX, os.getpid())
        with gzip.open(tmp, 'wt') as f:
            json.dump(dict(golds=list(gid), points=points), f)
        os.replace(tmp, FSTORE_INDEX)
    golds = list(gid)
    return {d: (case, point, golds[g]) for d, (case, point, g, mt) in points.items()}


def ancestor_order(forms, i):
    """The numbers of the forms that form i of parsed forms reads, directly or through other forms, sorted by (depth in the read
    graph, form text). A form comes after each form it reads, and the order reads no written position."""
    heads = {f[1]: j for j, f in enumerate(forms) if len(f) > 1 and isinstance(f[1], str) and f[1].startswith('&')}
    depth = {}

    def d(j):
        if j not in depth:
            depth[j] = 1 + max((d(heads[r]) for r in strata.reads_of(forms[j][2:], set()) - {forms[j][1]} if r in heads), default=0)
        return depth[j]
    d(i)
    del depth[i]
    return sorted(depth, key=lambda j: (depth[j], sx(forms[j])))


def ancestor_spec(spec):
    """spec with its program written as the clause's ancestors (ancestor_order), the clause, and the other forms as they were; the
    decoder never reaches the other forms, which only keep the program whole. The point's number follows, written_point and
    fstore_point keep its place in the written program, and the seed reads the clause's text. An INIT port's clause is its
    whole INIT, so the ancestors are those of the INIT."""
    port = spec.get('port')
    whole = port['full_sexp'] if port else spec['gold_sexp']
    texts = [whole[a:b] for a, b in form_spans(whole)]
    i = spec['point'][0]
    anc = ancestor_order(strata.sexprs(whole), i)
    head = [texts[j] for j in anc]
    new = '\n'.join(head + [texts[i]] + [t for j, t in enumerate(texts) if j != i and j not in anc])
    out = dict(spec, point=[len(anc)] + list(spec['point'][1:]), written_point=spec['point'], fstore_point=spec.get('fstore_point', spec['point']),
               written_sexp=whole, gold_sexp=new, prefix_lines=head, seed_point=texts[i])
    if port:
        g = spec['gold_sexp']
        out['gold_sexp'] = '\n'.join(head + [g[a:b] for a, b in form_spans(g)[i:]])
        out['port'] = dict(port, full_sexp=new)
    return out


def moved_names(relations, text):
    """{'&rN': display name} of the slots of program text, a program with the forms of the written one in another order. A form
    declares a run of slots (an INIT one per port), in the same inner order wherever the form stands. relations: the written program's
    entries of relation_source_names_json."""
    runs = collections.defaultdict(list)
    for r in sorted(relations, key=lambda r: r['relation_slot']):
        runs[r['display_name'].split('.')[0]].append(r['display_name'])
    names = [x for f in strata.sexprs(text) if len(f) > 1 and isinstance(f[1], str) and f[1].startswith('&') for x in runs.get(f[1], ())]
    if len(names) != len(relations):
        raise ValueError('the forms of the program do not account for its %d relations' % len(relations))
    return {'&r%d' % i: x for i, x in enumerate(names)}


def point_forms(spec):
    """The parsed forms of the program that spec's point number counts in."""
    return strata.sexprs(spec['gold_sexp']) if spec.get('written_sexp') else strata.program_forms(spec['point_dir'])


def pick_groups(n, dev, groups, per_task=1):
    """Hash-ordered points of dev tasks in fstore/points: up to n of each point group, at most per_task of a task in a group."""
    idx = fstore_points()
    by_task = collections.defaultdict(list)
    for d in idx:
        by_task[d.split('-')[0]].append(d)
    got, seen = collections.Counter(), collections.Counter()
    comps = component_ports()
    order = sorted((t for t in dev if t in by_task), key=lambda t: hashlib.sha256(t.encode()).hexdigest())
    for t in order:
        for d in sorted(by_task[t], key=lambda d: hashlib.sha256(d.encode()).hexdigest()):
            case, point, gold = idx[d]
            forms = strata.sexprs(gold)
            if point[0] >= len(forms) or not forms[point[0]]:
                continue
            f = forms[point[0]]
            if not any(isinstance(x, list) for x in f[2:]):  # a lib relation's constructor form, such as (DET &bg DominantColor): no body to draw
                continue
            port = None
            if len(point) == 3 and f[0] == 'INIT' and 'INIT port' in groups:  # [clause, port's place in the INIT, element]
                el = f[3 + point[1]] if 3 + point[1] < len(f) else None
                ports = port_parts(f[:3] + [el]) if isinstance(el, list) and el and el[0] != 'key' else []
                if not ports or f[2] not in comps or any(isinstance(x, list) and x and x[0] == 'key' for x in f[3:]):
                    continue
                name, head, atoms = ports[0]
                params, cports = comps[f[2]]
                if any(not isinstance(lb, str) for _, lb in head) or name not in cports:
                    continue
                lines = [ln for ln in gold.splitlines() if ln.strip()]
                port = dict(name=name, head=head, atoms=atoms, ctypes=cports[name], params=sorted(params), full_sexp=gold)
                gold = '\n'.join(lines[:point[0]] + ['(RULE &port_body %s)' % ' '.join(sx(a) for a in atoms),
                                                      '(RULE &output (input (:P *P) (:Col *Col)))', '(OUT (&output ^P ^Col))'])
            elif len(point) != 2 or f[0] not in ('RULE', 'DET'):
                continue
            pf = strata.point_fields(forms, point[0])
            if port:
                pf['point_group'] = 'INIT port'
            s = pf['point_group']
            if s in groups and got[s] < n and seen[t, s] < per_task:
                got[s] += 1
                seen[t, s] += 1
                yield dict(task=t, case=case, point=[point[0], 0] if port else point, fstore_point=point, gold_sexp=gold,
                           point_dir=FSTORE + d, kind=pf['kind'], point_group=pf, port=port)


def pick_points(n, dev, kind='RULE'):
    """Hash-ordered points of dev tasks in fstore/points whose clause is of the kind (RULE or DET), one per task."""
    idx = fstore_points()
    by_task = collections.defaultdict(list)
    for d in idx:
        by_task[d.split('-')[0]].append(d)
    order = sorted((t for t in dev if t in by_task), key=lambda t: hashlib.sha256(t.encode()).hexdigest())
    for t in order:
        for d in sorted(by_task[t], key=lambda d: hashlib.sha256(d.encode()).hexdigest()):
            case, point, gold = idx[d]
            forms = M_sexprs(gold)
            if len(point) == 2 and point[0] < len(forms) and forms[point[0]] and forms[point[0]][0] == kind:
                yield dict(task=t, case=case, point=point, gold_sexp=gold, point_dir=FSTORE + d)
                n -= 1
                break
        if n <= 0:
            return


def worker(args):
    """[(info, rows)] of points of one gold program, in program order, sharing one Prefix."""
    jobs, draws, seconds, regcols, samples, engine_stats = args
    out, pre = [], None
    prof = None
    if os.environ.get('PROFILE'):  # PROFILE=path: each job's cProfile stats go to path.<pid>.<n>
        import cProfile
        prof = cProfile.Profile()
        prof.enable()
    try:
        pre = Prefix(jobs[0][0])
        jobs = sorted(jobs, key=lambda j: pre.first(j[0]['point']))
    except Exception:  # noqa: BLE001
        pre = None
    for spec, counts, hazard in jobs:
        try:
            if pre is not None and pre.pos > pre.first(spec['point']):
                pre = None
            out.append(run_point(spec, draws, seconds, counts, hazard, regcols, pre, samples, engine_stats))
        except Exception as e:  # noqa: BLE001
            out.append((dict(task=spec['task'], case=spec['case'], point=spec.get('fstore_point', spec['point']),
                             point_group=spec.get('point_group'), error='%s: %s' % (type(e).__name__, e),
                             trace=traceback.format_exc()[-800:]), []))
            pre = None
    if ADM_STATS is not None:
        with open('%s.%d.%d' % (os.environ['ADM_STATS'], os.getpid(), time.time_ns()), 'w') as f:
            json.dump([[list(k), v] for k, v in ADM_STATS.items()], f)
        ADM_STATS.clear()
    if prof is not None:
        prof.disable()
        prof.dump_stats('%s.%d.%d' % (os.environ['PROFILE'], os.getpid(), time.time_ns()))
    if GC_TUNE:  # a point's session sits in a cycle, and the tuned collector would hold many of them
        import gc
        pre = None
        gc.collect()
    return out


def tally(rows):
    c = collections.Counter()
    for r in rows:
        if r.get('gold'):
            continue
        c.update({'try:' + k: v for k, v in (r.get('tries') or {}).items()})
        if r.get('fail'):
            c['fail:' + re.sub(r'\d+', 'k', r['fail'].split(':')[0])] += 1
        elif r.get('x') is None:
            c['no_x'] += 1
        else:
            fired = bool((r.get('static') or {}).get('matches'))
            c['static'] += fired
            c['empty'] += bool(r['x'].get('empty_all'))
            c['done'] += 1
    return c


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--points', type=int, default=50)
    ap.add_argument('--draws', type=int, default=200)
    ap.add_argument('--seconds', type=float, default=20)
    ap.add_argument('--jobs', type=int, default=2)
    ap.add_argument('--kind', default='RULE', choices=('RULE', 'DET'))
    ap.add_argument('--groups', default='', help='comma-separated point groups (DET, output, RULE depth 1/2/3+, INIT port); --points of each')
    ap.add_argument('--samples', action='store_true', help='also write the study-sample-v1 records (samples.jsonl.zst, golds.jsonl.zst)')
    ap.add_argument('--per-task', type=int, default=1, help='points of a task in a point group, at most')
    ap.add_argument('--split', default='dev', choices=('dev', 'holdout'), help="the tasks whose points are drawn; the prior and hazards are always dev's")
    ap.add_argument('--engine-stats', action='store_true', help="each point's info gives its CPU ms per engine phase (`engine`); the engine's collection of them costs time")
    a = ap.parse_args()
    if ANCESTOR_PREFIX and a.samples:
        ap.error('--samples writes records in the slots of the written program, so it does not take ANCESTOR_PREFIX=1')
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, 'fstore.txt'), 'w') as f:  # the feature-store points the run's points and gold come from, for its scorers
        f.write(FSTORE)
    pp = os.path.join(a.out, 'points.jsonl.zst')
    done = set()
    if os.path.exists(pp):
        for r in iter_json(pp):
            done.add((r['task'], r['case'], tuple(r['point'])))
    names_path = os.path.join(a.out, 'names.json')
    names_all = json.load(open(names_path)) if os.path.exists(names_path) else {}
    dev = [t for t, s in json.load(open(SPLITS)).items() if s == 'dev']
    groups = set(filter(None, a.groups.split(',')))
    tasks = dev if a.split == 'dev' else [t for t, s in json.load(open(SPLITS)).items() if s == a.split]
    picked = list(pick_groups(a.points, tasks, groups, a.per_task) if groups else pick_points(a.points, tasks, a.kind))
    kinds = {s.get('kind', a.kind) for s in picked}
    prior, hazard = {}, {}
    if 'RULE' in kinds:
        prior['RULE'] = Prior()
        hazard['RULE'], _ = body_hazard(dev)
        ghaz = group_hazards(dev) if HAZARD_GROUP else {}
    else:
        ghaz = {}
    if 'INIT' in kinds:
        bodies = gold_port_bodies(dev)
        prior['INIT'] = Prior(bodies)
        hazard['INIT'] = kind_hazard(bodies)
    if 'DET' in kinds:
        bodies = gold_bodies(dev, 'DET')
        prior['DET'] = Prior(bodies)
        hazard['DET'] = kind_hazard(bodies)
    regcols = registry_columns()
    specs = [s for s in picked if (s['task'], s['case'], tuple(s.get('fstore_point', s['point']))) not in done]
    if os.environ.get('STEMS'):  # STEMS=path: only the points of the (task, case) pairs in path, one tab-separated pair a line; a third field (the point as JSON, [24, 0]) limits it to that point
        stems = {tuple(l.rstrip('\n').split('\t')) for l in open(os.environ['STEMS']) if l.strip()}
        specs = [s for s in specs if any(x[:2] == (s['task'], s['case']) and (len(x) < 3 or x[2] == json.dumps(s['point'])) for x in stems)]
    if os.environ.get('SKIP_TASKS'):  # SKIP_TASKS=path: leave out the tasks in path, one task id a line
        skip = {l.strip() for l in open(os.environ['SKIP_TASKS']) if l.strip()}
        specs = [s for s in specs if s['task'] not in skip]
    if os.environ.get('SKIP_POINTS'):  # SKIP_POINTS=path: leave out the points of the runs in path, one output directory a line
        for d in filter(None, map(str.strip, open(os.environ['SKIP_POINTS']))):
            done |= {(r['task'], r['case'], tuple(r['point'])) for r in iter_json(os.path.join(d, 'points.jsonl.zst'))}
        specs = [s for s in specs if (s['task'], s['case'], tuple(s.get('fstore_point', s['point']))) not in done]
    if ANCESTOR_PREFIX:
        specs = [ancestor_spec(s) for s in specs]
    print('%s points %d, static mask %s, registry relations %d' % (
        a.groups or a.kind, len(specs), STATIC_MASK, len(regcols)), flush=True)
    t0 = time.time()
    total = collections.Counter()
    gp, sp = os.path.join(a.out, 'golds.jsonl.zst'), os.path.join(a.out, 'samples.jsonl.zst')
    golds = {sl.digest(g) for g in iter_json(gp)} if a.samples and os.path.exists(gp) else set()  # gold_refs already written
    sids = {r['sample_id'] for r in iter_json(sp)} if a.samples and os.path.exists(sp) else set()  # a repeated draw is one sample
    with (cf.ProcessPoolExecutor(a.jobs) as ex, JsonlWriter(pp) as pf, JsonlWriter(os.path.join(a.out, 'draws.jsonl.zst')) as df,
          contextlib.ExitStack() as files):
        gf, sf = (files.enter_context(JsonlWriter(f)) for f in (gp, sp)) if a.samples else (None, None)
        cutf = files.enter_context(JsonlWriter(os.path.join(a.out, 'cuts.jsonl.zst'))) if PREFIX_DRAWS else None
        relf = files.enter_context(JsonlWriter(os.path.join(a.out, 'relrows.jsonl.zst'))) if REL_ROWS else None
        chf = files.enter_context(JsonlWriter(os.path.join(a.out, 'choices.jsonl.zst'))) if CHOICE_ROWS else None
        vcf = files.enter_context(JsonlWriter(os.path.join(a.out, 'valcuts.jsonl.zst'))) if VAL_CUTS else None
        coptf = files.enter_context(JsonlWriter(os.path.join(a.out, 'cutopts.jsonl.zst'))) if CUT_OPTS else None
        pcf = files.enter_context(JsonlWriter(os.path.join(a.out, 'prefcuts.jsonl.zst'))) if PREFIX_CUTS else None
        comp = compound_counts(dev) if 'RULE' in kinds else {}

        @functools.lru_cache(maxsize=None)  # one per task and kind: every point of the run would hold its own copy
        def counts_of(task, kind):
            c = prior[kind].held_out(task)
            c['compound'] = held_out(comp, task) if comp and kind == 'RULE' else None
            return c
        progs = collections.defaultdict(list)  # points of one gold program share its prefix, at most PROG_CHUNK to a job
        for s in specs:
            progs[s['task'], s['case'], s['gold_sexp']].append((s, counts_of(s['task'], s.get('kind', a.kind)), ghaz.get((s.get('point_group') or {}).get('point_group')) if s.get('kind', a.kind) == 'RULE' and ghaz.get((s.get('point_group') or {}).get('point_group')) else hazard[s.get('kind', a.kind)]))
        chunks = [v[k:k + PROG_CHUNK] for v in progs.values() for k in range(0, len(v), PROG_CHUNK)]
        chunks.sort(key=lambda c: -sum(j[0]['point'][0] + a.seconds for j in c))  # the longest first, for a short tail
        futs = {ex.submit(worker, (c, a.draws, a.seconds, regcols, a.samples, a.engine_stats)) for c in chunks}

        def done_points():  # a finished job's future leaves futs, so its rows are freed once written
            for fu in cf.as_completed(futs):
                futs.discard(fu)
                yield from fu.result()
        for i, (info, rows) in enumerate(done_points(), 1):
            for r in rows:
                df.write(r)
            df.flush()  # a frame per point, so a reader sees each point as it ends
            for r in info.pop('prefix_rows', None) or []:
                cutf.write(r)
            if PREFIX_DRAWS:
                cutf.flush()
            for r in info.pop('rel_rows', None) or []:
                relf.write(r)
            if REL_ROWS:
                relf.flush()
            for r in info.pop('choice_rows', None) or []:
                chf.write(r)
            if CHOICE_ROWS:
                chf.flush()
            for r in info.pop('valcut_rows', None) or []:
                vcf.write(r)
            if VAL_CUTS:
                vcf.flush()
            for r in info.pop('prefcut_rows', None) or []:
                pcf.write(r)
            if PREFIX_CUTS:
                pcf.flush()
            for r in info.pop('cutopt_rows', None) or []:
                coptf.write(r)
            if CUT_OPTS:
                coptf.flush()
            gold_line, samples = info.pop('gold_line', None), info.pop('samples', [])
            if samples and samples[0]['gold_ref'] not in golds:  # a gold line goes before the first sample that refers to it
                gf.write(gold_line)
                gf.flush()
                golds.add(samples[0]['gold_ref'])
            for r in samples:
                if r['sample_id'] not in sids:
                    sids.add(r['sample_id'])
                    sf.write(r)
            if sf:
                sf.flush()
            names = info.pop('names', None)
            if names is not None:
                names_all['%s|%s|%s' % (info['task'], info['case'], json.dumps(info['point']))] = names
                with open(names_path + '.tmp', 'w') as nf:  # replaced whole, so a stop mid-write leaves the last full file
                    json.dump(names_all, nf)
                os.replace(names_path + '.tmp', names_path)
            c = tally(rows)
            c.update({'rc_error:' + k: v for k, v in (info.get('rc_errors') or {}).items()})
            total.update(c)
            info['tally'] = dict(c)
            g = rows[0] if rows else {}
            info['gold'] = dict(fail=g.get('fail'), empty=(g.get('x') or {}).get('empty_inputs'),
                                static=bool((g.get('static') or {}).get('matches')), safe=g.get('prefix_safe'))
            pf.write(info)
            pf.flush()
            el = time.time() - t0
            print('[%d/%d %.0fs eta %.0fs] %s %s %s %s draws=%s %.1fs gold=%s %s' % (
                i, len(specs), el, el / i * (len(specs) - i), info['task'], info['case'], info['point'], info.get('error', ''),
                info.get('draws'), info.get('seconds', 0), info['gold'], dict(c)), flush=True)
    print('TOTAL', dict(total), flush=True)


if __name__ == '__main__':
    main()
