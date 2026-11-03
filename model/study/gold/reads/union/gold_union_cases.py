"""The programs of the union gold of one task set, one line per program: the pinned program (case `pinned`, source view-final) and every case of each task's solver from the latest empty-gold publication, with `excluded` true for the cases gen-v3's excluded-case-files.tsv lists. Writes cases-<set>.jsonl and its sha256 in work/lm/data-study/gold/gold-union.

  python3 gold_union_cases.py SET      SET: train, dev or held-out
"""
import hashlib, json, os, sys
import gold_case_counts as K
from gold_union_fits import set_of
from gold_union_identity import D

OUT = os.environ.get('GOLD_UNION_DIR', '/Users/davidlu/code/arc-workspace/work/lm/data-study/gold/gold-union')


def main():
    want = sys.argv[1]
    pubs, ex = K.publications(), K.excluded()
    path = OUT + '/cases-%s.jsonl' % want
    with open(path, 'w') as out:
        for t in sorted(os.listdir(D + 'gold/gold-v3-combined-cut/view-final')):
            if set_of(t) != want:
                continue
            out.write(json.dumps(dict(task=t, case='pinned', gold_sexp=K.pinned(t), excluded=False, source='gold-v3-combined-cut/view-final')) + '\n')
            if t in pubs:
                p, res = pubs[t]
                for c in res['cases']:
                    out.write(json.dumps(dict(task=t, case=c['case'], concept=bool(c.get('concept')), gold_sexp=c.get('filtered_program') or c.get('original_program') or '',
                                              excluded=c['case'].replace('$', '').replace(' ', '+') in ex[t], source=p.replace(K.G, ''))) + '\n')
    sha = hashlib.sha256(open(path, 'rb').read()).hexdigest()
    open(path + '.sha256', 'w').write('%s  %s\n' % (sha, os.path.basename(path)))
    print(want, sha)


if __name__ == '__main__':
    main()
