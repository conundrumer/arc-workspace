"""Replays the corpus programs and writes one row per form: shape, DAG facts, link.

  ib_corpus.py --shard K/N [--limit M]

Stems go by index mod N in the sorted list of corpus stems. Appends to R/corpus/rows-KofN.jsonl (with --limit, R/corpus-smoke/). One line per form
({stem, g, kind, shape, facts, link, holds, ident_only, nscope}) and one {"rec": "task", ...} line per stem, written together. A rerun skips stems
that have a task line. The line {"rec": "shard_done"} comes when the shard has no stem left. The process exits with status 75 after a stem
when its peak RSS passes 3 GiB; the driver loop starts it again.
"""
import argparse
import json
import os
import sys
import time

import ib_lib as L

RSS_EXIT_GIB = 3.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--shard', required=True)
    ap.add_argument('--limit', type=int)
    a = ap.parse_args()
    k, n = (int(x) for x in a.shard.split('/'))
    L.setup()
    pin_file = L.R + '/corpus-pin.json'
    if not os.path.exists(pin_file):
        json.dump(L.corpus_pin(), open(pin_file, 'w'), indent=1)
        print('wrote', pin_file, flush=True)
    out_dir = L.R + ('/corpus-smoke' if a.limit else '/corpus')
    os.makedirs(out_dir, exist_ok=True)
    out = '%s/rows-%dof%d.jsonl' % (out_dir, k, n)
    stems = [s for i, s in enumerate(L.corpus_stems()) if i % n == k]
    done = set()
    if os.path.exists(out):
        for line in open(out):
            try:
                x = json.loads(line)
            except ValueError:
                continue
            if x.get('rec') == 'task':
                done.add(x['stem'])
            elif x.get('rec') == 'shard_done':
                print('shard %d/%d is done' % (k, n), flush=True)
                return 0
    todo = [s for s in stems if s not in done]
    if a.limit:
        todo = todo[:a.limit]
    print('shard %d/%d: %d stems, %d done, %d to do' % (k, n, len(stems), len(done), len(todo)), flush=True)
    sampler = L.live.Sampler(L.MODELS['corpus'])
    fh = open(out, 'a')
    t0 = time.time()
    for c, stem in enumerate(todo):
        t1 = time.time()
        forms, rows, err = [], [], None
        try:
            forms = L.forms_of(L.corpus_gold(stem))
            sess, d = L.session_of(L.task_path(stem, 'corpus'))
            cts, err = L.replay(sampler, d, sess, forms)
            info, _ = L.analyze(forms, cts)
            for x in info:
                rows.append(dict(stem=stem, g=x['i'], kind=x['kind'], shape=x['shape'], facts=x['facts'], link=x['link'], holds=x['holds'], ident_only=x['ident_only'], nscope=x['nscope']))
            del sess, cts
        except Exception as e:  # noqa: BLE001
            err = '%s: %s' % (type(e).__name__, str(e)[:120])
        task = dict(rec='task', stem=stem, forms=len(forms), replayed=len(rows), error=err, seconds=round(time.time() - t1, 2))
        fh.write(''.join(json.dumps(r, separators=(',', ':')) + '\n' for r in rows) + json.dumps(task, separators=(',', ':')) + '\n')
        fh.flush()
        rate, rest = L.eta(c + 1, len(todo), t0)
        print('[%d/%d] %s %d forms, %d rows, %.2fs%s | %.2f s a stem, ETA %.0f s, rss %.2f GiB' % (
            c + 1, len(todo), stem, len(forms), len(rows), time.time() - t1, ' ERROR ' + err if err else '', rate, rest, L.rss_gib()), flush=True)
        if L.rss_gib() > RSS_EXIT_GIB and c + 1 < len(todo):
            print('rss past %.1f GiB: exit for a restart' % RSS_EXIT_GIB, flush=True)
            return 75
    if not a.limit:
        L.append_line(fh, dict(rec='shard_done', shard='%d/%d' % (k, n), stems=len(stems)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
