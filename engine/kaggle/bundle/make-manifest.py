#!/usr/bin/env python3
"""Writes the bundle's manifest.json from the base bundle's fields, this bundle's files and the check results in this folder. A check of run-rest.sh with no result in times.txt is written as pending.

It reads build-params.json beside it. Config fields manifest, settings_add, code_notes, bundle_manifest_edits, arclog_tests and wheel_engine say what changes.
"""
import hashlib
import json
import os
import re
import sys
import tarfile

HERE = os.path.dirname(os.path.abspath(__file__)) + '/'
sys.path.insert(0, HERE)
import pass_conditions  # noqa: E402

prm = json.load(open(HERE + 'build-params.json'))
cfg = prm['config']
C, LASTC = prm['c'], prm['basec']
K = prm['out'].rstrip('/') + '/'
B = prm['bundle'].rstrip('/') + '/'
H = HERE
BASE = prm['base'].rstrip('/') + '/'
FREEZE = prm['freeze'].rstrip('/') + '/'
SITE = prm['mac_site']
SITE_NAME = os.path.basename(SITE.rstrip('/'))
sha = lambda p: hashlib.sha256(open(p, 'rb').read()).hexdigest()  # noqa: E731
last = json.load(open(BASE + 'manifest.json'))
wheel = B + 'dataset/' + prm['wheel_name']
got = sha(wheel)
assert got == sha(prm['wheel']), 'the wheel of dataset/ differs from the config wheel'
if got != last['wheel_sha256']:
    assert cfg.get('wheel_engine'), 'the wheel differs from that of %s: config wheel_engine must say which engine it is' % LASTC
mac = sha(prm['mac_wheel']) if prm.get('mac_wheel') else None
so = sha(SITE + '/arclog/arclog.abi3.so')
assert so == prm['so_sha']
for name, want in cfg['models']['files'].items():
    assert sha(B + 'dataset/' + name).startswith(want), name
    assert sha(FREEZE + name) == sha(B + 'dataset/' + name), name
priors = sha(B + 'dataset/live_priors.pkl')
t = tarfile.open(B + 'dataset/code.bin')
tb = tarfile.open(BASE + 'dataset/code.bin')
src12 = lambda tar, n: hashlib.sha256(tar.extractfile('model/study/sampler/' + n).read()).hexdigest()[:12]  # noqa: E731
names = sorted(os.path.basename(n) for n in t.getnames() if re.fullmatch(r'model/study/sampler/[^/]+\.py', n))
base_names = {os.path.basename(n) for n in tb.getnames() if re.fullmatch(r'model/study/sampler/[^/]+\.py', n)}
changed = {n: dict(base=src12(tb, n) if n in base_names else None, new=src12(t, n)) for n in names if n not in base_names or src12(tb, n) != src12(t, n)}
sup_sha = sha(B + 'dataset/supervisor.py')
times = {}  # check name -> its runs in order, each (seconds, exit code, finished)
for line in open(H + 'times.txt'):
    m = re.match(r'(\S+) (\d+) s, exit (\d+), (\S+)', line)
    times.setdefault(m[1], []).append((int(m[2]), int(m[3]), m[4]))
KIT_CHECKS = ('gate-80a900e0', 'kit-start-74dd1130')  # they read the kit folder, so a run before the kit exists fails
kit_made = os.path.getmtime(K + 'kernel-soak-%s-linux-ramp59-2400s.tar.gz' % C)
iso = lambda z: __import__('datetime').datetime.strptime(z, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=__import__('datetime').timezone.utc).timestamp()  # noqa: E731
failed_first = {n for n, runs in times.items() if any(r[1] != 0 and not (n in KIT_CHECKS and iso(r[2]) < kit_made) for r in runs[:-1])}
assert failed_first <= {'fault-test', 'code-vs-kit'}, 'a check other than the fault test and code-vs-kit failed before it passed: %s' % sorted(failed_first)
extra_pass = cfg.get('pass_extra')
EXPECT = None
mm = re.search(r"^EXPECT = '([^']*)'", open(H + 'kit-files/kernel-soak-dag-read.py').read(), re.M) if os.path.exists(H + 'kit-files/kernel-soak-dag-read.py') else None
if mm:
    EXPECT = mm[1]
SESSION_MIB = last['settings'].get('session_mib')


def read(name):
    return open(H + 'check-%s.txt' % name, errors='replace').read()


def passed(name, text=None):
    """The step of check `name`: its last run, which must have exited 0 and met its conditions."""
    seconds, code, finished = times[name][-1]
    assert code == 0, name
    text = read(name) if text is None else text
    bad = pass_conditions.failures(name, read(name), C, extra_pass, EXPECT, SESSION_MIB)
    assert not bad, (name, bad)
    return dict(result='passed', commit=C, seconds=seconds, finished=finished, read=text)


def lines(name, pattern):
    m = re.search(pattern, read(name))
    assert m, (name, pattern)
    return m


def excerpt(name):
    return [x[:200] for x in read(name).splitlines()[:12]]


REST = re.findall(r'run-check\.sh (\S+)', open(H + 'run-rest.sh').read())
RAN = [n for n in REST if n in times]
assert len(RAN) in (0, len(REST)), 'some of the checks of run-rest.sh ran and some did not: %s' % sorted(set(REST) - set(RAN))
RAN = bool(RAN)
for q in pass_conditions.QUICK + tuple((cfg.get('extra_quick_checks') or {})):
    assert q in times, 'quick check %s has no result in times.txt' % q
steps = {}
if RAN:
    seed = lines('seed-8f3a5a89', r'end: None, (\d+) draws, (\d+) forms, (\d+) nodes, (\d+) candidates, (\d+) MiB, (\d+) s\ncandidates (\d+) right on test (\d+)')
    assert SITE_NAME + '/arclog/__init__.py' in read('seed-8f3a5a89')
    fill = {x: lines('fill-' + x, r'refused:loo (\d+) fill lines (\d+) candidates bytes (\d+)') for x in ('135a2760', '80a900e0')}
    gate = read('gate-80a900e0')
    gr = re.search(r"gate_records \{'files': (\d+), 'bytes': (\d+), 'records': (\d+)", gate)
    gf = re.search(r'refused:loo (\d+) fill lines (\d+)', gate)
    guard = read('guard-269e22fb')
    gt = re.search(r'table lines (\d+), refused table lines (\d+), stacks in the log (\d+)', guard)
    g_drop = [int(x) for x in re.findall(r"'drop:table:[^']*': (\d+)", guard)]
    g_refused = [int(x) for x in re.findall(r"'memory:table refused': (\d+)", guard)]
    assert gr and gf and gt and g_drop and g_refused
    kit = read('kit-start-74dd1130')
    km = re.search(r'peak meter off lines (\d+), sampler lines (\d+), generations (\d+)', kit)
    ke = re.search(r'end: None, (\d+) draws, (\d+) forms, (\d+) nodes, (\d+) candidates, (\d+) MiB, (\d+) s', kit)
    kc = re.search(r'forms covered (\d+) of (\d+)', kit)
    ka = re.search(r'allotted ([\d.]+) s', kit)
    assert km and int(km[1]) >= 1 and km[1] == km[2] and ke and kc and ka, kit
    KIT_START = '74dd1130.search through the supervisor.py, gate-worker.sh, live_priors.pkl, steers, policy_model.pkl and code.bin of kernel-soak-%s-linux-ramp59-2400s, on the Mac: pool clauses: search, 0 Tracebacks, 0 deaths, %s of %s gold forms covered, %s candidates, allotted %s s on the share line, %s forms. The Mac has no /proc, so the peak meter is off: %s peak meter off line for %s sampler line, and the end line has %s nodes and %s MiB. kernel-soak-cover.py, kernel-soak-read.py (exit 0), kernel-soak-dag-read.py (exit 0) and kernel-soak-peak-read.py (exit 0) ran on its folder.' % (
        C, kc[1], kc[2], ke[4], ka[1], ke[2], km[1], km[2], ke[3], ke[5])
    fault_note = ''
    fault_runs = times['fault-test']
    if len(fault_runs) > 1:
        first = [r for r in fault_runs[:-1] if r[1] != 0]
        assert len(first) == len(fault_runs) - 1, fault_runs
        first_file = H + 'check-fault-test-first-try-failed.txt'
        why = re.findall(r'AssertionError: (.*)', open(first_file, errors='replace').read()) if os.path.exists(first_file) else []
        fault_note = ' The first run failed (exit %d, %d s, finished %s)%s; its output is in scratch/check-fault-test-first-try-failed.txt. This is the rerun that passed.' % (
            first[0][1], first[0][0], first[0][2], ' at ' + why[-1] if why else '')
    steps = dict(
        seeded_check=passed('seed-8f3a5a89', '8f3a5a89 with POOL_CLAUSES=search and no switch in the environment: pool clauses: search, 55 s worker, %s draws, %s forms, %s MiB at the end, %s candidate, %s right on test.' % (seed[1], seed[2], seed[5], seed[4], seed[8])),
        guard_check=passed('guard-269e22fb', '269e22fb through the real supervisor and worker, 60 s, --rss-limit-mib 2888, in a scratch copy of the code with ROOM_SHARE 0.05 and TABLE_LINE_MIB 1: %s table lines, %s of them refused, the drop:table counter (up to %d) and the memory:table refused counter (up to %d) in the log, 0 deaths, 0 kills, SIGUSR1 sent to the worker after 25 s, %s stack in the log, and an end line.' % (gt[1], gt[2], max(g_drop), max(g_refused), gt[3])),
        notebook_private_path=passed('nb-private', '00576224 on both paths, 0 Tracebacks, 0 deaths, one sampler line equal to the expected line'),
        nb_rerun=passed('nb-rerun', 'the notebook cell on the competition path with pool search, 6 tasks in the submission, 0 Tracebacks, 0 deaths, one sampler line equal to the expected line'),
        fault_test=passed('fault-test', 'the faults, then a worker that exits FULL_EXIT: no respawn, no death, slot freed, candidates in the submission, bank file kept. Shares sum to no more than the worker seconds, and a late task has a positive share. FAULT TEST PASSED.' + fault_note),
        fill_check=[
            passed('fill-135a2760', '135a2760 through the real supervisor and worker: %s fill lines, equal to refused:loo, candidates file empty, 0 deaths' % fill['135a2760'][2]),
            passed('fill-80a900e0', '80a900e0 through the real supervisor and worker: %s fill lines, equal to refused:loo, candidates file empty, 0 deaths' % fill['80a900e0'][2]),
            passed('gate-80a900e0', '80a900e0 through the real supervisor, the gate-worker.sh of the ramp kit and the reader: %s fill lines, equal to refused:loo' % gf[2])],
        gate_records_check=passed('gate-80a900e0', 'the same run, laid out as a soak folder with gate records and node records on: %s records, %s bytes in %s file. The reader found out/gate and out/record at run time, with session_mib %s, and blocks is empty' % (gr[3], gr[2], gr[1], SESSION_MIB)),
        kit_start=passed('kit-start-74dd1130', KIT_START))
    for n in REST:
        if n not in ('seed-8f3a5a89', 'guard-269e22fb', 'nb-private', 'nb-rerun', 'fault-test', 'gate-80a900e0', 'kit-start-74dd1130') and not n.startswith('fill-'):
            steps[n.replace('-', '_')] = passed(n, 'see output; the pass conditions of pass_conditions.py and the config')
else:
    why = 'Not run in this build. scratch/run-rest.sh runs it, and make-manifest.py then reads its result.'
    steps = {k: dict(result='pending', commit=C, read=why) for k in ('seeded_check', 'guard_check', 'notebook_private_path', 'nb_rerun', 'fault_test', 'gate_records_check', 'kit_start')}
    steps['fill_check'] = [dict(result='pending', commit=C, read=why) for _ in range(3)]

# the quick checks
quick = {}
for q in pass_conditions.QUICK + tuple((cfg.get('extra_quick_checks') or {})):
    key = {'code-read': 'code_read', 'code-vs-kit': 'code_vs_kit', 'kinds': 'priors_load', 'stack-kill': 'stack_kill'}.get(q, q.replace('-', '_'))
    old = last['build_steps'].get(key)
    default = 'scratch/%s output below, against the conditions of pass_conditions.py' % q
    text = (cfg.get('check_reads') or {}).get(q) or default
    quick[key] = dict(passed(q, text), output=excerpt(q))
sk = read('stack-kill')
sk_count = re.search(r'kill lines (\d+), stacks in the worker log (\d+)', sk)
sk_rss = re.search(r'kill .* RSS (\d+) MiB', sk)
quick['stack_kill']['read'] = (cfg.get('check_reads') or {}).get('stack-kill') or 'a fake worker that holds 300 MiB, through the supervisor.py of dataset/ with --rss-limit-mib 100: %s kill line (RSS %s MiB), %s stack in the worker log (most recent call first), and a submission with 1 task. Supervisor exit 0.' % (sk_count[1], sk_rss[1], sk_count[2])

old = BASE + 'dataset/'
new = B + 'dataset/'
names_ds = sorted(set(os.listdir(old)) | set(os.listdir(new)))
differ = [n for n in names_ds if not (os.path.exists(old + n) and os.path.exists(new + n) and sha(old + n) == sha(new + n))]
if 'expect_dataset_differ' in cfg:
    assert differ == sorted(cfg['expect_dataset_differ']), differ
assert sha(BASE + 'kernel/kernel-metadata.json') == sha(B + 'kernel/kernel-metadata.json')
assert sha(BASE + 'run-config-without-seconds.json') == sha(B + 'run-config-without-seconds.json')
nb_equal = sha(BASE + 'kernel/notebook.ipynb') == sha(B + 'kernel/notebook.ipynb')
if cfg.get('expect_notebook_equal', True):
    assert nb_equal

mf = cfg['manifest']
m = dict(last)
settings = dict(last['settings'], **(cfg.get('settings_add') or {}))
tok = lambda s: re.sub(r'@sha:([\w.]+)@', lambda g: src12(t, g[1]), s).replace('@C@', C).replace('@BASEC@', LASTC)  # noqa: E731
code = dict(last['code'])
for key, text in list(code.items()):
    f = key + '.py'
    if f in changed and isinstance(text, str):
        hits = list(re.finditer(r'sha256 starts [0-9a-f]{12}', text))
        code[key] = text[:hits[-1].start()] + 'sha256 starts ' + changed[f]['new'] + text[hits[-1].end():] if hits else '%s, sha256 starts %s' % (text, changed[f]['new'])
for key, text in (cfg.get('code_notes') or {}).items():
    code[key] = tok(text)
code['changed_since_%s' % LASTC] = changed
wheel_engine = dict(last['wheel_engine'], **(cfg.get('wheel_engine') or {}))
wheel_engine['wheel_sha256'] = got
if mac:
    wheel_engine['mac_wheel_sha256'] = mac
arclog_tests = tok(cfg['arclog_tests']) if cfg.get('arclog_tests') else 'not run in this build. The entry of kernel-bundle-%s reads: %s' % (LASTC, last['build_steps'].get('arclog_tests'))
wheels_seconds = tok(cfg['wheels_seconds']) if cfg.get('wheels_seconds') else ('%s' % last['build_steps'].get('wheels_seconds') if got == last['wheel_sha256'] else None)
assert wheels_seconds, 'the wheel differs from that of %s: config wheels_seconds must say how the wheels were built' % LASTC
carried = {k: 'not run in this build. The entry of kernel-bundle-%s reads: %s' % (LASTC, last['build_steps'][k]) for k in ('counters_check', 'rate_cap_check', 'reader_check', 'assembly_check') if k in last['build_steps']}
build_steps = dict(
    last['build_steps'],
    wheels_seconds=wheels_seconds,
    arclog_tests=arclog_tests,
    notebook='make_notebook.py, %s the notebook of kernel-bundle-%s' % ('equal to' if nb_equal else 'DIFFERENT FROM', LASTC),
    dataset='Against kernel-bundle-%s the files that differ in dataset/ are %s%s. Every other file in dataset/ and kernel/ is equal. dataset-metadata.json, kernel-metadata.json and run-config-without-seconds.json are copies of those of kernel-bundle-%s.' % (
        LASTC, ', '.join(differ) or 'none', ' (sha256 starts %s against %s, which is that of commit %s)' % (sha(new + 'code.bin')[:16], sha(old + 'code.bin')[:16], C) if 'code.bin' in differ else '', LASTC),
    engine_of_the_checks=dict(machine='Mac', wheel_sha256=mac, arclog_abi3_so_sha256=so, site='work/synth-kaggle/' + SITE_NAME, check='each check hashes arclog.abi3.so of the site against the one in the Mac wheel, and prints arclog.__file__ from the site. The fault test starts fake workers and imports no arclog. The stack-kill check starts a fake worker and imports no arclog.'),
    **carried, **quick, **steps)
if cfg.get('build_steps_extra'):
    build_steps.update({k: tok(v) if isinstance(v, str) else v for k, v in cfg['build_steps_extra'].items()})
m.update(
    commit=mf['commit'],
    wheel_sha256=got,
    wheel_engine=wheel_engine,
    settings=settings,
    code=code,
    linux_soak=dict(result='pending', folder='kernel-soak-%s-linux-ramp59-2400s' % C, note='The soak is the held-out difficulty ramp on the 59 tasks of its manifest, on the priors and steers of this bundle. It is the bar for the bundle.'),
    soak_kit='kernel-soak-%s-linux-ramp59-2400s' % C,
    fallback='kernel-bundle-%s' % LASTC,
    fallback_linux_soak=last['linux_soak'],
    config_file='run-config-without-seconds.json, in this folder, equal to that of kernel-bundle-%s' % LASTC,
    dataset_sha256_16={n: sha(new + n)[:16] for n in sorted(os.listdir(new))},
    build_steps=build_steps)
if mf.get('what'):
    m['what'] = mf['what']
if mf.get('notes'):
    m['notes'] = [tok(x) for x in mf['notes']]
if mf.get('reads_as'):
    m['read_rule'] = tok(mf['reads_as'])


def edit(doc, e):
    keys = e['path'].split('.')
    for k in keys[:-1]:
        doc = doc[k]
    op = e.get('op', 'set')
    if op == 'set':
        doc[keys[-1]] = tok(e['value']) if isinstance(e['value'], str) else e['value']
    elif op == 'append':
        doc[keys[-1]] = doc[keys[-1]] + [e['value']] if isinstance(doc[keys[-1]], list) else doc[keys[-1]] + ' ' + tok(e['value'])
    elif op == 'replace':
        assert e['old'] in doc[keys[-1]], (e['path'], e['old'][:60])
        doc[keys[-1]] = doc[keys[-1]].replace(e['old'], tok(e['new']))
    elif op == 'delete':
        assert keys[-1] in doc, e['path']  # a delete of a key that isn't there is a stale config
        del doc[keys[-1]]
    else:
        raise AssertionError(op)


for e in cfg.get('bundle_manifest_edits', []):
    edit(m, e)
with open(B + 'manifest.json', 'w') as f:
    json.dump(m, f, indent=1)
print('fields of the last manifest missing', set(last) - set(m), 'new', set(m) - set(last), 'build steps missing', set(last['build_steps']) - set(m['build_steps']), 'new', set(m['build_steps']) - set(last['build_steps']))
print('wheel in manifest', m['wheel_sha256'][:16], 'dataset wheel', sha(new + prm['wheel_name'])[:16])
assert m['wheel_sha256'] == sha(new + prm['wheel_name'])
print('dataset differs from', LASTC, ':', differ, '; sampler files changed:', sorted(changed))
