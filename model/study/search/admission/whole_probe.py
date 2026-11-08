"""Where and why the whole-pool scope of a bank is refused, and what part of it the refusal needs.

  <python> -I whole_probe.py BANK TASK_JSON [SECONDS]

It orders every form of the bank as a scope is ordered (depth, then form id), replays the forms into one decoder token by token, as live.Run.scope
does with no step_tables, and stops at the first refused form F. Then it replays these programs, each in a new decoder of the same session:
  closure   F with its ancestors
  part      the DET forms before F that share a part with F (one reads the other at any depth, joined over the chain), F, and their ancestors
  others    the prefix up to F with the part's DET forms and the forms that read them left out, and then F's closure
It prints one JSON line for each.
"""
import json
import sys
import time

sys.path.insert(0, '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/search-worker/joint-tools')
import search_node_score_parity as PA  # noqa: E402

import arclog  # noqa: E402

SETTINGS = dict(rule_tests=False, table_work_cap=1 << 21, static_pruning=True)
READER_OUT = '(OUT (input ^P ^Col))'
T0 = time.perf_counter()
LIMIT = float(sys.argv[3]) if len(sys.argv) > 3 else 15.0

bank = PA.load_bank(sys.argv[1])
forms = bank['forms']
with open(sys.argv[2]) as f:
    task = json.load(f)
settings = arclog.DecodeSettings(relations=65536, **SETTINGS)
session = arclog.Session(arclog.Task.from_json(json.dumps(task), arclog.World.Open), settings, session_bytes=2 << 30)


def replay(fids):
    """(the place of the refused form or None, the refusal text, seconds) of a decode of the forms fids in their order."""
    t0 = time.perf_counter()
    texts = [forms[f].text for f in fids]
    ids, model, paths = arclog.StudyProgram.from_sexp('\n'.join(texts + [READER_OUT]), settings).decode_stream()
    dec = session.decoder()
    for (t, m, p) in zip(ids, model, paths):
        if not m:
            continue
        if p[0] >= len(texts):
            break
        try:
            dec.step(t)
        except arclog.Refusal as e:
            return p[0], str(e), time.perf_counter() - t0
        if time.perf_counter() - T0 > LIMIT:
            return -1, 'probe time limit', time.perf_counter() - t0
    return None, '', time.perf_counter() - t0


anc = {}


def ancestors(f):
    if f not in anc:
        got, todo = set(), list(forms[f].parents)
        while todo:
            g = todo.pop()
            if g not in got:
                got.add(g)
                todo += forms[g].parents
        anc[f] = frozenset(got)
    return anc[f]


def order(fids):
    return sorted(set(fids), key=lambda f: (forms[f].depth, f))


every = order(forms)
at, why, secs = replay(every)
out = dict(step='whole', forms=len(every), dets=sum(forms[f].kind == 'DET' for f in every), refused_at=at, refusal=why, seconds=round(secs, 2))
print(json.dumps(out), flush=True)
if at is None or at < 0:
    sys.exit(0)
F = every[at]
prefix = every[:at + 1]
dets = [f for f in prefix if forms[f].kind == 'DET']
# the part of F among the DETs of the prefix: join two DETs where one is an ancestor of the other, until no DET joins
part, grew = {F}, True
while grew:
    grew = False
    for d in dets:
        if d not in part and any(d in ancestors(p) or p in ancestors(d) for p in part):
            part.add(d)
            grew = True
closure_F = order({F} | ancestors(F))
part_forms = order(set(part) | set().union(*(ancestors(d) for d in part)))
in_part = [d for d in part]
print(json.dumps(dict(step='F', form=F, kind=forms[F].kind, depth=forms[F].depth, closure_forms=len(closure_F), closure_dets=sum(forms[f].kind == 'DET' for f in closure_F),
                      part_dets=len(part), part_forms=len(part_forms), part_dets_outside_closure=len(part - set(closure_F)), text=forms[F].text[:300])), flush=True)
for name, fids in (('closure', closure_F), ('part', part_forms)):
    at2, why2, s2 = replay(fids)
    print(json.dumps(dict(step=name, forms=len(fids), dets=sum(forms[f].kind == 'DET' for f in fids), refused_at=at2, refusal=why2, seconds=round(s2, 2))), flush=True)
drop = set(part) - {F}
others = [f for f in prefix if f not in drop and not (ancestors(f) & drop) and f != F]
others_F = order(set(others) | set(closure_F))
at3, why3, s3 = replay(others_F)
print(json.dumps(dict(step='others', forms=len(others_F), dets=sum(forms[f].kind == 'DET' for f in others_F), refused_at=at3, refusal=why3, seconds=round(s3, 2))), flush=True)
print(json.dumps(dict(step='end', seconds=round(time.perf_counter() - T0, 2))), flush=True)
