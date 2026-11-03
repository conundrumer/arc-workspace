"""The reader: turns the rows of this folder into per-pick-unread.tsv, the tables, summary.json and partial.md. Stdlib only. Reads the rows that exist, so it runs on a partial walk.

  python3 features_unread_read.py

No number here is fit to a held row: BAR is the brief's 25 bits, and each w comes from fit.json, which reads non-held walks only.
"""
import collections
import json
import math
import os
import random
import statistics as st

import features_unread_lib as L

HERE = os.path.dirname(os.path.abspath(__file__)) + '/'
BAR = L.BAR
READ_SETS = ('unread_later', 'unread_before', 'unread_so_far')
NAMES = {'unread_gold': 'read by no form of gold', 'unread_later': 'read by no other form of gold', 'unread_before': 'read by no form before this form', 'unread_so_far': 'read by no form before this pick'}
KINDS = ('RULE', 'INIT', 'DET')
HEADLINE_ARM = 'control_search'
PREFIX = {'control_search': 'control', 'factored_search': 'factored'}


def fmt(x, d=2):
    return '-' if x is None else ('%.*f' % (d, x))


def table(head, rows):
    out = ['| ' + ' | '.join(head) + ' |', '|' + '---|' * len(head)]
    out += ['| ' + ' | '.join(str(c) for c in r) + ' |' for r in rows]
    return '\n'.join(out) + '\n'


def position(k):
    return {1: 'first', 2: 'second', 3: 'third'}.get(k, 'later')


def load():
    forms = [json.loads(x) for x in open(HERE + 'part1-forms.jsonl')]
    walk = {}
    if os.path.exists(HERE + 'walk-held-before.jsonl'):
        for x in open(HERE + 'walk-held-before.jsonl'):
            r = json.loads(x)
            walk[(r['task'], r['line'])] = r
    pool = {a: {} for a in L.ARMS}
    for x in open(HERE + 'pool-tasks.jsonl'):
        r = json.loads(x)
        pool[r['arm']][r['task']] = r
    return forms, walk, pool


def attach_walk(f, g, walk):
    """Adds to each atom of a form with a walk row: `o`, the relation options at its relation pick in each set, or at its op pick where it has only that."""
    w = walk.get((f['task'], f['line']))
    if w is None or not f['census']:
        return False
    st_ = L.Sets(g, f['line'])
    seen = set()
    picks = w['picks']
    i = 0
    ok = True
    for a in f['atoms']:
        sets = st_.at(seen)
        for key in ('op', 'rel'):
            if (key == 'op' and a['op_bits'] is None) or (key == 'rel' and a['rel_bits'] is None):
                continue
            if i >= len(picks):
                ok = False
                break
            p = picks[i]
            i += 1
            if key == 'rel' and p['gold'] != a['rel']:
                ok = False
            forms_ = [g.form_of_slot(n) for n, _ in p['rels']]
            a['o_' + key] = {k: sum(x in set(sets[k]) for x in forms_) for k in L.SETS}
            a['o_all_' + key] = len(forms_)
            if key == 'rel':
                a['offered'] = a['rel'] in {n for n, _ in p['rels']} if a.get('target') is not None else None
        if 'target' in a:
            seen.add(a['target'])
    return ok


def picks_of(rows):
    """The derived picks with bits, over valid forms of the kinds with a census row."""
    return [(f, a) for f in rows if f['census'] and f['valid'] for a in f['atoms'] if 'target' in a and a['rel_bits'] is not None]


def size_rows(rows):
    out = []
    groups = [('all', lambda f, a: True)] + [(k, lambda f, a, k=k: f['kind'] == k) for k in KINDS]
    groups += [('%s, %s' % (k, p), lambda f, a, k=k, p=p: (k == 'all' or f['kind'] == k) and position(a['k']) == p) for k in ('all',) + KINDS for p in ('first', 'second', 'third', 'later')]
    all_picks = picks_of(rows)
    for name, keep in groups:
        ps = [(f, a) for f, a in all_picks if keep(f, a)]
        if not ps:
            continue
        r = dict(group=name, picks=len(ps), tasks=len({f['task'] for f, _ in ps}), forms=len({(f['task'], f['line']) for f, _ in ps}), median_scope=st.median(a['n_scope'][0] for _, a in ps), bits=sum(a['rel_bits'] for _, a in ps) / len(ps))
        for k in L.SETS:
            ns = [a['n'][k][0] for _, a in ps]
            inside = [a for _, a in ps if a['inside'][k]]
            r[k] = dict(median=st.median(ns), mean=sum(ns) / len(ns), empty=sum(x == 0 for x in ns), inside=len(inside), share=len(inside) / len(ps), bits_inside=sum(a['rel_bits'] for a in inside) / len(inside) if inside else None, log2_inside=sum(math.log2(a['n'][k][0]) for a in inside) / len(inside) if inside else None,
                        log2_all=sum(math.log2(n) for n in ns if n) / max(1, sum(1 for n in ns if n)))
        out.append(r)
    return out


def over(rows, valid_key='valid', total='total'):
    """{form key: total} of forms with bits; forms with no valid bits go in `none`."""
    t, none = {}, set()
    for f in rows:
        if f['kind'] == 'OUT':
            continue
        k = (f['task'], f['line'])
        if f['census'] and f[valid_key]:
            t[k] = f[total]
        else:
            none.add(k)
    return t, none


def reach(t, none, tasks):
    """(forms under BAR, tasks whose every form has bits and is under BAR, list of those tasks)."""
    worst, missing = collections.defaultdict(float), {x for x, _ in none}
    for (x, _), v in t.items():
        worst[x] = max(worst[x], v)
    under = sorted(x for x in tasks if x not in missing and worst[x] < BAR)
    return sum(v < BAR for v in t.values()), len(under), under


def oracle(rows, name, scope=0):
    """Form totals with each pick inside the set paying log2 of the set, all others paying what they pay now."""
    t, none = over(rows, 'valid' if scope == 0 else 'valid_parents', 'total' if scope == 0 else 'total_parents')
    out = dict(t)
    n = 0
    for f in rows:
        k = (f['task'], f['line'])
        if k not in out:
            continue
        for a in f['atoms']:
            if 'target' in a and a['inside'][name]:
                bits = a['rel_bits'] if scope == 0 else a['rel_bits_parents']
                c = a['n'][name][scope]
                if bits is None or c == 0:  # the target is outside the parents scope's set, which can't be for a form that reads it
                    continue
                out[k] += math.log2(c) - bits
                n += 1
    return out, none, n


def oracle_options(rows, name):
    """As oracle, scope of all earlier forms, with a pick inside the set paying log2 of the relation options of the set at that pick. Forms with a walk row only."""
    t, none = over(rows)
    out, base = {}, {}
    n = 0
    for f in rows:
        k = (f['task'], f['line'])
        if k not in t:
            continue
        v = t[k]
        ok = True
        for a in f['atoms']:
            if a['rel_bits'] is None:
                continue
            if 'o_rel' not in a:
                ok = False
                break
            if 'target' in a and a['inside'][name] and a.get('offered'):
                v += math.log2(a['o_rel'][name]) - a['rel_bits']
                n += 1
        if ok:
            out[k], base[k] = v, t[k]
    return out, base, n


def by_kind_under(t, rows):
    kinds = {(f['task'], f['line']): f['kind'] for f in rows}
    c = collections.Counter()
    for k, v in t.items():
        if v < BAR:
            c[kinds[k]] += 1
    return dict(c)


def mix_form(f, name, w, variant):
    """(saved at derived picks, count of derived picks, saved at all relation picks, count, new total), or None for a form that this variant can't read."""
    dsave = dn = asave = an = 0
    for a in f['atoms']:
        n = a['n'][name][0]
        for key, bits in (('op', a['op_bits']), ('rel', a['rel_bits'])):
            if bits is None:
                continue
            c = n
            if variant == 'options':
                c = a.get('o_' + key, {}).get(name)
                if c is None:
                    return None
            inside = key == 'rel' and 'target' in a and a['inside'][name] and (variant == 'forms' or bool(a.get('offered')))
            new = L.mix_bits(bits, w, c, inside)
            asave += bits - new
            an += 1
            if key == 'rel' and 'target' in a:
                dsave += bits - new
                dn += 1
    return dsave, dn, asave, an, f['total'] - asave


def bootstrap(by_task, reps=10000, seed=0):
    rng = random.Random(seed)
    tasks = sorted(by_task)
    vals = []
    for _ in range(reps):
        s = n = 0.0
        for _ in tasks:
            a, b = by_task[rng.choice(tasks)]
            s += a
            n += b
        vals.append(s / n if n else 0.0)
    vals.sort()
    return vals[int(.025 * reps)], vals[int(.975 * reps)]


def mixture(rows, fit, tasks):
    out = []
    t0, none = over(rows)
    for name in READ_SETS:
        for variant in ('forms', 'options'):
            w = fit['w']['test']['%s:%s' % (name, variant)]['w']
            use = []
            t = {}
            by_task = collections.defaultdict(lambda: [0.0, 0])
            ds = dn = aS = an = 0
            skipped = 0
            for f in rows:
                k = (f['task'], f['line'])
                if k not in t0:
                    continue
                r = mix_form(f, name, w, variant)
                if r is None:
                    skipped += 1
                    continue
                t[k] = r[4]
                ds, dn, aS, an = ds + r[0], dn + r[1], aS + r[2], an + r[3]
                by_task[f['task']][0] += r[0]
                by_task[f['task']][1] += r[1]
                use.append(k)
            lo, hi = bootstrap({a: tuple(b) for a, b in by_task.items()}) if dn else (None, None)
            base = {k: t0[k] for k in use}
            ntasks_all = {x for x, _ in t0} | {x for x, _ in none}
            missing = none | ({k for k in t0} - set(use))
            forms_u, tasks_u, under = reach(t, missing, ntasks_all)
            bf, bt, _ = reach(base, missing, ntasks_all)
            out.append(dict(set=name, variant=variant, w=w, forms_read=len(use), forms_skipped=skipped, derived_picks=dn, saved_per_derived_pick=ds / dn if dn else None, ci95=[lo, hi], relation_picks=an, saved_per_relation_pick=aS / an if an else None, net_saved_per_derived_pick=aS / dn if dn else None,
                            forms_under=forms_u, forms_under_now=bf, tasks_under=tasks_u, tasks_under_now=bt, taken_under=sum(t[k] < BAR <= base[k] for k in use), pushed_over=sum(t[k] >= BAR > base[k] for k in use), tasks=under))
    return out


def pool_rows(rows, pool, tasks):
    """One row per arm and group of the derived picks of the run's tasks."""
    out = []
    picks = [(f, a) for f, a in picks_of(rows) if f['task'] not in L.NOT_IN_RUN]
    for arm in L.ARMS:
        for gname, keep in [('all', lambda f, a: True)] + [(k, lambda f, a, k=k: f['kind'] == k) for k in KINDS]:
            ps = [(f, a) for f, a in picks if keep(f, a)]
            read, found, withnode, rule_for_init = [], [], [], 0
            source = collections.Counter()
            for f, a in ps:
                p = pool[arm].get(f['task'])
                if p is None:
                    continue
                t = p['targets'][a['target']] if a['target'] < len(p['targets']) and p['targets'][a['target']]['line'] == a['target'] else next((x for x in p['targets'] if x['line'] == a['target']), None)
                source[(t or {}).get('source')] += 1
                if t is None or t.get('found') is None:
                    continue
                read.append((f, a, p, t))
                if t['found']:
                    found.append((f, a, p, t))
                    if 'node' in t:
                        withnode.append((f, a, p, t))
                        rule_for_init += a['target_kind'] == 'INIT' and t.get('node_kind') != 'INIT'
            r = dict(arm=arm, group=gname, picks=len(ps), source={str(k): v for k, v in source.items()}, readable=len(read), found=len(found), found_share=len(found) / len(read) if read else None, with_node=len(withnode), init_target_by_other_kind=rule_for_init,
                     target_forms=len({(f['task'], a['target']) for f, a, _, _ in read}), target_forms_found=len({(f['task'], a['target']) for f, a, _, _ in found}))
            if read:
                ends = [p['unread'] for _, _, p, _ in read]
                r.update(unread_end_median=st.median(ends), forms_end_median=st.median(p['forms'] for _, _, p, _ in read), log2_end_mean=sum(math.log2(x) for x in ends) / len(ends), bits_read_mean=sum(a['rel_bits'] for _, a, _, _ in read) / len(read))
            if found:
                r.update(found_seconds_median=st.median(t['seconds'] for *_, t in found), unread_at_found_median=st.median(t['unread_at_found'] for *_, t in found), forms_at_found_median=st.median(t['forms_at_found'] for *_, t in found),
                         log2_at_found_mean=sum(math.log2(max(1, t['unread_at_found'])) for *_, t in found) / len(found), log2_end_found_mean=sum(math.log2(p['unread']) for _, _, p, _ in found) / len(found), bits_found_mean=sum(a['rel_bits'] for _, a, _, _ in found) / len(found))
            if withnode:
                un = [x for x in withnode if not x[3]['read_end']]
                r.update(unread_end_inside=len(un), unread_end_inside_share=len(un) / len(withnode), read_at_found=sum(x[3]['read_at_found'] for x in withnode), readers_median=st.median(x[3]['readers_end'] for x in withnode),
                         bits_inside_mean=sum(a['rel_bits'] for _, a, _, _ in un) / len(un) if un else None, log2_end_inside_mean=sum(math.log2(p['unread']) for _, _, p, _ in un) / len(un) if un else None, cheaper_than_log2=sum(a['rel_bits'] < math.log2(p['unread']) for _, a, p, _ in un), log2_at_found_inside_mean=sum(math.log2(max(1, t['unread_at_found'])) for *_, t in un) / len(un) if un else None)
            out.append(r)
    return out


def tsv(forms, golds, pool):
    cols = ['task', 'form_line', 'form_kind', 'form_head', 'form_valid', 'has_bits', 'form_bits', 'form_bits_parents', 'atom_index', 'atom_k', 'position', 'place', 'negated', 'repeat_relation', 'repeat_form', 'relation', 'target_line', 'target_kind', 'target_head', 'bits_relation', 'bits_relation_parents', 'bits_not', 'bits_atom',
            'n_scope', 'n_scope_parents']
    for k in L.SETS:
        cols += ['n_%s' % k, 'n_%s_parents' % k]
    cols += ['in_%s' % k for k in L.SETS]
    cols += ['options_relation', 'options_unread_later', 'options_unread_before', 'options_unread_so_far', 'target_offered']
    pc = ['source', 'found', 'found_seconds', 'found_draw', 'covering_node', 'covering_kind', 'forms_at_found', 'unread_at_found', 'forms_end', 'unread_end', 'in_unread_at_found', 'in_unread_end', 'readers_end']
    for arm in L.ARMS:
        cols += ['%s_%s' % (PREFIX[arm], c) for c in pc]
    cols.append('atom_text')
    with open(HERE + 'per-pick-unread.tsv', 'w') as out:
        out.write('\t'.join(cols) + '\n')
        n = 0
        for f in forms:
            g = golds[f['task']]
            for a in f['atoms']:
                if 'target' not in a:
                    continue
                k = a['k']
                d = dict(task=f['task'], form_line=f['line'], form_kind=f['kind'], form_head=g.head.get(f['line']), form_valid=int(f['valid']), has_bits=int(a['rel_bits'] is not None), form_bits=f['total'], form_bits_parents=f['total_parents'], atom_index=a['atom'], atom_k=k, position=position(k) if k else None, place=a['ctx'], negated=None if a['neg'] is None else int(a['neg']), repeat_relation=int(a['repeat']), repeat_form=int(a['same_form']),
                         relation=a['rel'], target_line=a['target'], target_kind=a['target_kind'], target_head=g.head.get(a['target']), bits_relation=a['rel_bits'], bits_relation_parents=a['rel_bits_parents'], bits_not=a['op_bits'], bits_atom=a['atom_bits'], n_scope=a['n_scope'][0], n_scope_parents=a['n_scope'][1], atom_text=a['text'])
                for s in L.SETS:
                    d['n_%s' % s] = a['n'][s][0]
                    d['n_%s_parents' % s] = a['n'][s][1]
                    d['in_%s' % s] = int(a['inside'][s])
                if 'o_rel' in a:
                    d.update(options_relation=a['o_all_rel'], options_unread_later=a['o_rel']['unread_later'], options_unread_before=a['o_rel']['unread_before'], options_unread_so_far=a['o_rel']['unread_so_far'], target_offered=None if a.get('offered') is None else int(a['offered']))
                for arm in L.ARMS:
                    p = pool[arm].get(f['task'])
                    t = None
                    if p is not None:
                        t = next((x for x in p['targets'] if x['line'] == a['target']), None)
                    if t is None:
                        continue
                    q = PREFIX[arm] + '_'
                    d[q + 'source'] = t.get('source')
                    d[q + 'forms_end'], d[q + 'unread_end'] = p['forms'], p['unread']
                    if t.get('found') is None:
                        continue
                    d[q + 'found'] = int(t['found'])
                    if t['found']:
                        d.update({q + 'found_seconds': t['seconds'], q + 'found_draw': t['draw'], q + 'forms_at_found': t['forms_at_found'], q + 'unread_at_found': t['unread_at_found']})
                        if 'node' in t:
                            d.update({q + 'covering_node': t['node'], q + 'covering_kind': t['node_kind'], q + 'in_unread_at_found': int(not t['read_at_found']), q + 'in_unread_end': int(not t['read_end']), q + 'readers_end': t['readers_end']})
                out.write('\t'.join('' if d.get(c) is None else str(d[c]) for c in cols) + '\n')
                n += 1
    return n, cols


def main():
    forms, walk, pool = load()
    golds = {p['task']: L.Gold(L.lines_of(p['gold_sexp'])) for p in json.load(open(L.BASE + 'points-base.json'))}
    fit = json.load(open(HERE + 'fit.json'))
    tasks = L.held_tasks()
    walked = misaligned = 0
    for f in forms:
        if (f['task'], f['line']) in walk and f['census']:
            walked += 1
            misaligned += not attach_walk(f, golds[f['task']], walk)
    count_kind = collections.Counter((f['kind'], f['census'], f['valid']) for f in forms)
    rows_n, cols = tsv(forms, golds, pool)

    S = dict(walked_forms=walked, walk_misaligned=misaligned)
    S['forms'] = {'%s census=%s valid=%s' % k: v for k, v in sorted(count_kind.items())}
    S['picks_by_kind'] = {k: sum(1 for f in forms if f['kind'] == k for a in f['atoms'] if 'target' in a) for k in sorted({f['kind'] for f in forms})}
    sizes = size_rows(forms)
    S['sizes'] = sizes
    t0, none = over(forms)
    fu, tu, under0 = reach(t0, none, tasks)
    S['under_now'] = dict(forms_with_bits=len(t0), forms_no_bits=len(none), forms_under=fu, tasks_under=tu, tasks=under0, by_kind=by_kind_under(t0, forms))
    t0p, nonep = over(forms, 'valid_parents', 'total_parents')
    fup, tup, under0p = reach(t0p, nonep, tasks)
    S['under_now_parents'] = dict(forms_with_bits=len(t0p), forms_under=fup, tasks_under=tup, tasks=under0p, by_kind=by_kind_under(t0p, forms))
    S['oracle'] = []
    for scope, name_ in ((0, 'all earlier forms'), (1, 'parents')):
        base, n0 = (t0, none) if scope == 0 else (t0p, nonep)
        for k in READ_SETS:
            t, nn, picks = oracle(forms, k, scope)
            u, ut, lst = reach(t, nn, tasks)
            S['oracle'].append(dict(scope=name_, set=k, picks_paying_log2=picks, forms_under=u, forms_under_now=reach(base, n0, tasks)[0], taken_under=sum(t[x] < BAR <= base[x] for x in t), tasks_under=ut, tasks_under_now=reach(base, n0, tasks)[1], tasks=lst, by_kind=by_kind_under(t, forms),
                                    taken=sorted('%s %d' % x for x in t if t[x] < BAR <= base[x])))
    S['oracle_options'] = []
    for k in READ_SETS:
        t, base, picks = oracle_options(forms, k)
        S['oracle_options'].append(dict(set=k, forms_read=len(t), picks_paying_log2=picks, forms_under=sum(v < BAR for v in t.values()), forms_under_now=sum(v < BAR for v in base.values()), taken_under=sum(t[x] < BAR <= base[x] for x in t)))
    S['mixture'] = mixture(forms, fit, tasks)
    S['pool'] = pool_rows(forms, pool, tasks)
    S['fit'] = fit['w']['test']
    S['bits_check'] = json.load(open(HERE + 'bits-check.json')) if os.path.exists(HERE + 'bits-check.json') else None
    if S['bits_check']:
        for v in S['bits_check'].values():
            v.pop('differ', None)
    S['pool_tasks'] = {a: dict(forms=st.median(r['forms'] for r in pool[a].values()), unread=st.median(r['unread'] for r in pool[a].values()), nodes=st.median(r['nodes'] for r in pool[a].values()), unread_share=st.median(r['unread'] / r['forms'] for r in pool[a].values()), nodes_match_done=sum(r['nodes'] == r['done_nodes'] for r in pool[a].values()), tasks=len(pool[a])) for a in L.ARMS}
    json.dump(S, open(HERE + 'summary.json', 'w'), indent=1)

    md = ['# Unread forms at derived relation picks: partial\n', 'Generated by features_unread_read.py. State: %d of 816 census forms walked for option counts, %d rows in per-pick-unread.tsv. Part 1 from the census and gold\'s text and Part 2 from the run\'s records are complete. The rows that need a walk (the `options` rows, and the option counts of the table) read the walked forms only.\n' % (walked, rows_n)]
    md.append('Terms. Derived pick: a relation pick of an atom whose relation belongs to an earlier form of gold. Set definitions, each cut to the forms in scope at the pick:\n')
    md += ['- unread_gold: read by no form of gold, the pick\'s own form included. A target is never inside, as the pick\'s form reads it.', '- unread_later: read by no form of gold other than the pick\'s form. This set uses forms after the pick.', '- unread_before: read by no form before the pick\'s form. This is `unread_before` of the record features-init-residual-bits-split-74forms.', '- unread_so_far: read by no form before the pick, and by no earlier atom of the pick\'s form.', '']
    md.append('Bits: `relation` of the census row\'s atom, scope of all earlier forms unless a row says parents.\n')
    md.append('Form counts: %s\n' % json.dumps(S['forms']))
    md.append('Derived picks by kind, every row of the table, valid or not: %s\n' % json.dumps(S['picks_by_kind']))
    md.append('## Sets at a derived pick, scope of all earlier forms\n')
    md.append('Valid forms. Each cell: median size, share of picks with gold\'s target in the set.\n')
    md.append(table(['Group', 'Picks', 'Tasks', 'Median scope', 'Bits paid'] + [k for k in L.SETS], [[r['group'], r['picks'], r['tasks'], r['median_scope'], fmt(r['bits'])] + ['%s, %.1f%%' % (r[k]['median'], 100 * r[k]['share']) for k in L.SETS] for r in sizes]))
    md.append('## Bits paid against log2 of the set, picks with the target in the set\n')
    md.append(table(['Group', 'Set', 'Picks in set', 'Mean bits paid', 'Mean log2 set'], [[r['group'], k, r[k]['inside'], fmt(r[k]['bits_inside']), fmt(r[k]['log2_inside'])] for r in sizes if r['group'] in ('all',) + KINDS for k in READ_SETS]))
    md.append('## Under 25 bits with a pick inside the set at log2 of the set\n')
    md.append('This count assumes something tells a pick inside the set from a pick outside it.\n')
    md.append('Now: %d forms of %d with bits, tasks %d; parents scope %d forms, tasks %d.\n' % (fu, len(t0), tu, fup, tup))
    md.append(table(['Scope', 'Set', 'Picks at log2', 'Forms under 25', 'Taken under', 'Tasks under 25'], [[r['scope'], r['set'], r['picks_paying_log2'], r['forms_under'], r['taken_under'], r['tasks_under']] for r in S['oracle']]))
    md.append('Same count, a pick inside the set paying log2 of the relation options of the set at that pick, forms with a walk row:\n')
    md.append(table(['Set', 'Forms read', 'Picks at log2', 'Forms under now', 'Forms under', 'Taken under'], [[r['set'], r['forms_read'], r['picks_paying_log2'], r['forms_under_now'], r['forms_under'], r['taken_under']] for r in S['oracle_options']]))
    md.append('## Mixture prior, w fit on non-held walks\n')
    md.append(table(['Set', 'Variant', 'w', 'Forms read', 'Saved per derived pick (95%)', 'Net of the cost at all relation picks, per derived pick', 'Forms under now, under mixture', 'Taken under, pushed over', 'Tasks under'], [[r['set'], r['variant'], r['w'], r['forms_read'], '%s (%s to %s)' % (fmt(r['saved_per_derived_pick'], 3), fmt(r['ci95'][0], 3), fmt(r['ci95'][1], 3)), fmt(r['net_saved_per_derived_pick'], 3), '%d, %d' % (r['forms_under_now'], r['forms_under']), '%d, %d' % (r['taken_under'], r['pushed_over']), r['tasks_under']] for r in S['mixture']]))
    md.append('## Pool forms\n')
    md.append(table(['Arm', 'Group', 'Picks', 'Sources', 'Readable', 'Target forms, found', 'Found picks', 'Found s, median', 'Unread at found, median', 'Unread at end, median', 'Target unread at found', 'Target unread at end', 'Bits paid, target unread at end', 'log2 set at end', 'log2 set at found', 'INIT target, node of another kind'],
                    [[r['arm'], r['group'], r['picks'], json.dumps(r['source']), r['readable'], '%d, %d' % (r['target_forms'], r['target_forms_found']), '%d, %.1f%%' % (r['found'], 100 * (r['found_share'] or 0)), r.get('found_seconds_median'), r.get('unread_at_found_median'), r.get('unread_end_median'), '%s of %s' % (r['with_node'] - r.get('read_at_found', 0), r['with_node']), '%s of %s' % (r.get('unread_end_inside'), r['with_node']), fmt(r.get('bits_inside_mean')), fmt(r.get('log2_end_inside_mean')), fmt(r.get('log2_at_found_inside_mean')), r['init_target_by_other_kind']] for r in S['pool']]))
    open(HERE + 'partial.md', 'w').write('\n'.join(md))
    print('%d rows, %d columns; walked %d, misaligned %d' % (rows_n, len(cols), walked, misaligned))
    print('\n'.join(md))


if __name__ == '__main__':
    main()
