"""Dev labeling layer: the variants of each task kept in one place, so later work reuses them and generates none again.

    python3 corpus.py OUT_DIR TASK [TASK ...]

Writes corpus/<task>.jsonl next to this folder: the base record, then one record per variant with its id, kind, source example, edits (`ops`), and
for an input variant its grid, and for an output variant from outvariants.py the input variant it comes from (`from`) and its whole output where
its size differs (`target`); and, as tagged by the analysis in OUT_DIR, its stored status, the tables it tests (`counted`) and the
postconditions it falsifies (`falsifies`). A variant that tests some table works as a test; one that falsifies a postcondition is a
counterexample. The tags hold for the feature library and the analysis that wrote OUT_DIR, which `tagged_by` names; the grids and edits hold
for any. refeature.py takes a corpus file as its source.
"""
import json
import sys
from pathlib import Path
import jsonl as J  # noqa: E402

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / 'features'))
import paths  # noqa: E402

CORPUS = paths.DATA / 'corpus'
KEEP = ('id', 'kind', 'source', 'ops', 'from', 'grid', 'target')


def main(out_dir, tasks):
    CORPUS.mkdir(exist_ok=True)
    for task in tasks:
        src = Path(out_dir) / (task + '.variants.jsonl')
        uses_path = Path(out_dir) / (task + '.uses.jsonl')
        uses = {u['id']: u for u in J.records(uses_path)}
        n = works = counter = 0
        out = []
        for r in J.records(src):
            rec = {k: r[k] for k in KEEP if k in r}
            if r['kind'] != 'base':
                u = uses.get(r['id'], {})
                rec.update(stored=r.get('stored', 'same'), stored_changed=r.get('stored_changed', []), stored_invalid=r.get('stored_invalid', r.get('stored_changed', [])), counted=u.get('counted', []),
                           falsifies=u.get('falsifies', []), tagged_by=str(Path(out_dir).resolve()))
                n += 1
                works += bool(rec['counted'])
                counter += bool(rec['falsifies'])
            out.append(rec)
        J.write_all(CORPUS / (task + '.jsonl'), out)
        print('%s: %d variants, %d test some table, %d falsify some postcondition' % (task, n, works, counter))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2:])
