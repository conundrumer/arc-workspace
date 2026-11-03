"""Slot-order pass over the gold of a gen dir, with sampler-worker's slot_order_check binary.
usage: norm.py extract <gen dir> <work dir> <shards>   writes <work>/in-<k>/<n>.sexp and <work>/manifest.tsv (n, kind, path)
       norm.py apply <work dir>                          replaces each file's text by <work>/out-<k>/<n>.sexp where there is one
kinds: gold (ast-corpus/<task>/pairs.jsonl.gz, field gold_sexp) and case (corpus/gen/cases/<task>/<case>.arclog)."""
import gzip, json, os, sys
from pathlib import Path

mode = sys.argv[1]
if mode == 'extract':
    gen, work, shards = Path(sys.argv[2]), Path(sys.argv[3]), int(sys.argv[4])
    work.mkdir(parents=True, exist_ok=True)
    for k in range(shards):
        (work / f'in-{k}').mkdir(exist_ok=True)
    rows = []
    for task in ([] if os.environ.get('NOGOLD') else sorted(os.listdir(gen / 'ast-corpus'))):
        f = gen / 'ast-corpus' / task / 'pairs.jsonl.gz'
        if not f.exists():
            continue
        line = json.loads(gzip.open(f, 'rt').readline())
        rows.append(('gold', str(f), line['gold_sexp']))
    cases = gen / 'corpus' / 'gen' / 'cases'
    for task in ([] if os.environ.get('NOCASES') else sorted(os.listdir(cases))):
        d = cases / task
        want = None
        gf = gen / 'ast-corpus' / task / 'pairs.jsonl.gz'
        if gf.exists():
            want = json.loads(gzip.open(gf, 'rt').readline())['case'].replace('$', '').replace(' ', '+') + '.arclog'
        for name in sorted(os.listdir(d)):
            sel = os.environ.get('CASES')
            if sel == 'named' and name != want or sel == 'others' and name == want:
                continue
            if name.endswith('.arclog'):
                rows.append(('case', str(d / name), (d / name).read_text()))
    with open(work / 'manifest.tsv', 'w') as m:
        for n, (kind, path, text) in enumerate(rows):
            (work / f'in-{n % shards}' / f'{n}.sexp').write_text(text)
            m.write(f'{n}\t{kind}\t{path}\n')
    print(f'extracted {len(rows)} programs into {shards} shards')
else:
    work = Path(sys.argv[2])
    done = kept = 0
    for line in open(work / 'manifest.tsv'):
        n, kind, path = line.rstrip('\n').split('\t')
        out = next((p for p in work.glob(f'out-*/{n}.sexp')), None)
        if out is None:
            kept += 1
            continue
        text = out.read_text()
        if kind == 'case':
            Path(path + '.tmp').write_text(text)
            os.replace(path + '.tmp', path)
        else:
            rec = json.loads(gzip.open(path, 'rt').readline())
            rec['gold_sexp'] = text
            tmp = path + '.tmp'
            with gzip.open(tmp, 'wt') as f:
                f.write(json.dumps(rec) + '\n')
            os.replace(tmp, path)
        done += 1
    print(f'rewrote {done}, kept the text of {kept}')
