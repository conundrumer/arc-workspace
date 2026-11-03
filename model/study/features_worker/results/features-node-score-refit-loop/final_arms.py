"""The five final arms, as chosen on tune. Shared by features_node_final.py and features_node_read_held.py.

Every arm: all rows of N600 and the 200 S120 tasks, 150 rounds, softmax objective, a 0, fold all.
s = t * model(node) is the score of a read; the hand score (recorded, t 1) is the base.
"""
import hashlib, json, os

HERE = '/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-node-score-refit-loop/'  # the data folder
PY = '/Users/davidlu/code/arc-workspace/work/lm/data-study/ast/run/runtime-kaggle-py313/venv/bin/python'
ARMS = {
    'M-H': dict(name='mh', features='H', label='true', t=.75),
    'M-TS': dict(name='mts', features='TS', label='true', t=.5),
    'M-T': dict(name='mt', features='T', label='true', t=.5),
    'C-shuffle': dict(name='cshuf', features='H', label='shuffle', t=.75),
    'C-depth': dict(name='cdepth', features='D', label='true', t=.5),
}
ARMS.update({'R%d' % k: dict(name='r%d' % k, features='T', label='true', t=.5) for k in range(1, 100)})
for a in ARMS.values():
    a['name'] = os.environ.get('FINAL_PREFIX', '') + a['name']
    a.update(sources='n600,s120', a=0, rounds=int(os.environ.get('FINAL_ROUNDS', 150)), objective='softmax', fold='all')
# order of the held reads: the base first, then the design's order (C-hand of the design is M-H here)



def state_path(arm):
    return HERE + 'fit-out/%s-fall.state.pkl' % ARMS[arm]['name']


def card_path(arm):
    return HERE + 'final-models/%s.json' % ARMS[arm]['name']


def fit_command(arm):
    a = ARMS[arm]
    return '%s -I features_node_fit.py --features %s --sources %s --a %d --fold all --rounds %d --seconds 1500 --name %s --objective softmax --label %s' % (
        PY, a['features'], a['sources'], a['a'], a['rounds'], a['name'], a['label'])


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()

# the base first, then the rounds in order
READ_ORDER = ['hand'] + ['R%d' % k for k in range(1, 100)]
