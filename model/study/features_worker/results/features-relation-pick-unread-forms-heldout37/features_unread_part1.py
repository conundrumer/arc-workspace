"""Gold's earlier forms as found: one row per form of the 37 held tasks, with one entry per atom, from census-base.jsonl and points-base.json. Stdlib only. No engine: every number comes from the census's rows and gold's text.

  python3 features_unread_part1.py

Writes part1-forms.jsonl in this folder, one row per form, flushed. A rerun skips the forms that have a row. It prints a rate and an ETA.

A form with no census row (kinds CHOOSE, RIGID_DET, OUT) gets a row with census=False: its atoms are the reads of its text, in text order, with no bits.
"""
import collections
import json
import os
import time

import features_unread_lib as L

HERE = os.path.dirname(os.path.abspath(__file__)) + '/'
OUT = HERE + 'part1-forms.jsonl'


def sizes(sets, parents):
    """{set: [count of forms in the scope of all earlier forms, count in the parents scope]}."""
    p = set(parents)
    return {k: [len(v), sum(x in p for x in v)] for k, v in sets.items()}


def atoms_of(gold, j, before, parents):
    """The entries of form j's atoms, from the census row of each scope."""
    st = L.Sets(gold, j)
    seen = set()
    names = set()
    out = []
    for a, ((ctx, text, bits), det) in enumerate(zip(before['atoms'], before['detail'])):
        name, neg = L.relation_of(text)
        line = gold.form_of_slot(name)
        par = None
        if parents is not None and a < len(parents['atoms']):
            par = parents['detail'][a]['cur']
        sets = st.at(seen)
        e = dict(atom=a, k=det['k'], ctx=ctx, text=text, atom_bits=bits, neg=neg, rel=name, rel_bits=det['cur'].get('relation'), op_bits=det['cur'].get('relation (op)'), rel_bits_parents=par.get('relation') if par is not None else None,
                 op_bits_parents=par.get('relation (op)') if par is not None else None, n_scope=[len(st.scope), len(st.parents)], n=sizes(sets, st.parents))
        if line is not None and line != j:
            e.update(target=line, target_kind=gold.kind[line], repeat=name in names, same_form=line in seen, inside={k: line in v for k, v in sets.items()})
            seen.add(line)
        elif line == j:
            e['own_slot'] = True
        names.add(name)
        out.append(e)
    return out


def text_atoms(gold, j):
    """The reads of a form that the census has no row for."""
    st = L.Sets(gold, j)
    seen = set()
    out = []
    for a, line in enumerate(gold.reads[j]):
        if line >= j:
            continue
        sets = st.at(seen)
        out.append(dict(atom=a, k=None, ctx='text', text=gold.head.get(line), atom_bits=None, neg=None, rel=gold.head.get(line), rel_bits=None, op_bits=None, rel_bits_parents=None, op_bits_parents=None,
                        n_scope=[len(st.scope), len(st.parents)], n=sizes(sets, st.parents), target=line, target_kind=gold.kind[line], repeat=line in seen, same_form=line in seen, inside={k: line in v for k, v in sets.items()}))
        seen.add(line)
    return out


def main():
    golds = {p['task']: L.Gold(L.lines_of(p['gold_sexp'])) for p in json.load(open(L.BASE + 'points-base.json'))}
    cen = collections.defaultdict(dict)
    for x in open(L.BASE + 'census-base.jsonl'):
        r = json.loads(x)
        cen[(r['task'], r['line'])][r['scope']] = r
    done = set()
    if os.path.exists(OUT):
        done = {(r['task'], r['line']) for r in map(json.loads, open(OUT))}
    todo = [(t, j) for t in L.held_tasks() for j in range(len(golds[t].lines)) if (t, j) not in done]
    print('%d forms to do, %d done' % (len(todo), len(done)), flush=True)
    t0 = time.time()
    misfit = 0
    with open(OUT, 'a') as out:
        for c, (t, j) in enumerate(todo, 1):
            g = golds[t]
            kind = g.kind[j]
            rows = cen.get((t, j))
            if rows:
                b, p = rows['before'], rows['parents']
                atoms = atoms_of(g, j, b, p)
                got = {a['target'] for a in atoms if 'target' in a}
                extra = sorted(got - set(g.reads[j]))
                aligned = len(b['atoms']) == len(p['atoms']) and all(x[1].split(' ')[0] == y[1].split(' ')[0] or x[1].startswith('(&') or x[1].startswith('(NOT (&') for x, y in zip(b['atoms'], p['atoms']))
                row = dict(task=t, line=j, kind=kind, census=True, valid=not b['bad'] and b['dead'] is None and not b['left'], valid_parents=not p['bad'] and p['dead'] is None and not p['left'], total=b['total'], total_parents=p['total'], bad=b['bad'], dead=b['dead'], nscope=b['nscope'], nscope_parents=p['nscope'],
                           reads_in_text=sorted(set(g.reads[j])), reads_in_atoms=sorted(got), extra=extra, aligned=aligned, atoms=atoms)
                misfit += bool(extra)
            else:
                row = dict(task=t, line=j, kind=kind, census=False, valid=False, valid_parents=False, total=None, total_parents=None, bad=[], dead=None, nscope=None, nscope_parents=None, reads_in_text=sorted(set(g.reads[j])), reads_in_atoms=[], extra=[], aligned=True, atoms=text_atoms(g, j))
            out.write(json.dumps(row) + '\n')
            out.flush()
            if c % 100 == 0 or c == len(todo):
                rate = c / max(time.time() - t0, 1e-9)
                print('%d of %d, %.0f forms/s, ETA %.1f s' % (c, len(todo), rate, (len(todo) - c) / rate), flush=True)
    print('forms whose atoms read a form that their text does not read: %d' % misfit)


if __name__ == '__main__':
    main()
