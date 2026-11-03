"""Whether plain false hits have gold that reads D4 values by hand: a check on the plain label, after the read. Used by no form.

A gold file counts where its text, comments left out, has a D4 relation (d4_ or c4_ in a relation name, or a :D4 column).

  features_label_noise.py ROWS...
"""
import json
import os
import re
import sys

R = '/Users/davidlu/code/arc-workspace/'
GEN = R + 'work/lm/data-study/gold/gen-v3-11f6a212c/corpus/gen/'
rows = []
for p in sys.argv[1:]:
    rows += [json.loads(x) for x in open(p)]
pat = re.compile(r'd4_|c4_|:D4\b')


def reads_d4(t):
    s = re.sub(r';[^\n]*', '', open(GEN + t + '.arclog').read())
    return pat.search(s) is not None


plain = [r for r in rows if r['group'] == 'plain' and not r['whole'][0] + r['whole'][1]]
flag = {r['task']: reads_d4(r['task']) for r in plain}
all_rate = sum(flag.values()) / len(flag)
print('plain', len(plain), 'reads D4', sum(flag.values()), round(all_rate, 3))
for f in ('base', 'task-several', 'other', 'win'):
    hit = [r['task'] for r in plain if r['forms'][f][0]]
    d = [t for t in hit if flag[t]]
    print(f, 'hits', len(hit), 'read D4', len(d), round(len(d) / len(hit), 3), d[:10])
