"""Pins, task lists, gold loaders and the engine setup that the scripts of this record share. No engine import at module load."""
import gzip
import hashlib
import json
import os
import sys
from pathlib import Path

HERE = Path('/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-dag-conversion-heldout37')  # the data folder
ROOT = Path('/Users/davidlu/code/arc-workspace')
SCRATCH = Path('/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad')
SAMPLER_CODE = Path(os.environ.get('SAMPLER_CODE', SCRATCH / 'records/sampler-wt-d1c0f40e6/model/study/sampler'))
CODE_HASH = '13bbd6afa43e'
CODE_FILES = 'live.py', 'or_q.py', 'search.py', 'search_gold.py', 'live_try.py', 'sample2_col.py', 'sample.py'
ENGINE_PATH = ROOT / 'work/lm/data-study/ast/run/runtime-ba0754492/py313-path'
WHEEL_SO = '4538e2630f39d751117a59354494a1d4035d873177c6e9abffe3927a71661371'
DS = ROOT / 'work/lm/data-study'
WORKER = DS / 'sampler/sampler-worker'
BASE = WORKER / 'sampler-helper-forms/gold-v3-helper-forms-a036da074'
HELD_CORPUS = DS / 'gold/gold-v3-helper-forms-a036da074/corpus-view'
POOL_GOLD = DS / 'gold/gold-v3-extended-cut/view-pass1'
FIT_CORPUS = DS / 'sampler/corpus-v3mix'
RANK = DS / 'features-worker/results/features-relation-pick-rank-context-rows-heldout37'
STEER_MODELS = RANK / 'steer-models'
PRIORS_FOLD = DS / 'sampler/sampler-worker/sampler-priors-folds-8a5ffec60/fold{}/live_priors.pkl'
KINDS = ('RULE', 'DET', 'INIT')
OUT_DIR = HERE
ORDER_PARTS = {'held': 8, 'dev': 2, 'fit': 2, 'pass1': 4, 'init77': 8}  # form sets with orders, and K (item 7): 2K orders each

sys.path.insert(0, str(HERE))


def code_hash() -> str:
    h = hashlib.sha256()
    for name in CODE_FILES:
        h.update((SAMPLER_CODE / name).read_bytes())
    return h.hexdigest()[:12]


def so_hash() -> str:
    return hashlib.sha256((ENGINE_PATH / 'arclog/arclog.abi3.so').resolve().read_bytes()).hexdigest()


def check_pins():
    if code_hash() != CODE_HASH:
        sys.exit('the sampler code hash is %s, the pin is %s' % (code_hash(), CODE_HASH))
    if so_hash() != WHEEL_SO:
        sys.exit('arclog in %s is not the wheel %s' % (ENGINE_PATH, WHEEL_SO))


def setup_engine(corpus, models):
    """Checks the pins, sets the environment, and puts the engine and the sampler code on sys.path. Returns nothing: import live, live_try, or_q after."""
    check_pins()
    os.environ.update(STEER_COVER='init,branch', SAMPLER_CORPUS=str(corpus).rstrip('/') + '/', SEARCH_MODELS=str(models), RAYON_NUM_THREADS='1', OMP_NUM_THREADS='1', PYTHONDONTWRITEBYTECODE='1')
    sys.dont_write_bytecode = True
    sys.path[:0] = [str(ENGINE_PATH), str(SAMPLER_CODE)]


def held_tasks():
    return open(WORKER / 'held/tasks.txt').read().split()


def base_gold():
    """Task -> gold's lines, for the 99 tasks of points-base.json (37 held, 62 dev)."""
    return {x['task']: [l for l in x['gold_sexp'].splitlines() if l.strip()] for x in json.load(open(BASE / 'points-base.json'))}


def pass1_gold():
    """Task -> gold's lines of the pool gold (view-pass1): the text that the visits and covers of the base arms index. The held tasks."""
    got = {x['task']: [l for l in x['gold_sexp'].splitlines() if l.strip()] for x in json.load(open(POOL_GOLD / 'points-eval.json'))}
    return {t: got[t] for t in held_tasks()}


def dev_tasks():
    held = set(held_tasks())
    return [t for t in base_gold() if t not in held]


def fit_tasks():
    ex = set(open(DS / 'features-worker/arm/eval-tasks.txt').read().split()) | set(open(WORKER / 'held/leave_out.txt').read().split())
    return [t for t in sorted(os.listdir(FIT_CORPUS)) if t not in ex]


def fit_gold(tasks=None):
    """Task -> gold's lines: the first pair of each task of corpus-v3mix."""
    out = {}
    for t in tasks or fit_tasks():
        with gzip.open(FIT_CORPUS / t / 'pairs.jsonl.gz', 'rt') as f:
            out[t] = [l for l in json.loads(f.readline())['gold_sexp'].splitlines() if l.strip()]
    return out


def test_tasks():
    return sorted({r[4] for r in json.load(open(RANK / 'forms-test.json'))})


def form_key(text: str) -> str:
    import features_dag_order as D
    return 'OUT' if text.startswith('(OUT') else D.parse(text)[1]


def kind_of(text: str) -> str:
    return text.split()[0].lstrip('(')


def check_engine_loaded():
    """arclog was imported through the pinned path, and the .so it sits beside has the pinned hash."""
    import arclog
    got = Path(arclog.__file__)
    if ENGINE_PATH not in got.parents:
        sys.exit('arclog loaded from %s, not %s' % (got, ENGINE_PATH))
    if so_hash() != WHEEL_SO:
        sys.exit('arclog.abi3.so is not the pinned build')
