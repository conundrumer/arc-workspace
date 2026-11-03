"""The engine's QueryHash of each query in state-search jobs, beside the hash the run stored.

    PYTHONPATH=<site with query_hash>:model/study/sampler ARCLOG_IDENT_SOURCE=value <python> rehash_query_hash.py out/NAME/TASK ...

Per job, it writes <bank>.query_hash.jsonl, one line per query: the hash the run stored, the engine's QueryHash (as hex), or the
error where the engine refuses the program. A query's program is its use closure in dependency order, with the query last and the
reader's OUT after it; the hash is StudyProgram.query_hash at the query's index. A job whose file exists is skipped.
"""
import glob
import json
import os
import pickle
import sys
import time

import arclog
import live
import superdag as D


def closure(qs, d):
    got, todo = set(), [d]
    while todo:
        x = todo.pop()
        if x not in got:
            got.add(x)
            todo += qs[x].parents
    return sorted(got - {d}, key=lambda x: (qs[x].depth, x)) + [d]


def main():
    settings = arclog.DecodeSettings(relations=D.RELATIONS, **D.SETTINGS)
    t0 = time.time()
    for i, w in enumerate(sys.argv[1:]):
        bank = next(iter(glob.glob(w + '/work/*.out.jsonl.bank')), None)
        if not bank or os.path.exists(bank + '.query_hash.jsonl'):
            continue
        qs = pickle.load(open(bank, 'rb'))['forms']
        ok = bad = 0
        with open(bank + '.query_hash.jsonl.tmp', 'w') as out:
            for d, rec in sorted(qs.items()):
                order = closure(qs, d)
                try:
                    prog = arclog.StudyProgram.from_sexp('\n'.join([qs[x].text for x in order] + [live.READER_OUT]), settings)
                    h, err = '%032x' % prog.query_hash(len(order) - 1), None
                    ok += 1
                except Exception as e:  # noqa: BLE001
                    h, err = None, repr(e)[:200]
                    bad += 1
                stored = getattr(rec, 'query_hash', None) or getattr(rec, 'definition_hash', None) or getattr(rec, 'fhash', None)
                out.write(json.dumps(dict(stored=stored, query_hash=h, error=err, text=rec.text)) + '\n')
        os.replace(bank + '.query_hash.jsonl.tmp', bank + '.query_hash.jsonl')
        print('[%d/%d] %s: %d queries hashed, %d refused, %.0f s' % (i + 1, len(sys.argv) - 1, w, ok, bad, time.time() - t0), flush=True)


if __name__ == '__main__':
    main()
