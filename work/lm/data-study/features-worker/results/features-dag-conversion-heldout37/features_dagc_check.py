#!/usr/bin/env python
"""Checks of the fact layer. Writes fact-layer-check.txt.

  features_dagc_env.sh 1 features_dagc_check.py [NTASKS]

1. check_columns and check_tokens refuse each banned name and pass each allowed one.
2. On NTASKS fit tasks (100), a form whose bodies, OR branches, ports and lines are shuffled, with the marks dropped and the labels renamed, gives the same multiset of pick_facts over its picks (each pair of a downset and an atom
   that follows it in one of the form's orders; forms with at most 24 orders; the scope is the form's ancestors).
3. Power: on the same shuffles, the written facts (the index of an atom and the relation before it in written order) change on some forms.
"""
import collections
import random
import re
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import features_dagc_lib as L  # noqa: E402

L.setup_engine(L.HELD_CORPUS, L.BASE / 'models-base')
import features_dag_order as D  # noqa: E402
import features_dagc_facts as F  # noqa: E402
import features_ofree_facts as FL  # noqa: E402
import features_ofree_text as T  # noqa: E402

MAX_ORDERS = 24
BANNED_COLUMNS = ['ord', 'k', 'last_derived', 'last_lib', 'last_not', 'last', 'recency', 'recency_frac', 'prevform1', 'readers', 'kept_reads', 'scopereads:x', 'steer', 'rank', 'der_rank', 'opt_readers1', 'q_live']
BANNED_TOKENS = ['last:input', 'k:3', 'ord:2', 'recency:1', 'prevform1:x', 'scopereads:x', 'kept_reads:2', 'steer:1', 'opt_readers2', 'rank:1', 'first:input', 'position:1', 'before:input']


def scramble_form(line, rng):
    """A form with its body's atoms, its OR branches, its INIT's ports and key group's ports in a random order, recursively."""
    p = T.sexp(line)[0]

    def conj(c):
        marks = [x for x in c if D.is_clause_mark(x)]  # (ONE) and (SET) stay after the atoms
        c = [atom(x) for x in c if not D.is_clause_mark(x)]
        rng.shuffle(c)
        return c + marks

    def atom(a):
        if a and a[0] in T.COMPOUND:
            rest = [conj(x) if T.is_conj(x) else x for x in a[1:]]
            if a[0] == 'OR':
                rng.shuffle(rest)
            return [a[0]] + rest
        return a

    if p[0] in ('RULE', 'DET') and len(p) > 2 and isinstance(p[2], list):
        return p[:2] + conj(p[2:])
    if p[0] == 'INIT':
        rest = []
        for x in p[3:]:
            if x[0] == 'key':
                ports = [q[:2] + conj(q[2:]) for q in x[2:]]
                rng.shuffle(ports)
                rest.append(['key', conj(x[1])] + ports)
            else:
                rest.append(x[:2] + conj(x[2:]))
        rng.shuffle(rest)
        return p[:3] + rest
    return p


def port_rank(dag, reg):
    """A sort key for a form's own bodies: the key group first, then the ports in the component's order of the registry."""
    comp = dag.proposer if False else (D.parse(dag.text)[2] if dag.kind == 'INIT' else '')
    ports = reg.ports.get(comp, [])
    return lambda b: (0 if b.role == 'key' else 1, ports.index(b.role[5:]) if b.role[5:] in ports else 99, b.role)


def picks_of(text, reg):
    """Multiset keys: for each order of the form (at most MAX_ORDERS), each step's pick, as (downset ids, atom id, pick dict)."""
    dag = D.FormDag(text)
    n = dag.count_orders()
    if n is None or n > MAX_ORDERS:
        return dag, None
    seen = {}
    for order in dag.all_orders():
        leaves = dag.leaves(order, port_rank(dag, reg))
        for j, a in enumerate(leaves):
            seen[frozenset(leaves[:j]), a] = None
    return dag, list(seen)


def fact_multiset(text, scope_lines, reg):
    dag, ps = picks_of(text, reg)
    if ps is None:
        return None
    prog = F.program_of(scope_lines, reg)
    rec = F.scope_record(prog)
    out = collections.Counter()
    for dset, a in ps:
        p = F.pick_of(dag, dset, a)
        p['ctx'] = F.ctx_of(p['atoms'], prog)
        out[frozenset(F.pick_facts(p, prog, 'dag', rec))] += 1
    return out


def written_multiset(text):
    """The old written facts: at each step of the text's own atom order, the step's index and the relation of the atom just before."""
    dag = D.FormDag(text)
    leaves = dag.leaves(dag.written_order())
    out = collections.Counter()
    for j, a in enumerate(leaves):
        prev = dag.atoms[leaves[j - 1]].tree[0] if j else ''
        out[('k:%d' % j, 'last:' + str(prev), frozenset(leaves[:j]) and 0)] += 1
    return out


def main():
    nt = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    out = []
    t0 = time.time()
    for bad in BANNED_COLUMNS:
        try:
            F.check_columns([bad])
        except F.BannedFact:
            continue
        raise AssertionError('column passed: ' + bad)
    for bad in BANNED_TOKENS:
        try:
            F.check_tokens([bad])
        except F.BannedFact:
            continue
        raise AssertionError('token passed: ' + bad)
    F.check_columns(F.ALLOWED_COLUMNS + F.CONTENT_COLUMNS + ['type_Color', 'col2_in_scope', 'scope_n_RULE', 'grid_h'])
    F.check_tokens(['prefix:input', 'scope:RULE', 'place:RULE', 'ddepth:2', 'in:input', 'join:a~b'])
    out.append('refused %d banned columns and %d banned tokens; passed each allowed column pattern and token prefix' % (len(BANNED_COLUMNS), len(BANNED_TOKENS)))
    reg = T.Registry()
    txt = open(T.REGISTRY, encoding='utf8').read()
    caps = set(re.findall(r'^\((?:component|proposer) (\w+)', txt, re.M)) | {'RULE', 'DET', 'INIT', 'OUT', 'RIGID_DET', 'CHOOSE', 'NOT', 'OR', 'ALL', 'IF', 'ONE', 'SET'}
    tasks = L.fit_tasks()
    tasks = tasks[::max(1, len(tasks) // nt)][:nt]
    rng = random.Random(0)
    forms = skipped = bad_forms = moved = same = 0
    examples = []
    for t in tasks:
        lines = L.fit_gold([t])[t]
        names = {}
        scr = [FL.strip_marks(FL.unparse(scramble_form(x, rng)), caps, names) if not x.startswith('(OUT') else x for x in lines]
        order = list(range(len(lines)))
        rng.shuffle(order)
        scr_shuffled = [scr[i] for i in order]
        prog_a, prog_b = D.ProgramDag(lines), D.ProgramDag(scr_shuffled)
        for i, text in enumerate(lines):
            kind = L.kind_of(text)
            if kind not in L.KINDS:
                continue
            key = D.parse(text)[1]
            a = fact_multiset(text, prog_a.texts(sorted(prog_a.ancestors(key))), reg)
            if a is None:
                skipped += 1
                continue
            b = fact_multiset(scr[i], prog_b.texts(sorted(prog_b.ancestors(key))), reg)
            forms += 1
            if a != b:
                bad_forms += 1
                if len(examples) < 3:
                    examples.append((t, i, text[:200], scr[i][:200]))
            wa, wb = written_multiset(text), written_multiset(scr[i])
            moved += wa != wb
            same += wa == wb
    out.append('%d fit tasks, %d forms compared (%d skipped with more than %d orders): pick_facts differ on %d forms %s' % (len(tasks), forms, skipped, MAX_ORDERS, bad_forms, examples))
    out.append('the check has power: on the same shuffles, the written facts (index and previous relation) change on %d forms and stay on %d' % (moved, same))
    out.append('%.0f s' % (time.time() - t0))
    print('\n'.join(out), flush=True)
    with open(L.OUT_DIR / 'fact-layer-check.txt', 'w') as f:
        f.write('\n'.join(out) + '\n')


if __name__ == '__main__':
    main()
