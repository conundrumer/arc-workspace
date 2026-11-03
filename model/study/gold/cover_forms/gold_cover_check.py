"""Reads every program of corpus-view with the reader of the priors fit, S.corpus_forms, and compares the count of forms with the program's lines. Then reads a sample of the swapped programs with arclog.StudyProgram.from_sexp and steps each to its end. Run with SAMPLER_CORPUS set to the view.

  SAMPLER_CORPUS=<view>/ <runtime python> gold_cover_check.py [SAMPLE]
"""
import gzip, json, os, random, sys
from pathlib import Path

sys.path.insert(0, os.environ['SAMPLER_CODE'])
import arclog
import sample2_col as S

ROOT = Path('/Users/davidlu/code/arc-workspace')
n = int(sys.argv[1]) if len(sys.argv) > 1 else 12
good, bad = 0, []
for t in sorted(os.listdir(S.CORPUS)):
    forms = S.corpus_forms(t)
    with gzip.open(S.CORPUS + t + '/pairs.jsonl.gz', 'rt') as f:
        r = json.loads(f.readline())
    if forms and len(forms) == sum(1 for x in r['gold_sexp'].splitlines() if x.strip()):
        good += 1
    else:
        bad.append(t)
print('reader', S.CORPUS, 'read', good, 'not read', len(bad), bad[:10], flush=True)
stems = [json.loads(l) for l in open('view-stems.jsonl')]
cover = sorted(s['stem'] for s in stems if s['source'] == 'cover')
ended = 0
sample = random.Random(0).sample(cover, min(n, len(cover)))
for t in sample:
    with gzip.open(S.CORPUS + t + '/pairs.jsonl.gz', 'rt') as f:
        text = json.loads(f.readline())['gold_sexp']
    sess = arclog.Session(arclog.Task.from_json((ROOT / 'data/tasks' / f'{t}.json').read_text(), arclog.World.Closed), arclog.DecodeSettings(table_work_cap=1 << 20))
    i, m, _ = arclog.StudyProgram.from_sexp(text, sess.settings).decode_stream()
    d = sess.decoder()
    for a, b in zip(i, m):
        if b:
            d.step(int(a))
    ended += bool(d.ended)
print('sample', len(sample), 'ended', ended, sample)
