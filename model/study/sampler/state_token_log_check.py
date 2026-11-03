"""For each line of a state-search token log: the QueryHash of a fresh decoder fed the logged ids, and of a fresh decode of the scope and query
texts, beside the stored hash."""
import json, sys, time
import arclog, live, superdag as D
LOG, KIT = sys.argv[1], sys.argv[2]
D.S.TASKS = KIT + '/data/tasks/'
L = [json.loads(l) for l in open(LOG)]
sampler = live.Sampler(KIT + '/models-tk')
sess, d, _ = D.session_of(L[0]['task'])
run = D.Run(sampler.pri, sess, 0, time.monotonic() + 600, d, live.Limits())
n = fed_eq = text_eq = fed_text_eq = fail = 0
for r in L:
    n += 1
    try:
        dec = run.root.fork()
        for t in r['fed']:
            dec.step(t)
        hf = '%032x' % dec.query_hash(-1)
    except Exception:  # noqa: BLE001
        fail += 1
        continue
    p = arclog.StudyProgram.from_sexp('\n'.join(r['scope'] + [r['text'], live.READER_OUT]), sess.settings)
    ht = '%032x' % p.query_hash(len(r['scope']))
    fed_eq += hf == r['stored']; text_eq += ht == r['stored']; fed_text_eq += hf == ht
print('lines %d, fed replay failed %d; fed = stored %d, text = stored %d, fed = text %d' % (n, fail, fed_eq, text_eq, fed_text_eq))
