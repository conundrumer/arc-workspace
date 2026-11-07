"""How far a production is fixed by the tables it reads and writes. Prints the counts for each set and writes readsets-SET.json in work/lm/data-study/gold/gold-union.

- A read set is the set of graph tables a production reads, within one task. Base relations such as `input` are not graph tables, so productions that read only base relations share the empty read set; the counts are given with it and without it.
- A head is one graph table (one merge key) a production makes; a production with several heads counts once for each.
- Per read set: the count of distinct heads. Per (read set, head) pair: the count of distinct productions (union identities), which differ in text.
- Per depth: the depth of the head, from graph-tables-SET.jsonl, over the productions with a nonempty read set; a read set's heads there are its heads at that depth.
- Counts of 10 or more are binned at 10.
- A pair with 2 or more texts is `within_case` when one case's text (union-keys-SET.jsonl) has 2 or more of them, as OR branches of one table, and `across_cases` otherwise.

  <runtime python> gold_union_readsets.py SET [SET ...]    (the env is needed for the case split)
"""
import collections, json, sys
from gold_union import forms_of, program_lines
import study_zst as Z  # on the path since gold_union is imported

OUT = '/Users/davidlu/code/arc-workspace/work/lm/data-study/gold/gold-union/'


def case_idents(s):
    """Per task, the set of form identities of each case."""
    out = collections.defaultdict(list)
    for l in Z.open_text(OUT + 'union-keys-%s.jsonl' % s):
        c = json.loads(l)
        fs, _ = forms_of([x for x in program_lines(c['text']) if not x.startswith('(OUT')])
        out[c['task']].append({f['ident'] for f in fs})
    return out


def counts(prods, cases):
    heads, texts = collections.defaultdict(set), collections.defaultdict(set)
    for p in prods:
        rs = (p['task'], frozenset(p['reads']))
        for h in p['heads']:
            heads[rs].add(h)
            texts[rs, h].add(p['ident'])
    return dict(
        read_sets=len(heads),
        one_head=round(sum(len(v) == 1 for v in heads.values()) / max(1, len(heads)), 3),
        heads_per_read_set=dict(sorted(collections.Counter(min(len(v), 10) for v in heads.values()).items())),
        pairs=len(texts),
        pairs_with_2_texts=round(sum(len(v) >= 2 for v in texts.values()) / max(1, len(texts)), 3),
        texts_per_pair=dict(sorted(collections.Counter(min(len(v), 10) for v in texts.values()).items())),
        several_texts=dict(collections.Counter('within_case' if any(len(v & c) >= 2 for c in cases[t]) else 'across_cases' for ((t, _), _h), v in texts.items() if len(v) >= 2)))


def main():
    out = {}
    for s in sys.argv[1:]:
        depth = {(t['task'], t['table']): t['depth'] for t in map(json.loads, Z.open_text(OUT + 'graph-tables-%s.jsonl' % s))}
        prods = [json.loads(l) for l in Z.open_text(OUT + 'graph-prods-%s.jsonl' % s)]
        cases = case_idents(s)
        nonempty = [p for p in prods if p['reads']]
        r = dict(all=counts(prods, cases), without_empty=counts(nonempty, cases), per_head_depth={})
        by = collections.defaultdict(list)
        for p in nonempty:
            for h in p['heads']:
                by[depth.get((p['task'], h))].append(dict(p, heads=[h]))
        for d in sorted(by, key=lambda x: (x is None, x if x is not None else 0)):
            r['per_head_depth'][str(d)] = counts(by[d], cases)
        out[s] = r
        print(s, json.dumps(r['all']))
        print(s, 'without empty', json.dumps(r['without_empty']))
        for d, c in r['per_head_depth'].items():
            print('  depth', d, json.dumps(c))
        json.dump(r, open(OUT + 'readsets-%s.json' % s, 'w'), indent=1)


if __name__ == '__main__':
    main()
