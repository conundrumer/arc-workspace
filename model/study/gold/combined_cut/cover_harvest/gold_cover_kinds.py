"""Kinds of difference between the two clauses of each harvest pair, with counts and bits saved by kind, on the census bits of pair-census.jsonl and, where reread4 has the cover side, on the bits of record. Writes pair-kinds.jsonl in this folder.

  python3 gold_cover_kinds.py
"""
import collections, json, os, re, statistics

HERE = os.path.dirname(os.path.abspath(__file__))
LAB = re.compile(r'&[A-Za-z_0-9]+')


def tokens(line):
    """The clause body's tokens with labels as &_, variables as V and binding marks dropped, as a sorted list: equal lists hold the same atoms in another order or with other bindings."""
    x = LAB.sub('&_', line[line.index('&'):])
    x = re.sub(r'[*^]?\b[A-Z][A-Za-z0-9]*\b', 'V', x[x.index(' '):] if ' ' in x else '')
    return sorted(re.findall(r'[^\s()]+', x))


def kind(p):
    a, b = p['gold_parts'], p['cover_parts']
    rc = set(p['read_class'].values())
    if a['kind'] == 'DET' and a['component'] != b['component']:
        return 'DET component swap'
    if 'brought in' in rc or p['gold_out'] or p['brought']:
        return 'new subtree'
    if 'other gold form' in rc:
        return 'reads another gold form'
    if a['kind'] != 'INIT' and a['component'] and b['component'] and a['component'] == b['component'] and tokens(p['gold']) != tokens(p['cover']):
        return 'DET argument change'
    if tokens(p['gold']) == tokens(p['cover']):
        return 'same atoms, other order or binding'
    if b['atoms'] < a['atoms']:
        return 'drops an atom'
    if b['atoms'] > a['atoms']:
        return 'adds an atom'
    return 'same reads, other columns or sub-relation'


def main():
    census = {(r['stem'], r['gold_label']): r for r in map(json.loads, open(HERE + '/pair-census.jsonl'))}
    by = collections.defaultdict(list)
    with open(HERE + '/pair-kinds.jsonl', 'w') as out:
        for l in open(HERE + '/pairs.jsonl'):
            p = json.loads(l)
            c = census.get((p['stem'], p['gold_parts']['label']))
            g = sum(c['gold'].values()) if c and None not in c['gold'].values() else None
            v = sum(c['cover'].values()) if c and None not in c['cover'].values() else None
            k = kind(p)
            row = dict(stem=p['stem'], set=p['set'], kind=k, gold=p['gold'], cover=p['cover'], census_gold=g, census_cover=v, census_saved=None if None in (g, v) else round(g - v, 2),
                       record_gold=p['gold_side_bits'], record_cover=p['cover_side_bits'], record_saved=None if None in (p['gold_side_bits'], p['cover_side_bits']) else round(p['gold_side_bits'] - p['cover_side_bits'], 2),
                       worst_form=bool(c and g is not None and abs(max(c['gold'].values()) - p['stem_before']['worst']) < .01))
            out.write(json.dumps(row) + '\n')
            by[k].append(row)
    print('| Kind | Pairs | Training, 37, ramp | Census bits saved, median | Saved, quartiles | Pair held the worst form | Record saved, median (n) |')
    for k, rs in sorted(by.items(), key=lambda x: -len(x[1])):
        s = [r['census_saved'] for r in rs if r['census_saved'] is not None]
        q = statistics.quantiles(s, n=4) if len(s) > 1 else [0, 0, 0]
        rec = [r['record_saved'] for r in rs if r['record_saved'] is not None]
        sets = collections.Counter(r['set'] for r in rs)
        print('| %s | %d | %d, %d, %d | %.2f | %.2f to %.2f | %d | %s |' % (k, len(rs), sets['training'], sets['37'], sets['ramp'], statistics.median(s) if s else 0, q[0], q[2], sum(r['worst_form'] for r in rs), '%.2f (%d)' % (statistics.median(rec), len(rec)) if rec else '-'))


if __name__ == '__main__':
    main()
