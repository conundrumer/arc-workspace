#!/usr/bin/env python3
"""Fills a ramp soak folder of a kernel bundle, writes its manifest.json and packs the folder as a .tar.gz beside it.

  make-kit.py <time the pass bar was set> [checks JSON]

It reads build-params.json beside it. The files and the manifest start from the previous ramp soak of the base bundle. Config fields manifest, settings_add,
kit_manifest_edits and wheel_engine say what changes.
"""
import hashlib
import json
import math
import os
import pickle
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__)) + '/'
prm = json.load(open(HERE + 'build-params.json'))
cfg = prm['config']
NEW, C = prm['c'], prm['basec']
K = prm['out'].rstrip('/') + '/'
B = prm['bundle'].rstrip('/') + '/dataset/'
L = prm['base'].rstrip('/') + '/dataset/'
P = prm['prev_soak'].rstrip('/') + '/'
PREV = os.path.basename(P.rstrip('/'))
WHEEL = prm['wheel_name']
NAME = 'kernel-soak-%s-linux-ramp59-2400s' % NEW
S = K + NAME + '/'
sha = lambda p: hashlib.sha256(open(p, 'rb').read()).hexdigest()  # noqa: E731
GENERATED = ('manifest.json', 'last-ramp.json', 'run.sh')
DATASET_FILES = (WHEEL, 'choice5_o.pkl', 'code.bin', 'policy_model.pkl', 'relR4_o.pkl', 'supervisor.py', 'tilt_v1.json')

os.makedirs(S, exist_ok=True)
prev_m = json.load(open(P + 'manifest.json'))
PRIORS_SRC = prm['freeze'].rstrip('/') + '/live_priors.pkl'
priors = sha(PRIORS_SRC)
assert sha(B + 'live_priors.pkl') == priors, 'live_priors.pkl of the dataset differs from the freeze folder'
assert sha(P + 'live_priors.pkl') == sha(L + 'live_priors.pkl'), 'the previous soak and the base bundle have different priors'
for name, want in cfg['models']['files'].items():
    assert sha(B + name).startswith(want), name

# the files
for n in DATASET_FILES:
    shutil.copy(B + n, S + n)
shutil.copy(PRIORS_SRC, S + 'live_priors.pkl')
kit_files = HERE + 'kit-files/'
override = sorted(n for n in os.listdir(kit_files) if n not in GENERATED and os.path.isfile(kit_files + n)) if os.path.isdir(kit_files) else []
names = sorted(set(prev_m['reads']) | set(override))
from_p, from_kit = [], []
for n in names:
    if n in GENERATED or n in DATASET_FILES or n == 'live_priors.pkl':
        continue
    if n in override and not (os.path.exists(P + n) and sha(P + n) == sha(kit_files + n)):
        shutil.copy(kit_files + n, S + n)
        os.chmod(S + n, 0o755)
        from_kit.append(n)
    else:
        assert os.path.exists(P + n), 'the previous soak has no %s' % n
        master = K + n
        if os.path.exists(master) and (n.startswith('kernel-soak-') or n == 'meter-check.py'):
            assert sha(master) == sha(P + n), '%s of %s differs from the master copy' % (n, PREV)
        shutil.copy(P + n, S + n)
        from_p.append(n)
for n in ('kernel-soak-peak-read.py', 'meter-check.py', 'steers-check.py', 'kernel-soak-dag-read.py', 'gate-worker.sh', 'rss-log.sh', 'rss-peak.py', 'compare-ramp.py'):
    if os.path.exists(S + n):
        os.chmod(S + n, 0o755)

prev_read = json.load(open(P + 'soak-read.json'))
prev_peak = json.load(open(P + 'rss-peak.out'))
prev_dag = json.load(open(P + 'dag-read.json'))
assert prev_read['rss_kills'] == 0 and prev_read['rss_kill_cost'] == [] and prev_read['blocks'] == [], 'the previous soak did not pass'
assert prev_peak['limit_mib'] == 2888
whole = lambda x: format(math.floor(x + 0.5), ',')  # noqa: E731
PEAK_RSS, HEADROOM = prev_peak['peak_process_rss_mib'], prev_peak['headroom_mib']
assert PEAK_RSS > prev_read['peak_rss_max']
json.dump(dict(source='%s: soak-read.json, and rss-peak.out. peak_process_rss_mib is the highest rss_kib of the rows of its rss.log, as that soak had 0 RSS kills. Its progress rows peaked at %s MiB.' % (PREV, prev_read['peak_rss_max']),
               peak_process_rss_mib=PEAK_RSS, headroom_mib=HEADROOM, peak_rss_max=prev_read['peak_rss_max'], rss_kills=prev_read['rss_kills'], node_no_table=prev_read['node_no_table'], bins=prev_read['bins'], by_source=prev_read['by_source'],
               all_bins=prev_read['all_bins'], proposal_rate=prev_read['proposal_rate'], peak_process_at=prev_peak['at']), open(S + 'last-ramp.json', 'w'), indent=1)

# run.sh: the wheel hash and the priors hash
run = open(P + 'run.sh').read()
old_wheel, new_wheel = sha(P + WHEEL), sha(B + WHEEL)
old_priors = sha(P + 'live_priors.pkl')
assert run.count(old_wheel) == 1 and run.count(old_priors) == 1 and run.count('meter-check.py') == 1 and 'steers-check.py' in run, 'run.sh of %s does not hold the hashes of its wheel and priors once each' % PREV
for word in ('P_DAG', 'ORDER_FREE', 'ARCLOG_IDENT_SOURCE'):
    assert word not in run, word
run = run.replace(old_wheel, new_wheel).replace(old_priors, priors)
open(S + 'run.sh', 'w').write(run)
os.chmod(S + 'run.sh', 0o755)

# the manifest, from the previous soak's
m = json.load(open(P + 'manifest.json'))
m.pop('checks', None)
m.pop('result', None)
base = prev_read['proposal_rate']['search']
whl = sha(S + WHEEL)
assert whl == new_wheel
if m['wheel_engine'].get('sha256') != whl:
    assert cfg.get('wheel_engine'), 'the wheel differs from that of %s: config wheel_engine must say which engine it is' % PREV
m['wheel_engine'].update(cfg.get('wheel_engine') or {})
m['wheel_engine']['sha256'] = whl
m['wheel_engine'].setdefault('machine', 'pod, x86_64 wheel from this folder')
tasks = json.load(open(S + 'tasks.json'))
assert sorted(tasks) == sorted(json.load(open(P + 'tasks.json'))) and len(tasks) == 59
pri = pickle.load(open(S + 'live_priors.pkl', 'rb'))
if 'hand' in pri and isinstance(m['settings'].get('hand'), dict):
    assert m['settings']['hand'] == {k: pri['hand'][k] for k in ('unjoined', 'p_reexport', 'else_neg', 'mirror_not')}, 'settings.hand differs from pri[hand]: say the new values in kit_manifest_edits'

cover = prev_read['all_bins']
by_source = prev_read['by_source']
EVAL = sum(v['forms_covered'] for k, v in by_source.items() if k.endswith('eval-37'))
FOLD = sum(v['forms_covered'] for k, v in by_source.items() if k.endswith('train-fill'))
assert cover['forms_covered'] == EVAL + FOLD
REFUSED_LINES = int(re.search(r'^refused lines: (\d+)$', open(P + 'peak-read.out').read(), re.M)[1])
DROPPED = prev_read['drop_table']['drop:table: table past the memory room']
CPU = re.search(r'Model name:\s+(.*?) \d+-Core', open(P + 'cpu.txt').read())[1]


def rename(text):
    return text.replace('kernel-bundle-%s' % C, 'kernel-bundle-%s' % NEW).replace(PREV, NAME)


m['pod_job'] = m['pod_job'].replace(PREV, NAME)
assert NAME in m['pod_job'] and 'kernel-soak-peak-read.py' in m['pod_job'] and 'peak-read.out' in m['copy_back']['take']
mf = cfg['manifest']
m['commit'] = mf['commit']
m['what'] = mf.get('what') or rename(m['what'])
m['arm'] = mf.get('arm') or rename(m['arm'])
m['priors']['file'] = rename(m['priors']['file'])
m['stands_for']['reads_as'] = mf.get('reads_as') or rename(m['stands_for']['reads_as'])
if mf.get('reads_as_append'):
    m['stands_for']['reads_as'] += ' ' + mf['reads_as_append']
m['settings'] = dict(m['settings'], **(cfg.get('settings_add') or {}))
m['control']['previous_soak'] = PREV
m['measures'] = [x for x in m['measures'] if not x.startswith('a compare against')]
m['measures'].append('a compare against %s by bin' % PREV)
past_end = '%s had %d.' % (PREV, prev_read['past_end_kills'])
m['expected'] = dict(
    memory='%s reached %s MiB in rss.log with %d RSS kills, %s MiB under the 2,888 MiB limit, and its progress rows peaked at %s MiB. Read rss_kill_cost, the peak of rss.log and P6 of peak-read.out.' % (
        PREV, whole(PEAK_RSS), prev_read['rss_kills'], whole(HEADROOM), format(prev_read['peak_rss_max'], ',')),
    past_end_kills=re.sub(r'kernel-soak-\w+-linux-ramp59-2400s had \d+\.', past_end, m['expected']['past_end_kills']),
    base=dict(soak=PREV, search={k: base[k] for k in ('tasks', 'proposals_per_cpu_s', 'node_equal_per_1000_proposals', 'non_duplicate_forms_per_cpu_s')}))
assert past_end in m['expected']['past_end_kills']
wi = dict(m['watch_items'])
wi.update(
    peak_process_rss='The peak RSS of one worker process. Read the higher of peak_rss_max in soak-read.json, which is a worker row, the peak of rss-peak.py on rss.log, and the RSS of each kill line in soak.log. %s reached %s MiB in rss.log, %s MiB under the 2,888 MiB kill limit, with %d RSS kills, and its progress rows peaked at %s MiB.' % (
        PREV, whole(PEAK_RSS), whole(HEADROOM), prev_read['rss_kills'], format(prev_read['peak_rss_max'], ',')),
    key_fallback='The counter key:fallback in the worker end lines. table_key takes an order-free key for a table past KEY_ORDERS or KEY_CELLS and adds 1 for each such table. kernel-soak-dag-read.py sums it as counts.key_fallback in dag-read.json. kernel-soak-read.py does not read it. %s had %d.' % (PREV, prev_dag['counts']['key_fallback']),
    compare_reference='last-ramp.json holds the figures of %s, which compare-ramp.py reads. Its peak_process_rss_mib is the peak of its rss.log, %s MiB, and its headroom_mib is %s.' % (PREV, format(PEAK_RSS, ','), HEADROOM),
    forms_covered_reference='%s covered %s of %s gold forms (cover.out): eval %d, fold %d (the eval-37 and train-fill sources of by_source). kernel-soak-cover.py and compare-ramp.py give the figures of this soak against those.' % (
        PREV, cover['forms_covered'], format(cover['forms'], ','), EVAL, FOLD),
    guard_reference='%s had %d refused lines in P4 of peak-read.out and %d clauses dropped as drop:table: table past the memory room (drop_table in soak-read.json). The guard settings of this soak are in settings, and its counts are read against these.' % (
        PREV, REFUSED_LINES, DROPPED),
    cpu_reference='%s ran on %s (cpu.txt). The CPU of this run is in its cpu.txt, and proposals per CPU s depend on it.' % (PREV, CPU))
m['watch_items'] = wi
dfi = m['watch']['differs_from_the_find']
dfi['code'] = mf.get('differs_code') or re.sub(r'code\.bin at \w+', 'code.bin at %s' % NEW, dfi['code'], count=1)

bar = m['pass_bar']
bar['set_before_the_run'] = sys.argv[1]
LAST_PEAK = ('peak process RSS from rss.log, the largest rss_kib of its rows, in MiB, against the 2,888 MiB kill limit, with the headroom: rss-peak.py. This is a watch item. The last ramp soak, %s, reached %s MiB in rss.log, '
             '%s MiB under the limit, with %d RSS kills, and its progress rows peaked at %s MiB. A peak at or over 2,888 MiB is an RSS kill, a cost line') % (
    PREV, whole(PEAK_RSS), whole(HEADROOM), prev_read['rss_kills'], format(prev_read['peak_rss_max'], ','))
n_peak = [i for i, x in enumerate(bar['report']) if x.startswith('peak process RSS from rss.log')]
n_cmp = [i for i, x in enumerate(bar['report']) if x.startswith('a compare against kernel-soak-')]
assert len(n_peak) == 1 and len(n_cmp) == 1
bar['report'][n_peak[0]] = LAST_PEAK
bar['report'][n_cmp[0]] = re.sub(r'kernel-soak-\w+-linux-ramp59-2400s', PREV, bar['report'][n_cmp[0]])

# edits from the config: {path: 'a.b.c', op: set | append | replace, value | old, new}
def edit(doc, e):
    keys = e['path'].split('.')
    for k in keys[:-1]:
        doc = doc[k]
    last = keys[-1]
    op = e.get('op', 'set')
    if op == 'set':
        doc[last] = e['value']
    elif op == 'append':
        if isinstance(doc[last], list):
            doc[last].append(e['value'])
        else:
            doc[last] = doc[last] + ' ' + e['value']
    elif op == 'replace':
        assert e['old'] in doc[last], (e['path'], e['old'][:60])
        doc[last] = doc[last].replace(e['old'], e['new'])
    elif op == 'delete':
        assert last in doc, e['path']  # a delete of a key that isn't there is a stale config
        del doc[last]
    else:
        raise AssertionError(op)


for e in cfg.get('kit_manifest_edits', []):
    edit(m, e)
mention = {k: sorted(set(re.findall(r'[\w-]*%s[\w-]*' % C, json.dumps(m[k])))) for k in m if C in json.dumps(m[k])}
print('mentions of', C, 'outside the new names:', {k: v for k, v in mention.items()})

# files
reads = sorted(x for x in os.listdir(S) if x != 'manifest.json' and os.path.isfile(S + x))
m['reads'] = reads
m['sha256_16'] = {n: sha(S + n)[:16] for n in reads}
if len(sys.argv) > 2:
    m['checks'] = json.load(open(sys.argv[2]))
with open(S + 'manifest.json', 'w') as f:
    json.dump(m, f, indent=1)
t = K + NAME + '.tar.gz'
subprocess.run(['tar', '-czf', t, '--exclude', NAME + '/scratch', '--exclude', NAME + '/out', '--exclude', NAME + '/work-logs', '-C', K, NAME], check=True, stdin=subprocess.DEVNULL, env=dict(os.environ, COPYFILE_DISABLE='1'))
print('files from the kit-files override:', from_kit, '; from', PREV, ':', len(from_p))
print(NAME, sha(t), os.path.getsize(t), 'bytes', len(reads), 'files')
