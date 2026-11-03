"""What the read, the check and the smoke gate know about the scope rule of the joint arm: its log lines, its run counters and its picks lines.

The rule (scope/joint.py of the kit) prints one marker line when a worker process loads it:  scope rule: name=joint beta=0.5 model=<sha8>
It prints `scope rule: fallback: <error>` for its first 3 fallbacks, and counts every fallback in the run counter FALLBACK, which the worker's `counts` line and
end line print. It labels the picks lines of its openings with the score name `joint`, and those of the openings that the policy picked with `ship`.

Arms: joint and the check arm jointcheck use the rule. jointfail uses it with SCOPE_RULE_FAIL=1, so that every opening falls back. smokejoint is the smoke arm.
"""
import ast
import json
import re

NAME = 'joint'
BETA = '0.5'
FALLBACK = 'search:scope rule fallback'
PICKED = 'search:scope rule picks'
RULE_ARMS = ('joint', 'jointcheck', 'jointfail', 'smokejoint')
FAIL_ARMS = ('jointfail',)
MARKER = re.compile(r'^scope rule: name=(?P<name>\S+) beta=(?P<beta>\S+) model=(?P<model>\S+)$', re.M)
FALLBACK_LINE = re.compile(r'^scope rule: (fallback|model failed).*$', re.M)


def markers(log):
    """The distinct marker lines of a log."""
    return sorted(set(m[0] for m in MARKER.finditer(log)))


def fallback_lines(log):
    return [m[0] for m in FALLBACK_LINE.finditer(log)]


def counts(log):
    """{counter: total over the processes of the log} for the rule's two counters. The count of a process is the larger of the last `counts` line it printed and
    the counter in the dict that it prints after its `end:` line. A process starts at a line `generation `."""
    total = {FALLBACK: 0, PICKED: 0}
    segments, cur = [], None
    for line in log.split('\n'):
        if line.startswith('generation '):
            cur = dict.fromkeys(total, 0)
            segments.append(cur)
        elif cur is None:
            continue
        elif line.startswith('counts '):
            try:
                got = json.loads(line[7:])
            except ValueError:
                continue
            for k in total:
                cur[k] = max(cur[k], got.get(k, 0))
        elif line.startswith("{'") and line.endswith('}'):
            try:
                got = ast.literal_eval(line)
            except (ValueError, SyntaxError):
                continue
            for k in total:
                cur[k] = max(cur[k], got.get(k, 0))
    for s in segments:
        for k in total:
            total[k] += s[k]
    return total


def picks_by_score(picks):
    """{score name: openings with picked nodes} over the picks lines. A line with no score has the name None."""
    got = {}
    for x in picks:
        if x.get('picks'):
            got[x.get('score')] = got.get(x.get('score'), 0) + 1
    return got


def items(base, log, picks):
    """[(item, ok, text)] of a job of a rule arm: the marker, the fallback count and the labels of the picks lines.
    base is the arm name without its seed. picks: the lines of the picks file."""
    out = []
    mk = markers(log)
    out.append(('RuleMarker', len(mk) == 1 and ' name=%s beta=%s ' % (NAME, BETA) in mk[0] + ' ', mk[0] if len(mk) == 1 else '%d distinct marker lines: %s' % (len(mk), mk[:2])))
    c = counts(log)
    by = picks_by_score(picks)
    n = sum(by.values())
    if base in FAIL_ARMS:
        out.append(('RuleFallback', c[FALLBACK] > 0 and not by.get(NAME) and c[PICKED] == 0, 'fallbacks counted %d, rule picks counted %d, openings labelled %s' % (c[FALLBACK], c[PICKED], by)))
    else:
        out.append(('RuleFallback', c[FALLBACK] == 0 and not fallback_lines(log), 'fallbacks counted %d, fallback lines %d' % (c[FALLBACK], len(fallback_lines(log)))))
        out.append(('RulePicks', n > 0 and by.get(NAME, 0) == n, '%d of %d openings with picks are labelled %s (rule picks counted %d)' % (by.get(NAME, 0), n, NAME, c[PICKED])))
    return out
