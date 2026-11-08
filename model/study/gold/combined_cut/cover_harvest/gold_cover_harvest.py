"""Cover harvest on the final text: where a search run logged a cover of a gold form, tries the covering clause, with the forms it reads, in place of that gold form, and keeps the result where it passes the bar and ranks lower. design.md in this folder gives the definitions. Rows in rows-K.jsonl; a stem with no candidate has a row in none-K.jsonl, so a restart skips it.

  <runtime python> gold_cover_harvest.py run [K N]
  <runtime python> gold_cover_harvest.py child STEM...
  <runtime python> gold_cover_harvest.py cands STEM...    prints the candidates of each stem and their matches, with no trial

HARVEST_RUNS=det runs the DET swap step (../det-swap/design.md): the one run is a DET line for each proposer component of one column.
HARVEST_MARGIN=0.5 makes a trial stand where its worst form is that many bits under the current one, as that design defines.
"""
import glob, json, os, re, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.append('/Users/davidlu/code/arc-workspace/model/study/gold/reads/union')  # gold_final_dedup.py
import gold_final_dedup as F
from gold_final_dedup import matches, form_tables, relations, text_of, vsha, say
import gold_cheapest_prune as P
from gold_cheapest_prune import C, holds, name_of, program_lines
C.GIB = 3  # a stem past 3 GiB of footprint is set aside; 6 shards share a 24 GiB machine
sys.path += [P.D + 'features-worker/results/features-node-score-refit-loop', P.D + 'sampler/search-worker/refit-tools']
from features_node_io import S120, R120, excluded, read_nodes
from search_node_score_parity import load_bank, read_lines

OUT = HERE + '/rows.jsonl'
NONE = HERE + '/none.jsonl'
STEM_SECONDS = 300  # trials stop here; the row keeps what stood and counts the trials left
BANK = P.D + 'sampler/search-worker/runs/search-refit-r1-heldout37-ramp22-2seeds-600s-0729e4943/out/'
RAMP = open(F.RAMP).read().split()
EXCLUDED = excluded()
DET = os.environ.get('HARVEST_RUNS') == 'det'  # the DET swap step: the one run is a DET line per proposer component
MARGIN = float(os.environ['HARVEST_MARGIN']) if 'HARVEST_MARGIN' in os.environ else None  # bits under the current worst form that a trial needs
HELD_RAMP = open(P.D + 'gold/held-out-ramp.txt').read().split() if DET else []


def set_of(t):
    """The task set of a stem: held-out ramp, 37, ramp, training, or None where the stem is in no set."""
    return 'held-out ramp' if t in HELD_RAMP else '37' if t in P.HELD else 'ramp' if t in RAMP else 'training' if t not in EXCLUDED else None


def events_run(folder, t):
    """({token: {clause, parents}}, [(node, token, draw)]) of a run of events and nodes files: the nodes, and the covers that count."""
    ev, nf = '%s/%s.events.jsonl' % (folder, t), '%s/%s.nodes.jsonl.zst' % (folder, t)
    if not (os.path.exists(ev) and os.path.exists(nf)):
        return {}, []
    covers = [r for r in read_lines(ev) if r.get('event') == 'cover' and r['draw'] > 0]
    if not covers:
        return {}, []
    nodes = {n['token']: n for n in read_nodes(nf)}
    keep = [(r['node'], str(r['node']), r['draw']) for r in covers if str(r['node']) in nodes and not (nodes[str(r['node'])].get('tags') or {}).get('seeded')]
    return {k: dict(clause=n['clause'], parents=[str(p) for p in n['parents']]) for k, n in nodes.items()}, keep


def bank_run(folder, t):
    """The same for a bank run: the nodes are the forms of the bank, and a cover counts where the lineage of the bank keeps its node."""
    stem = '%s/%s/work/%s.out.jsonl' % (folder, t, t)
    if not os.path.exists(stem + '.bank'):
        return {}, []
    bank = load_bank(stem + '.bank')
    covers = []
    for r in read_lines(stem + '.cover'):
        n = r['node']
        if r['draw'] > 0 and n in bank['nodes'] and any(e['proc'] == r['proc'] and e['nodes0'] <= n < e['nodes1'] for e in bank['lineage']):
            covers.append((n, str(bank['nodes'][n].form), r['draw']))
    return {str(i): dict(clause=f.text, parents=[str(p) for p in f.parents]) for i, f in bank['forms'].items()}, covers


def proposers():
    """The components of the Proposers list of the lib doc that have one column, as `SharedColor(C)`, in the order of the doc."""
    got, on = [], False
    for l in open(F.LIB):
        if l.startswith('## '):
            on = l.startswith('## Proposers')
        m = re.match(r'- `(\w+)\(([^,()]*)\)`', l)
        if on and m:
            got.append(m[1])
    return got


def det_run(folder, t):
    """The same for the DET run, which reads no folder: a node for each proposer component, a DET line with no parents, and a cover of each."""
    comps = proposers()
    return {str(k): dict(clause='(DET &f%d %s)' % (k, c), parents=[], tags={'seeded': False}) for k, c in enumerate(comps)}, [(k, str(k), 1) for k in range(len(comps))]


# name, reader, folders, task sets
RUNS = [('det', det_run, [None], ('training', '37', 'ramp', 'held-out ramp'))] if DET else [
        ('s120', events_run, [S120], ('training',)),
        ('r120', events_run, R120, ('training',)),
        ('b0', bank_run, [BANK + 'bundle_s0'], ('37', 'ramp')),
        ('b1', bank_run, [BANK + 'bundle_s1'], ('37', 'ramp'))]


def relabel(text, names):
    """text with each atom (&label ...) renamed at once by names: {label: (new label, {relation: {column label: new column label}})}. The column labels at the top level of the atom, (:Lab ...) and ^Lab, are renamed by the map of the relation, which is the part of the label after the dot."""
    edits, stack = [], [[]]
    for m in re.finditer(r'\(|\)|[^\s()]+', text):
        if m[0] == '(':
            stack.append([])
        elif m[0] == ')' and len(stack) > 1:
            kids = stack.pop()
            if kids and kids[0][0] == 'tok' and kids[0][1].startswith('&'):
                label, dot, sub = kids[0][1].partition('.')
                if label in names:
                    new, cols = names[label]
                    cols = cols.get(sub, {})
                    edits.append((kids[0][2], kids[0][3], new + dot + sub))
                    for k in kids[1:]:
                        if k[0] == 'tok' and k[1].startswith('^'):
                            edits.append((k[2], k[3], '^' + cols.get(k[1][1:], k[1][1:])))
                        elif k[0] == 'grp' and k[1] and k[1][0][0] == 'tok' and k[1][0][1].startswith(':'):
                            lab = k[1][0]
                            edits.append((lab[2], lab[3], ':' + cols.get(lab[1][1:], lab[1][1:])))
            stack[-1].append(('grp', kids))
        else:
            stack[-1].append(('tok', m[0], m.start(), m.end()))
    for a, b, new in sorted(edits, reverse=True):
        text = text[:a] + new + text[b:]
    return text


def head_to(line, label):
    """line with the label of its form changed."""
    return re.sub(r'^(\(\w+ )&\w+', lambda m: m[1] + label, line, count=1)


def flip(cols):
    """The column maps of a pair, the other way: {relation: {column label of the gold form: column label of the sub}}."""
    return {rel: {b: a for a, b in m.items()} for rel, m in cols.items()}


def subtree(nodes, token):
    """The tokens of the node and of every node that it reads, in order of token."""
    seen, todo = set(), [token]
    while todo:
        k = todo.pop()
        if k not in seen:
            seen.add(k)
            todo += nodes[k]['parents']
    return sorted(seen, key=int)


def sub_of(run, nodes, k):
    """The form of node k under its fresh label, with its reads on the fresh labels of its parents."""
    n = nodes[k]
    names = {name_of(nodes[p]['clause']): ('&h%s%s' % (run, p), {}) for p in n['parents']}
    stray = set(P.NAME.findall(n['clause'])) - set(names) - {name_of(n['clause'])}
    if stray:
        raise ValueError('reads %s, which no parent names' % sorted(stray))
    return dict(run=run, token=k, label='&h%s%s' % (run, k), line=head_to(relabel(n['clause'], names), '&h%s%s' % (run, k)), to={}, unread=None)


def candidates(t):
    """(candidates, subs): the cover candidates of the stem, each with its subtree, and the subtree forms of all of them, each once, in order of token. The gold index of a cover is not used."""
    reg, cands = {}, []
    for run, reader, folders, sets in RUNS:
        if set_of(t) not in sets:
            continue
        for folder in folders:
            nodes, covers = reader(folder, t)
            if covers:
                break
        seen = set()
        for n, tok, draw in covers:
            if tok in seen:
                continue
            seen.add(tok)
            c = dict(run=run, node=n, token=tok, draw=draw, why=None, subs=[])
            try:
                for k in subtree(nodes, tok):
                    if (run, k) not in reg:
                        reg[run, k] = sub_of(run, nodes, k)
                    c['subs'].append(reg[run, k])
            except (KeyError, ValueError) as e:
                c.update(subs=[], why='subtree unread: %s %s' % (type(e).__name__, str(e)[:100]))
            else:
                c['top'] = reg[run, tok]
            cands.append(c)
    runs = [r[0] for r in RUNS]
    return cands, sorted(reg.values(), key=lambda s: (runs.index(s['run']), int(s['token'])))


def reader_names(tab, names):
    """The names that readers write after (: for the columns of a table: the labels of a rule's table, the column names of an INIT's or a DET's, where a column of several cells a.c0, a.c1, ... has the name a."""
    return [re.sub(r'\.c\d+$', '', x) for x in (tab.labels if any(tab.labels) else names)]


def column_map(a, b, pi):
    """{name of column c in a: name of column pi[c] in b}, or None where one name goes to two or the lists do not fit."""
    if len(a) != len(pi) or len(b) != len(pi):
        return None
    got = {}
    for c, d in enumerate(pi):
        if got.setdefault(a[c], b[d]) != b[d]:
            return None
    return got


def find_covers(bar, forms, out, subs):
    """Fills the `to` of each sub: {gold form f: (eq, {relation: {column label of the sub: column label of f}})} for each gold form that the sub matches, as `find_pairs` of gold_final_dedup.py defines it with the gold forms taken as earlier; the reason a sub has no tables is its `unread`."""
    lines = forms + [s['line'] for s in subs]
    tabs, unread = form_tables(bar, '\n'.join(lines + [out]))
    n = len(forms)
    rel, canon, names = {}, {}, {}
    for g, line in enumerate(lines):
        s = subs[g - n] if g >= n else None
        if g in unread or g not in tabs:
            if s:
                s['unread'] = unread.get(g, 'no table')
            continue
        got, why = relations(line, tabs[g])
        if why:
            if s:
                s['unread'] = why
            continue
        kind, comp = line.split()[0][1:], line.split()[2] if line.startswith('(INIT') else None
        names.update((id(tab), reader_names(tab, cn)) for tab, cn in tabs[g].values())
        first = None
        for f in range(n if s else g if kind == 'DET' else 0):  # a gold form only moves `canon`, and only a DET does
            if f not in rel or rel[f][0] != kind or rel[f][1] != comp or not set(got) <= set(rel[f][2]):
                continue
            canon_g = dict(canon)
            if kind == 'DET':
                canon_g[next(iter(tabs[g]))] = canon.get(next(iter(tabs[f])), next(iter(tabs[f])))
            classes, cols = [], {}
            for name, tab in got.items():
                other = rel[f][2][name]
                kg, kf = tab.keys(canon_g), other.keys(canon)
                cols[name] = None
                for eq, by_label in (('equal', True), ('equal under relabelling', False)):
                    pi = matches(tab, other, kg, kf, by_label)
                    if pi is not None:
                        cols[name] = column_map(names[id(tab)], names[id(other)], pi)
                        if cols[name] is not None:
                            break
                if cols[name] is None:
                    break
                classes.append(eq)
            else:
                first = f if first is None else first
                if s:
                    s['to'][f] = ('equal' if set(classes) == {'equal'} else 'equal under relabelling', cols)
        if kind == 'DET' and first is not None:
            sg, sf = next(iter(tabs[g])), next(iter(tabs[first]))
            canon[sg] = canon.get(sf, sf)
        rel[g] = (kind, comp, got)


def match(bar, forms, out, cands, subs):
    """Fills the matches of the subs. Where the forms of all subtrees make the text fail to decode, each candidate is read alone, and one whose subtree still fails gets the reason."""
    try:
        find_covers(bar, forms, out, subs)
    except Exception:  # noqa: BLE001
        for c in cands:
            if c['subs']:
                try:
                    find_covers(bar, forms, out, c['subs'])
                except Exception as e:  # noqa: BLE001
                    c['why'] = 'subtree does not decode: %s %s' % (type(e).__name__, str(e)[:100])
    for c in cands:
        if not c['why'] and not c['top']['to']:
            c['why'] = 'no gold form matches' + (': ' + c['top']['unread'] if c['top']['unread'] else '')


def ordered(ls):
    """ls so that each form comes after the forms it reads, the lines in their order wherever that holds, and the OUT line last; None where forms read each other in a circle."""
    todo = [x for x in ls if not x.startswith('(OUT')]
    names = {name_of(x) for x in todo}
    done, got = set(), []
    while todo:
        k = next((k for k, x in enumerate(todo) if all(n in done for n in set(P.NAME.findall(x)) - {name_of(x)} if n in names)), None)
        if k is None:
            return None
        got.append(todo.pop(k))
        done.add(name_of(got[-1]))
    return got + [x for x in ls if x.startswith('(OUT')]


def pruned(ls):
    """ls without the forms that no form reads, again and again, as `dead_lines` finds them."""
    now = list(ls)
    while P.dead_lines(now):
        now.pop(P.dead_lines(now)[-1])
    return now


def squash(x):
    return ' '.join(x.split())


def trial(now, lab, c, g):
    """(reason, lines, info): the text where candidate c takes the place of gold form g in the lines now, or the reason there is none. lab: the label of each gold form."""
    have = {name_of(x) for x in now}
    if lab[g] not in have:
        return 'g is out already', None, None
    top = c['top']
    swap = {}  # sub label: (label of the gold form it is replaced by, its column maps)
    for s in c['subs']:
        if s is not top:
            f = next((f for f in sorted(s['to']) if f != g and lab[f] in have), None)
            if f is not None:
                swap[s['label']] = (lab[f], s['to'][f][1])
    keep = [(s['label'], relabel(s['line'], swap)) for s in c['subs'] if s['label'] not in swap]
    info = dict(replaced=[[a, b[0]] for a, b in swap.items()])
    if squash(head_to(dict(keep)[top['label']], lab[g])) == squash(next(x for x in now if name_of(x) == lab[g])):
        return 'same program', None, info
    new = [x for k, x in keep if k not in have]
    info['brought'] = [k for k, _ in keep if k not in have]
    read = {lab[g]: (top['label'], flip(top['to'][g][1]))}
    rest, at = [], None
    for x in now:
        if name_of(x) == lab[g]:
            at = len(rest)
        else:
            rest.append(relabel(x, read))
    lines = ordered(rest[:at] + new + rest[at:])
    return (None, lines, info) if lines else ('cycle', None, info)


def view(c):
    return dict(run=c['run'], node=c['node'], draw=c['draw'], clauses=[s['line'] for s in c['subs']], matched=[[f, eq] for f, (eq, _) in sorted(c['top']['to'].items())] if not c['why'] else [], why=c['why'])


def stands(fig, cur):
    """Whether the figures fig rank below those of the current text cur. With HARVEST_MARGIN set: fewer undrawable forms; or as many, and a worst form at least MARGIN bits under; or as many, a worst form not over, and a lower sum."""
    if MARGIN is None:
        return P.rank(fig) < P.rank(cur)
    (u, w, s), (u0, w0, s0) = P.rank(fig), P.rank(cur)
    return u < u0 or u == u0 and (w <= w0 - MARGIN or w <= w0 and s < s0)


def order_free(line):
    """line with the atoms of each RULE body and each OR branch sorted, and the two arguments of != and = sorted."""
    stack = [[]]
    for m in re.finditer(r'\(|\)|[^\s()]+', line):
        if m[0] == '(':
            stack.append([])
        elif m[0] == ')':
            kids = stack.pop()
            stack[-1].append(kids)
        else:
            stack[-1].append(m[0])

    def dump(e):
        return e if isinstance(e, str) else '(' + ' '.join(map(dump, e)) + ')'

    def sort(e):
        if isinstance(e, str):
            return e
        e = [sort(k) for k in e]
        if e[:1] in (['!='], ['=']):
            e[1:] = sorted(e[1:], key=dump)
        elif e[:1] == ['RULE']:
            e[2:] = sorted(e[2:], key=dump)
        elif e[:1] == ['OR']:
            e[1:] = [sorted(b, key=dump) for b in e[1:]]
        return e
    return dump(sort(stack[0][0]))


def same_order(lines, now, label, name):
    """Whether lines, with the label of the candidate renamed to name, are the lines now up to the order of atoms."""
    back = [re.sub(re.escape(label) + r'(?=[ .)])', name, x) for x in lines]
    return list(map(order_free, back)) == list(map(order_free, now))


def one(t, bits):
    print('stem', t, flush=True)
    text = text_of(t)
    row = dict(stem=t, vsha=vsha(text), set=set_of(t))
    cands, subs = candidates(t)
    if not cands:
        return dict(row, candidates=[], taken=None, why='no candidate')
    ls = program_lines(text)
    forms, out = [x for x in ls if not x.startswith('(OUT')], next(x for x in ls if x.startswith('(OUT'))
    bar = P.Bar(t)
    match(bar, forms, out, cands, subs)
    row.update(candidates=[view(c) for c in cands], verdicts=[])
    lab = [name_of(x) for x in forms]
    todo = sorted({g for c in cands if not c['why'] for g in c['top']['to']}, reverse=True)
    if not todo:
        return dict(row, taken=None, why='%d candidates, none matches' % len(cands))
    try:
        gold = bar.walk(ls)
    except Exception as e:  # noqa: BLE001
        return dict(row, taken=None, why='rows unread: ' + str(e)[:120])
    if not gold[1]:
        return dict(row, taken=None, why='the text does not end')
    now, cur, norm, dropped, before = list(ls), None, None, [], None
    end, left = time.time() + STEM_SECONDS, 0
    for g in todo:
        best, tried = None, set()
        for c in cands:
            if c['why'] or g not in c['top']['to']:
                continue
            if time.time() > end:
                left += 1
                continue
            v = dict(g=g, run=c['run'], node=c['node'])
            row['verdicts'].append(v)
            why, lines, info = trial(now, lab, c, g)
            v.update(info or {})
            if why:
                v['verdict'] = why
                continue
            if DET and same_order(lines, now, c['top']['label'], lab[g]):
                v['verdict'] = 'same text up to order'
                continue
            # Covers from several nodes and runs often give the same trial text; it is read once.
            if '\n'.join(lines) in tried:
                v['verdict'] = 'same trial text as an earlier candidate'
                continue
            tried.add('\n'.join(lines))
            if before is None:
                before = cur = bits.whole(t, ls)
            for kept in ([pruned(lines), lines] if pruned(lines) != lines else [lines]):
                bad, n = holds(bar, kept, gold)
                if not bad:
                    break
            v['removed'] = sorted(set(map(name_of, now)) - set(map(name_of, kept)) - {None})
            if bad:
                v['verdict'] = bad
                continue
            v['dead_out'] = kept is not lines
            fig = bits.whole(t, program_lines(n))
            if not stands(fig, cur):
                v['verdict'] = 'not cheaper on rank: ' + say(cur, fig)
            else:
                v['verdict'] = 'cheaper: ' + say(cur, fig)
                if best is None or P.rank(fig) < P.rank(best[1]):
                    best = v, fig, kept, n, c
        if best:
            v, fig, kept, n, c = best
            for w in row['verdicts']:
                if w['g'] == g and w['verdict'].startswith('cheaper'):
                    w['verdict'] = 'cheaper, not the lowest' + w['verdict'][7:]
            v['verdict'] = 'stands: ' + say(cur, fig)
            now, cur, norm = kept, fig, n
            dropped.append([g, c['run'], c['node']])
    if left:
        row['time_cap'] = '%d trials left untried at %d s' % (left, STEM_SECONDS)
    if not dropped:
        return dict(row, taken=None, why='%d candidates tried, none stands' % len(cands))
    return dict(row, taken=True, dropped=dropped, program=norm, before=before, after=cur, why='%d of %d gold forms taken a cover: %s' % (len(dropped), len(todo), say(before, cur)))


def child(stems):
    bits = P.Bits()
    for t in stems:
        print(json.dumps(one(t, bits)), flush=True)


class Rows:
    """The file the watchdog writes to: a stem with a candidate or a set_aside goes to rows.jsonl, any other to none.jsonl."""

    def __init__(self, rows, none):
        self.rows, self.none = rows, none

    def write(self, line):
        r = json.loads(line)
        if r.get('set_aside'):
            self.rows.write(json.dumps(dict(r, vsha=vsha(text_of(r['stem'])))) + '\n')
        elif r.get('candidates'):
            self.rows.write(line)
        else:
            self.none.write(json.dumps(dict(stem=r['stem'], vsha=r['vsha'])) + '\n')

    def flush(self):
        self.rows.flush()
        self.none.flush()


def run(args=()):
    """`run K N` takes the stems at positions K, K + N, ... of the order and writes rows-K.jsonl and none-K.jsonl."""
    k, n = (int(args[0]), int(args[1])) if args else (0, 1)
    out_p, none_p = (OUT, NONE) if n == 1 else (HERE + '/rows-%d.jsonl' % k, HERE + '/none-%d.jsonl' % k)
    done = set()
    for p in glob.glob(HERE + '/rows*.jsonl') + glob.glob(HERE + '/none*.jsonl'):
        for l in open(p):
            if l.endswith('\n'):
                r = json.loads(l)
                done.add((r['stem'], r.get('vsha')))
    left = [t for i, t in enumerate(x for x in F.order() if set_of(x)) if i % n == k and (t, vsha(text_of(t))) not in done]
    print(len(left), 'stems', flush=True)
    with open(out_p, 'a', buffering=1) as rows, open(none_p, 'a', buffering=1) as none:
        out = Rows(rows, none)
        while left:
            part, left = left[:C.PER_CHILD], left[C.PER_CHILD:]
            while part:
                part = C.watch(part, out, os.path.abspath(__file__))
                out.flush()


def show(stems):
    for t in stems:
        t0 = time.time()
        ls = program_lines(text_of(t))
        forms, out = [x for x in ls if not x.startswith('(OUT')], next(x for x in ls if x.startswith('(OUT'))
        cands, subs = candidates(t)
        match(P.Bar(t), forms, out, cands, subs)
        lab = [name_of(x) for x in forms]
        print(t, set_of(t), 'seconds', round(time.time() - t0, 1), 'candidates', len(cands), 'subs', len(subs), 'unread', {s['label']: s['unread'] for s in subs if s['unread']})
        for c in cands:
            print('  %s node %s draw %s subtree %s %s' % (c['run'], c['node'], c['draw'], [s['token'] for s in c['subs']], c['why'] or ''))
            for g in sorted(c['top']['to'] if not c['why'] else ()):
                why, lines, info = trial(ls, lab, c, g)
                print('    g%d %s  %s  %s' % (g, c['top']['to'][g][0], why or 'would try', info))
            if c['subs'] and not c['why']:
                print('    ' + c['top']['line'])


if __name__ == '__main__':
    {'child': child, 'cands': show}.get(sys.argv[1], run)(sys.argv[2:])
