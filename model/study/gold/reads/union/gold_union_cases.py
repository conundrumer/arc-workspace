"""The programs of the union gold of one task set, one line per program: the pinned program (case `pinned`, source view-final, where view-final has one) and every case of each task's solver from the latest empty-gold publication. Writes cases-<set>.jsonl and its sha256 in GOLD_UNION_DIR (default work/lm/data-study/gold/gold-union).

  .venv/bin/python gold_union_cases.py SET      SET: train, dev or held-out
"""
import json, os, sys
import gold_case_counts as K
from gold_union_fits import set_of
import study_zst as Z  # on the path since gold_union_fits is imported

OUT = os.environ.get('GOLD_UNION_DIR', '/Users/davidlu/code/arc-workspace/work/lm/data-study/gold/gold-union')


def main():
    want = sys.argv[1]
    pubs = K.publications()
    path = OUT + '/cases-%s.jsonl' % want
    with Z.open_text(path, 'w', atomic=True) as out:  # a reader never sees a part-written file
        for t in K.union_tasks(pubs):
            if set_of(t) != want:
                continue
            if K.pinned(t) is not None:
                out.write(json.dumps(dict(task=t, case='pinned', gold_sexp=K.pinned(t), source='gold-v3-combined-cut/view-final')) + '\n')
            if t in pubs:
                p, res = pubs[t]
                for c in res['cases']:
                    out.write(json.dumps(dict(task=t, case=c['case'], concept=bool(c.get('concept')), gold_sexp=c.get('filtered_program') or c.get('original_program') or '',
                                              source=p.replace(K.G, ''))) + '\n')
    sha = Z.write_sidecar_sha256(path)  # the hash of the text
    print(want, sha)


if __name__ == '__main__':
    main()
