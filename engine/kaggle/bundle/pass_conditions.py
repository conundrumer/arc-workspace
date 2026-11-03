"""Pass conditions of the Mac checks of a kernel bundle, shared by bundle_steps.py (step 6), write-records.py and make-manifest.py.

A condition is a regular expression that the check's output must match. `quick` names the checks that run in step 6.
"""
import re

QUICK = ('code-read', 'code-vs-kit', 'kinds', 'stack-kill')


def conditions(name, c9, extra=None, expect_line=None, session_mib=None):
    """Regular expressions that the output of check `name` must match, for commit c9."""
    esc = re.escape
    table = {
        'code-read': [r'sampler files equal ' + esc(c9)],
        'code-vs-kit': [r'code-vs-kit passed'],
        'kinds': [esc('kind_weights equals the sum of kinds1'),
                  esc('ARC_MEMO_NO_CT None gives True ARC_SLOT_NO_RUN None gives True'),
                  esc('ARC_MEMO_NO_CT 0 gives False ARC_SLOT_NO_RUN 0 gives False'),
                  r'steers check passed'],
        'stack-kill': [r'supervisor exit 0', r'kill lines [1-9]\d*, stacks in the worker log [1-9]\d*', r'kill .* RSS \d+ MiB',
                       esc('most recent call first'), esc("submission tasks 1 ['t']")],
        'seed-8f3a5a89': [esc('pool clauses: search'), r'end: None, \d+ draws, \d+ forms, \d+ nodes, \d+ candidates, \d+ MiB, \d+ s\ncandidates \d+ right on test \d+'],
        'guard-269e22fb': [r'table lines \d+, refused table lines [1-9]\d*, stacks in the log [1-9]\d*', r'deaths lines 0, kill lines 0', esc('signal sent, exit 0'), r'(?m)^end:'],
        'nb-private': [esc('Traceback lines in the cell log 0, in worker logs 0'), esc('deaths 0 kills 0'), esc("private ['00576224.draws', '00576224.search']")],
        'nb-rerun': [esc('submission tasks 6'), esc('Traceback lines in the cell log 0, in worker logs 0')],
        'fault-test': [esc('FAULT TEST PASSED')],
        'kit-start-74dd1130': [esc('pool clauses: search'), esc('deaths 0 kills 0'), esc('worker_exits 0'), esc('reader exit 0'), esc('dag read exit 0'), esc('peak read exit 0')],
    }
    if name.startswith('fill-'):
        t = [r'refused:loo (\d+) fill lines (\d+) candidates bytes 0', esc('deaths lines 0'), esc('deaths 0 kills 0')]
    elif name == 'gate-80a900e0':
        t = [r'blocks \[\]', r'record_files [1-9]\d*', r'refused:loo (\d+) fill lines (\d+)']
        if session_mib:
            t.append('session_mib ' + str(session_mib))
    else:
        t = list(table.get(name, []))
    if expect_line and name in ('nb-private', 'nb-rerun'):
        t.append(esc(expect_line[:150]))  # nb-test cuts each line at 170 characters
    return t + list((extra or {}).get(name, []))


def failures(name, text, c9, extra=None, expect_line=None, session_mib=None):
    """The conditions of check `name` that its output `text` does not meet."""
    out = [p for p in conditions(name, c9, extra, expect_line, session_mib) if not re.search(p, text)]
    if name.startswith('fill-') or name == 'gate-80a900e0':
        m = re.search(r'refused:loo (\d+) fill lines (\d+)', text)
        if m and m[1] != m[2]:
            out.append('refused:loo equals fill lines (%s, %s)' % (m[1], m[2]))
    if name == 'nb-private' and 'Traceback' in text.replace('Traceback lines', ''):
        out.append('no Traceback line')
    if name == 'kit-start-74dd1130' and 'Traceback' in text:
        out.append('no Traceback line')
    return out
