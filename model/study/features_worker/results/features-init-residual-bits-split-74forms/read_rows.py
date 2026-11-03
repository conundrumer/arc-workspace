"""Reads rows.jsonl, component-rows.jsonl and pool-components.jsonl, on the rows that exist. Stdlib only.

  python3 read_rows.py

Writes parts-by-form.tsv, parts-table.tsv, pairs-table.tsv, reads-table.tsv, read-counts.tsv, component-picks.tsv, component-summary.tsv, summary.json and partial.md in this folder.
No number here is fit to a row: BAR is the brief's 25 bits, and the groups of labels are the walk's own.
"""
import collections
import itertools
import json
import math
import os
import statistics as st

HERE = os.path.dirname(os.path.abspath(__file__)) + '/'
BAR = 25.0
ARTS = ('component', 'ports', 'key labels', 'heads', 'reads')
READ_PARTS = ('relation', 'columns', 'values', 'stops', 'join mix', 'OR and ALL coins')
UNITS = ('component', 'ports', 'key labels', 'heads') + READ_PARTS
SETS = (('all', lambda r: True), ('not held', lambda r: not r['held']), ('held', lambda r: r['held']))
PORT_COINS = {'keyed', 'port: taken or skipped', 'outside: taken or skipped', 'port: empty'}
HEAD_LABELS = {'head: bound', 'head: names a key label', 'head: body reads no key', 'head: count of labels', 'head: which label'}
KEY_LABELS = {'key: count of labels', 'key: which labels'}
BODY_COINS = ('or:take', 'top:no OR', 'top:no ALL', 'or:branches', 'or:after', 'br:else-NOT coin', 'br:else-NOT pick', 'br:nest coin', 'br:nest first coin', 'br:bind quit', 'or:export coin', 'all:guard stops', 'long body', 'key partly read')


def unit(label):
    """The part of a walk label of or_q.py. A label that this does not know stops the read: no part goes unnamed."""
    if label == 'component':
        return 'component'
    if label in PORT_COINS:
        return 'ports'
    if label in HEAD_LABELS:
        return 'heads'
    if label in KEY_LABELS or label.endswith('key: which labels an OR exports'):
        return 'key labels'
    if 'atom: ' in label:
        sub = label.split('atom: ', 1)[1]
        if sub in ('relation', 'relation (op)'):
            return 'relation'
        if sub in ('column', 'fcol'):
            return 'columns'
        if sub.startswith('value') or sub == 'op':
            return 'values'
        if sub == 'column stop':
            return 'stops'
        if sub == 'join mix':
            return 'join mix'
        raise ValueError('an atom label with no part: ' + label)
    if label.endswith(('top:stop', 'br:stop', 'br:go on')):
        return 'stops'
    if label.endswith(BODY_COINS):
        return 'OR and ALL coins'
    raise ValueError('a label with no part: ' + label)


def load(name):
    path = HERE + name
    out = []
    if os.path.exists(path):
        for line in open(path):
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return out


def quart(xs):
    xs = sorted(xs)
    if not xs:
        return (None, None, None)
    if len(xs) < 2:
        return (xs[0], xs[0], xs[0])
    q = st.quantiles(xs, n=4, method='inclusive')
    return tuple(round(x, 2) for x in q)


def fmt(x, d=1):
    return '%.*f' % (d, x) if x is not None else ''


def table(head, rows):
    out = ['| ' + ' | '.join(head) + ' |', '|' + '---|' * len(head)]
    for r in rows:
        out.append('| ' + ' | '.join(str(x) for x in r) + ' |')
    return out


def split_form(r):
    d = dict.fromkeys(UNITS, 0.0)
    for k, v in r['parts'].items():
        d[unit(k)] += v
    d['reads'] = sum(d[p] for p in READ_PARTS)
    return d


def check_tool(r, d):
    """The parts against the cats of arclog_bits: rel, col, val and stop equal; the sum equals the total."""
    c = r['cats']
    return dict(sum_diff=round(sum(d[p] for p in ('component', 'ports', 'key labels', 'heads', 'reads')) - r['total'], 3), rel=round(d['relation'] - c['rel'], 3), col=round(d['columns'] - c['col'], 3), val=round(d['values'] - c['val'], 3), stop=round(d['stops'] - c['stop'], 3))


def parts_rows(rows, splits):
    out = []
    for name, keep in SETS:
        sel = [r for r in rows if keep(r)]
        n = len(sel)
        for p in ARTS + READ_PARTS:
            xs = [splits[r['key']][p] for r in sel]
            under = sum(1 for r, x in zip(sel, xs) if r['total'] - x < BAR)
            out.append(dict(set=name, forms=n, part=p, total=round(sum(xs), 1), share=round(sum(xs) / sum(r['total'] for r in sel), 3) if n else None, median=round(st.median(xs), 2) if n else None, under=under))
    return out


def pairs_rows(rows, splits):
    out = []
    for a, b in itertools.combinations(UNITS, 2):
        row = dict(a=a, b=b)
        for name, keep in SETS:
            sel = [r for r in rows if keep(r)]
            row[name] = sum(1 for r in sel if r['total'] - splits[r['key']][a] - splits[r['key']][b] < BAR)
        out.append(row)
    for a in ('component', 'ports', 'key labels', 'heads'):
        row = dict(a=a, b='reads')
        for name, keep in SETS:
            sel = [r for r in rows if keep(r)]
            row[name] = sum(1 for r in sel if r['total'] - splits[r['key']][a] - splits[r['key']]['reads'] < BAR)
        out.append(row)
    return sorted(out, key=lambda x: -x['all'])


def fit_of(x):
    """A read that is the only atom of its body must meet each head need; a read among several must meet one."""
    return 'fit_head' if x['body_atoms'] == 1 else 'fit_head_any'


def read_rows(rows):
    flat = []
    for r in rows:
        for x in r['reads']:
            flat.append(dict(key=r['key'], held=r['held'], place=x['place'], port=x['port'], ctx=x['ctx'], relation=x['relation'], target_form=x['target_form'], kind=x['kind'], body_atoms=x['body_atoms'], neg=x['neg'], bits=x['bits'], cats=x['cats'], mix=round((x['bits'] or 0) - sum(x['cur'].values()), 3), counts=x.get('counts'), log2=x.get('log2'), target_in=x.get('target_in'), fit=fit_of(x)))
    return flat


def read_summary(flat):
    """Per set and place: reads of an earlier form, log2 of each count, gold's target in each set, bits paid."""
    out = []
    for name, keep in SETS:
        for place in ('key', 'port'):
            sel = [x for x in flat if keep(x) and x['place'] == place and x['kind'] == 'form']
            if not sel:
                continue
            row = dict(set=name, place=place, reads=len(sel), median_bits=round(st.median(x['bits'] for x in sel), 2), median_relation_bits=round(st.median(x['cats']['rel'] for x in sel), 2), sum_relation_bits=round(sum(x['cats']['rel'] for x in sel), 1))
            for m in ('all', 'unread_before', 'unread_so_far', 'fit', 'fit_head_key'):
                ks = [x['fit'] if m == 'fit' else m for x in sel]
                row[m + '_median_count'] = st.median(x['counts'][k] for x, k in zip(sel, ks))
                row[m + '_median_log2'] = round(st.median(x['log2'][k] if x['log2'][k] is not None else 0 for x, k in zip(sel, ks)), 2)
                row[m + '_gold_in'] = sum(x['target_in'][k] for x, k in zip(sel, ks))
                row[m + '_sum_log2_gold_in'] = round(sum(x['log2'][k] or 0 for x, k in zip(sel, ks) if x['target_in'][k]), 1)
                row[m + '_sum_relation_gold_in'] = round(sum(x['cats']['rel'] for x, k in zip(sel, ks) if x['target_in'][k]), 1)
            out.append(row)
    return out


def uniform_under(rows, flat):
    """Forms under BAR where each read of an earlier form with gold's target in the set pays log2 of the set in place of its relation bits, and any other read pays as it does now."""
    out = {}
    for name, keep in SETS:
        row = {}
        for m in ('all', 'unread_before', 'unread_so_far', 'fit', 'fit_head_key'):
            n = 0
            for r in rows:
                if not keep(r):
                    continue
                t = r['total']
                for x in flat:
                    if x['key'] != r['key'] or x['kind'] != 'form':
                        continue
                    k = x['fit'] if m == 'fit' else m
                    if x['target_in'][k]:
                        t += (x['log2'][k] or 0) - x['cats']['rel']
                n += t < BAR
            row[m] = n
        out[name] = row
    return out


def masked(w, gold, keep):
    """The bits of gold's component under the priors' counts w, cut to keep; None where gold is outside."""
    return round(-math.log2(w[gold] / sum(w[c] for c in keep)), 2) if gold in keep else None


def component_rows(rows, comp_rows, pool):
    by_key = {r['key']: r for r in rows}
    w = json.load(open(HERE + 'comp-priors.json'))
    found = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))
    nodes = collections.defaultdict(dict)
    for p in pool:
        found[p['task']][p['arm']].update(p['components'])
        nodes[p['task']][p['arm']] = p['nodes']
    out = []
    for c in comp_rows:
        rs = {k: v.get('status') for k, v in c['components'].items()}
        some = sorted(k for k, s in rs.items() if s in ('rows_all', 'rows_some'))
        every = sorted(k for k, s in rs.items() if s == 'rows_all')
        g = c['gold_component']
        paid = by_key[c['key']]['parts'].get('component') if c['key'] in by_key else None
        earlier = sorted(set(c['earlier_gold_components']))
        in_pool = c['task'] in found
        pool_f = sorted(found[c['task']]['factored_search']) if in_pool else None
        pool_c = sorted(found[c['task']]['control_search']) if in_pool else None
        pool_any = sorted(set(pool_f) | set(pool_c)) if in_pool else None
        out.append(dict(key=c['key'], task=c['task'], held=c['held'], gold=g, gold_status=rs.get(g), listed=len(c['listed']), rows_some=len(some), rows_all=len(every), feasible_some=some, feasible_all=every, statuses=dict(collections.Counter(rs.values())), capped=sorted(k for k, v in c['components'].items() if v.get('capped')), paid=paid,
                        uniform_some=round(math.log2(len(some)), 2) if some else None, uniform_all=round(math.log2(len(every)), 2) if every else None, uniform_list=round(math.log2(len(c['listed'])), 2), gold_in_some=g in some, gold_in_all=g in every,
                        masked_list=masked(w, g, c['listed']), masked_some=masked(w, g, some), masked_all=masked(w, g, every), total=by_key[c['key']]['total'] if c['key'] in by_key else None,
                        earlier_gold=earlier, gold_in_earlier=g in earlier, in_pool=in_pool, pool_factored=pool_f, pool_control=pool_c, pool_any=pool_any, gold_in_pool=(g in pool_any) if in_pool else None, feasible_and_pool=len(set(some) & set(pool_any)) if in_pool else None, feasible_and_earlier=len(set(some) & set(earlier))))
    return out


def comp_summary(cr):
    out = []
    for name, keep in SETS:
        sel = [x for x in cr if keep(x)]
        if not sel:
            continue
        row = dict(set=name, picks=len(sel))
        for m in ('rows_some', 'rows_all'):
            row[m + '_quartiles'] = quart([x[m] for x in sel])
        row['paid_sum'] = round(sum(x['paid'] or 0 for x in sel), 1)
        row['paid_median'] = round(st.median(x['paid'] or 0 for x in sel), 2)
        for m in ('uniform_some', 'uniform_all', 'uniform_list'):
            row[m + '_sum'] = round(sum(x[m] or 0 for x in sel), 1)
            row[m + '_median'] = round(st.median(x[m] or 0 for x in sel), 2)
        for m in ('masked_some', 'masked_all'):
            row[m + '_sum'] = round(sum(x[m] or 0 for x in sel), 1)
            row[m + '_median'] = round(st.median(x[m] or 0 for x in sel), 2)
        row['under_at_0'] = sum(x['total'] - x['paid'] < BAR for x in sel)
        for m in ('uniform_some', 'uniform_all', 'masked_some', 'masked_all'):
            row['under_' + m] = sum(x[m] is not None and x['total'] - x['paid'] + x[m] < BAR for x in sel)
        row['gold_in_some'] = sum(x['gold_in_some'] for x in sel)
        row['gold_in_all'] = sum(x['gold_in_all'] for x in sel)
        row['gold_in_earlier'] = sum(x['gold_in_earlier'] for x in sel)
        pooled = [x for x in sel if x['in_pool']]
        row['picks_in_pool'] = len(pooled)
        row['gold_in_pool'] = sum(bool(x['gold_in_pool']) for x in pooled)
        out.append(row)
    return out


def write_tsv(name, rows):
    if not rows:
        return
    head = list(rows[0])
    with open(HERE + name, 'w') as f:
        f.write('\t'.join(head) + '\n')
        for r in rows:
            f.write('\t'.join(json.dumps(r[k]) if isinstance(r[k], (list, dict)) else str(r[k]) for k in head) + '\n')


def main():
    rows = load('rows.jsonl')
    comp = load('component-rows.jsonl')
    pool = load('pool-components.jsonl')
    form_set = load('form-set.jsonl')
    good = [r for r in rows if 'error' not in r]
    splits = {r['key']: split_form(r) for r in good}
    checks = {r['key']: check_tool(r, splits[r['key']]) for r in good}
    worst = {k: max(abs(c[f]) for c in checks.values()) for k, f in (('sum', 'sum_diff'), ('rel', 'rel'), ('col', 'col'), ('val', 'val'), ('stop', 'stop'))} if checks else {}
    write_tsv('parts-by-form.tsv', [dict(key=r['key'], held=r['held'], group=r['group'], gold_component=r['component'], total=r['total'], census_bits=r['census_bits'], diff=r['diff'], port_count=sum(1 for b in r['bodies'] if b['place'] == 'port'), **{p: round(splits[r['key']][p], 3) for p in ARTS + READ_PARTS}) for r in good])
    pr = parts_rows(good, splits)
    write_tsv('parts-table.tsv', pr)
    pa = pairs_rows(good, splits)
    write_tsv('pairs-table.tsv', pa)
    flat = read_rows(good)
    write_tsv('reads-table.tsv', flat)
    rs = read_summary(flat)
    write_tsv('read-counts.tsv', rs)
    uu = uniform_under(good, flat)
    cr = component_rows(good, comp, pool)
    write_tsv('component-picks.tsv', cr)
    cs = comp_summary(cr)
    write_tsv('component-summary.tsv', cs)
    summary = dict(forms_in_set=len(form_set), rows=len(rows), bad_rows=len(rows) - len(good), held_rows=sum(r['held'] for r in good), not_held_rows=sum(not r['held'] for r in good), total_diffs=[(r['key'], r['diff']) for r in good if r['diff']], not_ok=[r['key'] for r in good if not r['ok']], no_match=[r['key'] for r in good if r['match'] is not True], fell_back=[r['key'] for r in good if r['fell_back']],
                   tool_check_worst=worst, components=dict(collections.Counter(r['component'] for r in good)), read_kinds=dict(collections.Counter('%s %s' % (x['place'], x['kind']) for x in flat)), several_atom_reads=sum(1 for x in flat if x['body_atoms'] > 1), uniform_relation_under=uu, parts=pr, pairs_top=pa[:12], read_counts=rs, component_summary=cs, component_rows=len(comp),
                   gold_out_some=[(x['key'], x['held'], x['gold'], x['gold_status']) for x in cr if not x['gold_in_some']], gold_out_all=[(x['key'], x['held'], x['gold'], x['gold_status']) for x in cr if not x['gold_in_all']], capped_picks=sum(1 for x in cr if x['capped']), capped_status=dict(collections.Counter(c['components'][k].get('status') for c in comp for k in c['components'] if c['components'][k].get('capped'))), status_total=dict(sum((collections.Counter(x['statuses']) for x in cr), collections.Counter())))
    pooled = [x for x in cr if x['in_pool']]
    summary['pool'] = dict(picks_covered=len(pooled), picks_outside=len(cr) - len(pooled), tasks_covered=len({x['task'] for x in pooled}), tasks_outside=len({x['task'] for x in cr if not x['in_pool']}), not_held_covered=sum(not x['held'] for x in pooled),
                           component_count_quartiles_any_arm=quart([len(x['pool_any']) for x in pooled]), feasible_and_pool_quartiles=quart([x['feasible_and_pool'] for x in pooled]), gold_in_factored=sum(x['gold'] in x['pool_factored'] for x in pooled), gold_in_control=sum(x['gold'] in x['pool_control'] for x in pooled), gold_in_any=sum(x['gold'] in x['pool_any'] for x in pooled), gold_outside=[(x['key'], x['gold']) for x in pooled if x['gold'] not in x['pool_any']],
                           uniform_feasible_and_pool_sum=round(sum(math.log2(x['feasible_and_pool']) for x in pooled if x['feasible_and_pool'] and x['gold'] in x['pool_any']), 1), paid_sum_same_picks=round(sum(x['paid'] for x in pooled if x['feasible_and_pool'] and x['gold'] in x['pool_any']), 1))
    summary['earlier_gold'] = dict(component_count_quartiles=quart([len(x['earlier_gold']) for x in cr]), feasible_and_earlier_quartiles=quart([x['feasible_and_earlier'] for x in cr]), gold_in=sum(x['gold_in_earlier'] for x in cr), picks=len(cr), gold_in_not_held=sum(x['gold_in_earlier'] for x in cr if not x['held']), gold_in_held=sum(x['gold_in_earlier'] for x in cr if x['held']))
    freq = collections.Counter(c for x in cr for c in x['feasible_some'])
    summary['component_freq'] = {c: dict(feasible_some=freq[c], gold=sum(x['gold'] == c for x in cr), statuses=dict(collections.Counter(q['components'][c].get('status') for q in comp if c in q['components']))) for c in sorted(freq, key=lambda c: -freq[c])}
    summary['paid_vs_priors_worst'] = max((abs(x['paid'] - x['masked_list']) for x in cr), default=None)
    tool = HERE + 'scratch/arclog-bits-35ab12c3-3.json'
    if os.path.exists(tool):
        q = json.load(open(tool))['rows'][-1]['before']
        mine = next(r for r in good if r['key'] == '35ab12c3 3')
        summary['arclog_bits_check'] = dict(key=mine['key'], tool_total=q['total'], row_total=mine['total'], parts_equal=q['parts'] == mine['parts'])
    json.dump(summary, open(HERE + 'summary.json', 'w'), indent=1)
    md = ['# INIT residual bits by part', '', 'State: %d of %d forms walked, %d of %d picks read for the component part. Generated by read_rows.py.' % (len(rows), len(form_set), len(comp), len(form_set)), '']
    md += ['Parts, from the walk\'s own labels in or_q.py (`unit` in read_rows.py; an unknown label stops the read):', '',
           '- component: `component`.', '- ports: the coins `keyed`, `port: taken or skipped`, `outside: taken or skipped`, `port: empty`. The walk draws no count of ports: the coins make it.', '- key labels: `key: count of labels`, `key: which labels`, `key: which labels an OR exports`.', '- heads: `head: bound`, `head: names a key label`, `head: body reads no key`, `head: count of labels`, `head: which label`.',
           '- reads: relation (`relation`, `relation (op)`), columns (`column`, `fcol`), values (`value: ...`, `op`), stops (`column stop`, `top:stop`, `br:stop`, `br:go on`), join mix (`atom: join mix`, the atom\'s bits less the sum of its picks, from the join coin; it is negative), and OR and ALL coins (the other body coins).', '',
           'The component set, its definitions and its caps are in the docstring of component_feasible.py.', '']
    md += ['## Bits by part', '', 'Each cell: total bits, median per form, forms under 25 with the part at 0 bits. The parts sum to each form\'s total.', '']
    by = {(x['set'], x['part']): x for x in pr}
    head = ['Part'] + [s for s, _ in SETS]
    body = []
    for p in ARTS + READ_PARTS:
        cells = [('  ' if p in READ_PARTS else '') + p]
        for s, _ in SETS:
            x = by[s, p]
            cells.append('%s / %s / %d of %d' % (fmt(x['total']), fmt(x['median'], 2), x['under'], x['forms']))
        body.append(cells)
    md += table(head, body)
    md += ['', '## Pairs at 0 bits, the first 12', '']
    md += table(['Pair'] + [s for s, _ in SETS], [['%s + %s' % (x['a'], x['b'])] + [x[s] for s, _ in SETS] for x in pa[:12]])
    md += ['', '## Reads of earlier forms', '', 'This uses gold\'s earlier forms as the found forms, so it is an upper bound on what a search has. See read-counts.tsv and reads-table.tsv.', '']
    md += table(['Set, place', 'Reads', 'Median bits, relation bits', 'All: count, log2, gold in', 'Unread before: count, log2, gold in', 'Unread so far: count, log2, gold in', 'Fit: count, log2, gold in'], [['%s, %s' % (x['set'], x['place']), x['reads'], '%s, %s' % (x['median_bits'], x['median_relation_bits'])] + ['%s, %s, %s' % (x[m + '_median_count'], x[m + '_median_log2'], x[m + '_gold_in']) for m in ('all', 'unread_before', 'unread_so_far', 'fit')] for x in rs])
    md += ['', 'Forms under 25 with each read of an earlier form paying log2 of the set where gold\'s target is in the set: `%s`.' % json.dumps(uu), '']
    md += ['## Component pick', '']
    md += table(['Set', 'Picks', 'Rows on some input: Q1, median, Q3', 'Rows on every input: Q1, median, Q3', 'Paid: sum, median', 'Uniform, some: sum, median', 'Uniform, every: sum, median', 'Gold inside: some, every', 'Gold in earlier forms', 'Picks in the pool run, gold there'],
                [[x['set'], x['picks'], x['rows_some_quartiles'], x['rows_all_quartiles'], '%s, %s' % (x['paid_sum'], x['paid_median']), '%s, %s' % (x['uniform_some_sum'], x['uniform_some_median']), '%s, %s' % (x['uniform_all_sum'], x['uniform_all_median']), '%s, %s' % (x['gold_in_some'], x['gold_in_all']), x['gold_in_earlier'], '%s, %s' % (x['picks_in_pool'], x['gold_in_pool'])] for x in cs])
    md += ['', 'Bits of gold\'s component with the priors\' counts cut to the set, and forms under 25 with the component at each cost: see component-summary.tsv and summary.json.', '']
    md += table(['Set', 'Priors cut to some: sum, median', 'Priors cut to every: sum, median', 'Under 25: at 0 bits', 'uniform some', 'uniform every', 'priors cut to some', 'priors cut to every'], [[x['set'], '%s, %s' % (x['masked_some_sum'], x['masked_some_median']), '%s, %s' % (x['masked_all_sum'], x['masked_all_median']), x['under_at_0'], x['under_uniform_some'], x['under_uniform_all'], x['under_masked_some'], x['under_masked_all']] for x in cs])
    md += ['', 'Picks with gold outside, rows on some input: `%s`.' % json.dumps(summary['gold_out_some']), '', 'Picks with gold outside, rows on every input: `%s`.' % json.dumps(summary['gold_out_all']), '']
    open(HERE + 'partial.md', 'w').write('\n'.join(md) + '\n')
    print('\n'.join(md))
    print({k: v for k, v in summary.items() if k not in ('parts', 'pairs_top', 'read_counts')})


if __name__ == '__main__':
    main()
