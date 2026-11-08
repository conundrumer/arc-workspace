"""A check of the patch's Run.admission_key and Run.closure_verdict on the whole-pool bank: the scope is the forms before the refused DET F in
scope order, F's body tokens are the drawn tokens, and the check prints the count name that the patch gives.

  <python> retest_check.py BANK TASK_JSON PATCHED_SAMPLER_DIR KIT_SAMPLER_DIR
"""
import collections
import json
import os
import sys
import types

sys.path.insert(0, '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/search-worker/joint-tools')
import search_node_score_parity as PA  # noqa: E402

sys.path.insert(0, sys.argv[4])
sys.path.insert(0, sys.argv[3])
os.environ['ADMISSION_RETEST'] = '1'
import live  # noqa: E402

arclog = live.arclog
SETTINGS = dict(rule_tests=False, table_work_cap=1 << 21, static_pruning=True)
bank = PA.load_bank(sys.argv[1])
forms = bank['forms']
task = json.load(open(sys.argv[2]))
settings = arclog.DecodeSettings(relations=65536, **SETTINGS)
session = arclog.Session(arclog.Task.from_json(json.dumps(task), arclog.World.Open), settings, session_bytes=2 << 30)
every = sorted(forms, key=lambda f: (forms[f].depth, f))
F = 209
scope = every[:every.index(F)]
texts = [forms[f].text for f in scope]
ids, model, paths = arclog.StudyProgram.from_sexp('\n'.join(texts + [forms[F].text, live.READER_OUT]), settings).decode_stream()
V = session.vocabulary
dec, made, mine = session.decoder(), collections.defaultdict(list), []
for t, m, p in zip(ids, model, paths):
    if not m:
        continue
    if p[0] < len(texts):
        made[p[0]] += [x for x in dec.step(t)[0] if V.kind(x) == 'relation']
    elif p[0] == len(texts):
        mine.append(t)
print('F model tokens', [V.name(t) for t in mine])
try:
    g = dec.fork()
    for t in mine:
        g.step(t)
    print('F over the scope: admitted')
except arclog.Refusal as e:
    print('F over the scope: refused', e)
run = types.SimpleNamespace(V=V, session=session, root=session.decoder(), scoped=(tuple(texts), None, None), c=collections.Counter())
run.closure_verdict = types.MethodType(live.Run.closure_verdict, run)
pg = types.SimpleNamespace(made=dict(made), kinds=[forms[f].kind for f in scope])
drawn = mine[1:-1]  # the DET token opens the form and the last END closes it, as Run.open_form and Run.end step them
print('count name:', live.Run.admission_key(run, pg, drawn, arclog.Refusal('DetAdmission(Bound(Assignments { cap: 256 }))')))
print('counts', dict(run.c))
