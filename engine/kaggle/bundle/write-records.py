#!/usr/bin/env python3
"""Writes the records of a kernel bundle after run-rest.sh: checks.json, kit-start-text.txt, the kit again with checks.json, and the bundle's manifest.json.

  write-records.py

It stops, naming the check, unless every check of run-rest.sh and every quick check has a last run that exited 0 and met its pass conditions. It prints the kit's .tar.gz path and sha256.
"""
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__)) + '/'
sys.path.insert(0, HERE)
import pass_conditions  # noqa: E402

prm = json.load(open(HERE + 'build-params.json'))
cfg = prm['config']
C, K = prm['c'], prm['out'].rstrip('/') + '/'
extra_quick = tuple(cfg.get('extra_quick_checks') or {})
rest = re.findall(r'run-check\.sh (\S+)', open(HERE + 'run-rest.sh').read())
times = {}
for line in open(HERE + 'times.txt'):
    m = re.match(r'(\S+) (\d+) s, exit (\d+), (\S+)', line)
    times.setdefault(m[1], []).append((int(m[2]), int(m[3]), m[4]))
m = re.search(r"^EXPECT = '([^']*)'", open(HERE + 'kit-files/kernel-soak-dag-read.py').read(), re.M)
expect = m[1] if m else None
for name in rest + list(pass_conditions.QUICK) + list(extra_quick):
    if name not in times:
        sys.exit('STOP write-records: check %s has no result in times.txt. Run %srun-rest.sh (and the quick checks of step 6) first.' % (name, HERE))
    seconds, code, finished = times[name][-1]
    text = open(HERE + 'check-%s.txt' % name, errors='replace').read()
    bad = pass_conditions.failures(name, text, C, cfg.get('pass_extra'), expect, 1877 if name == 'gate-80a900e0' else None)
    if code != 0 or bad:
        sys.exit('STOP write-records: check %s: last run exit %d, conditions not met: %s. For gate-80a900e0 with no fill line at 55 s, run it once more at 110 s.' % (name, code, bad))

kit = open(HERE + 'check-kit-start-74dd1130.txt', errors='replace').read()
seconds, code, finished = times['kit-start-74dd1130'][-1]
kit_text = ('74dd1130.search through the kit files of kernel-soak-%s-linux-ramp59-2400s on the Mac: pool clauses: search, 0 Tracebacks, 0 deaths, one peak meter off line per process (the Mac has no /proc), reader exit 0, dag read exit 0, peak read exit 0.' % C)
open(HERE + 'kit-start-text.txt', 'w').write(kit_text + '\n')
first_ok = [n for n in times if len(times[n]) == 1 and times[n][0][1] == 0]
again = {n: len(times[n]) for n in times if len(times[n]) > 1}
site = os.path.basename(prm['mac_site'].rstrip('/'))
checks = dict(
    engine="Mac, work/synth-kaggle/%s, arclog.abi3.so sha256 starts %s, the Mac build of the bundle's engine. Each run printed arclog.__file__ from that site. The Linux wheel in the kits did not run here: its hash equals the bundle's." % (site, prm['so_sha'][:16]),
    kit_start=dict(result='passed', commit=C, seconds=seconds, finished=finished, read=kit_text),
    bundle_checks='%s passed on their first run.%s' % (', '.join(sorted(first_ok)), ''.join(' %s ran %d times, and its last run passed.' % (n, k) for n, k in sorted(again.items()))),
    not_run=cfg.get('not_run', 'compare-ramp.py.'))
json.dump(checks, open(HERE + 'checks.json', 'w'), indent=2)
stamp = open(HERE + 'pass-bar-time.txt').read().strip()
r = subprocess.run(['python3', HERE + 'make-kit.py', stamp, HERE + 'checks.json'], capture_output=True, text=True, stdin=subprocess.DEVNULL)
print(r.stdout.strip().splitlines()[-1] if r.returncode == 0 else r.stdout + r.stderr)
if r.returncode != 0:
    sys.exit('STOP write-records: make-kit.py failed')
r = subprocess.run(['python3', HERE + 'make-manifest.py'], capture_output=True, text=True, stdin=subprocess.DEVNULL)
print(r.stdout.strip() if r.returncode == 0 else r.stdout + r.stderr)
if r.returncode != 0:
    sys.exit('STOP write-records: make-manifest.py failed')
print('report: %s%s' % (K, r'kernel-soak-%s-linux-ramp59-2400s.tar.gz' % C))
