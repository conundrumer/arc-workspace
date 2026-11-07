"""A LightGBM text model as compiled C: the raw score of each row, bit-equal to `Booster.predict(rows, raw_score=True)` for a model of numerical splits.

  python3 tree_compile.py MODEL...    builds each model's library in the cache, so that workers only load it

Each tree is one C function of nested branches with its thresholds and leaf values as constants, and a row's score is the sum of the trees' leaf values in tree
order, in double, as LightGBM sums them. The thresholds and leaf values are LightGBM's own, from Booster.dump_model(). A split follows LightGBM's NumericalDecision: a NaN goes to the default side where the split's missing type is NaN, and
reads as 0 otherwise; with missing type Zero, a value within KZ of 0 goes to the default side. LightGBM reads a value within KZ of 0 as 0, which matters only at a
split whose threshold lies within KZ of 0, so only those splits test it. `load` checks the library against the Booster on test rows before it is used.

The library is built once per model text, compiler and flags, in CACHE (WRITER_TREE_CACHE, default a folder in the temp directory), with the C compiler CC."""
import ctypes
import hashlib
import os
import subprocess
import sys
import tempfile

import numpy as np

CACHE = os.environ.get('WRITER_TREE_CACHE') or os.path.join(tempfile.gettempdir(), 'writer-tree-c')
CC = os.environ.get('CC', 'cc')
FLAGS = ('-O1', '-shared', '-fPIC', '-ffp-contract=off', '-fno-fast-math')
KZ = float.fromhex('0x1.a95a5cp-117')  # LightGBM's kZeroThreshold, the float 1e-35f as a double (1.0000000180025095e-35), above the double 1e-35 that zero splits use as their threshold
VERSION = '4'


class Unsupported(ValueError):
    pass


def _fields(text):
    """(header fields, [fields of each tree]) of a LightGBM model text."""
    head, trees = {}, []
    cur = head
    for line in text.splitlines():
        if line.startswith('Tree='):
            cur = {}
            trees.append(cur)
        elif line.startswith('end of trees'):
            break
        elif '=' in line:
            k, v = line.split('=', 1)
            cur[k] = v
    return head, trees


def _hex(x):
    return float(x).hex()


def _tree_c(k, root):
    """The C function of tree k, from its `tree_structure` in Booster.dump_model(): LightGBM's own values of the loaded model. Its parse of the model text can
    differ from a correctly rounded one in the last bit of a threshold, so the text's numbers are not used."""
    out = ['static double __attribute__((noinline)) t%d(const float *x) {\n' % k]  # each tree its own function: inlined into one, the compiler's passes take minutes

    def node(n, ind):
        if 'split_index' not in n:
            out.append('%sreturn %s;\n' % (ind, _hex(n['leaf_value'])))
            return
        if n['decision_type'] != '<=':
            raise Unsupported('tree %d has a categorical split' % k)
        thr, missing, default_left = float(n['threshold']), n['missing_type'], bool(n['default_left'])
        v, T = '(double)x[%d]' % n['split_feature'], _hex(thr)
        if missing == 'Zero':  # a NaN reads as 0, and a value within KZ of 0 takes the default side
            z = '(isnan(%s) || fabs(%s) <= %s)' % (v, v, _hex(KZ))
            cond = '(%s ? %d : (%s <= %s))' % (z, int(default_left), v, T)
        else:
            if abs(thr) <= KZ:  # LightGBM reads a value within KZ of 0 as 0
                v = '(fabs(%s) <= %s ? 0.0 : %s)' % (v, _hex(KZ), v)
            nan_left = default_left if missing == 'NaN' else 0.0 <= thr  # NaN: the default side; None: a NaN reads as 0
            cond = '!(%s > %s)' % (v, T) if nan_left else '(%s <= %s)' % (v, T)
        out.append('%sif (%s) {\n' % (ind, cond))
        node(n['left_child'], ind + ' ')
        out.append('%s} else {\n' % ind)
        node(n['right_child'], ind + ' ')
        out.append('%s}\n' % ind)

    node(root, ' ')
    out.append('}\n')
    return ''.join(out)


def source(model_file):
    """(C source, number of features) of the model file, from the Booster's dump."""
    lightgbm = sys.modules.get('lightgbm') or __import__('lightgbm')  # a worker has it from tree_dist.import_lightgbm already
    d = lightgbm.Booster(model_file=model_file).dump_model()
    if d.get('num_tree_per_iteration', 1) != 1 or d.get('num_class', 1) != 1:
        raise Unsupported('a model of more than one tree per iteration')
    trees = d['tree_info']
    parts = ['#include <math.h>\n'] + [_tree_c(k, t['tree_structure']) for k, t in enumerate(trees)]
    body = ''.join('  s += t%d(x);\n' % k for k in range(len(trees)))
    parts.append('void predict(const float *X, long n, long stride, double *out) {\n for (long i = 0; i < n; i++) {\n  const float *x = X + i * stride;\n'
                 '  double s = 0.0;\n%s  out[i] = s;\n }\n}\n' % body)
    return ''.join(parts), int(d['max_feature_idx']) + 1


def build(model_file):
    """The path of the model's library in CACHE, built where it is missing."""
    text = open(model_file).read()
    key = hashlib.sha256('\0'.join((VERSION, text, CC, ' '.join(FLAGS), sys.platform)).encode()).hexdigest()[:24]
    lib = os.path.join(CACHE, key + ('.dylib' if sys.platform == 'darwin' else '.so'))
    if os.path.exists(lib):
        return lib
    os.makedirs(CACHE, exist_ok=True)
    src, _ = source(model_file)
    fd, c = tempfile.mkstemp(suffix='.c', dir=CACHE)
    with os.fdopen(fd, 'w') as f:
        f.write(src)
    tmp = c[:-2] + '.part'
    try:
        subprocess.run([CC, *FLAGS, '-o', tmp, c], check=True, capture_output=True)
        os.replace(tmp, lib)
    finally:
        for p in (c, tmp):
            if os.path.exists(p):
                os.remove(p)
    return lib


class Compiled:
    """The compiled scorer of one model file."""

    def __init__(self, model_file):
        self.lib = ctypes.CDLL(build(model_file))
        self.fn = self.lib.predict
        self.fn.restype = None
        self.fn.argtypes = (ctypes.c_void_p, ctypes.c_long, ctypes.c_long, ctypes.c_void_p)
        self.num_feature = int(_fields(open(model_file).read())[0]['max_feature_idx']) + 1

    def raw(self, rows):
        """The raw score of each row of rows (n x num_feature), float64."""
        rows = np.ascontiguousarray(rows, np.float32)
        if rows.ndim != 2 or rows.shape[1] != self.num_feature:
            raise ValueError('rows of %s columns, and the model has %d features' % (rows.shape[1:], self.num_feature))
        out = np.empty(len(rows), np.float64)
        self.fn(rows.ctypes.data, len(rows), rows.shape[1], out.ctypes.data)
        return out


def test_rows(booster, n=400, seed=0):
    """Rows that probe every split: each split's threshold, the floats next to it, 0, values within KZ of 0, and NaN, mixed over the features."""
    rng = np.random.default_rng(seed)
    d = booster.dump_model()
    nf = booster.num_feature()
    cuts = [[] for _ in range(nf)]

    def walk(t):
        if 'split_feature' in t:
            th = t['threshold']
            if isinstance(th, (int, float)):
                cuts[t['split_feature']].append(float(th))
            walk(t['left_child'])
            walk(t['right_child'])
    for tr in d['tree_info']:
        walk(tr['tree_structure'])
    X = np.zeros((n, nf), np.float32)
    for j in range(nf):
        c = np.clip(np.array(cuts[j] or [0.0], np.float64), -3e38, 3e38)  # within float32's range
        pick = rng.choice(c, n)
        near = np.stack([pick, np.nextafter(pick.astype(np.float32), np.float32(np.inf)), np.nextafter(pick.astype(np.float32), np.float32(-np.inf))], 1)
        X[:, j] = near[np.arange(n), rng.integers(0, 3, n)].astype(np.float32)
        spec = rng.random(n)
        X[spec < 0.08, j] = np.nan
        X[(spec >= 0.08) & (spec < 0.14), j] = 0.0
        X[(spec >= 0.14) & (spec < 0.17), j] = np.float32(5e-36) * rng.choice([-1, 1])
    return X


def load(model_file, booster=None, rows=None):
    """The Compiled scorer of model_file, or None where it can't be built or its scores differ from the Booster's on test_rows (and on rows, where given)."""
    try:
        c = Compiled(model_file)
        if booster is not None:
            for X in [test_rows(booster)] + ([np.asarray(rows, np.float32)] if rows is not None else []):
                want = np.asarray(booster.predict(X, raw_score=True, num_threads=1), np.float64)
                got = c.raw(X)
                if not np.array_equal(want, got):
                    bad = int((want != got).sum())
                    print('compiled tree not used: %d of %d test scores differ from the Booster' % (bad, len(X)), file=sys.stderr, flush=True)
                    return None
        return c
    except Exception as e:  # noqa: BLE001 - no compiler, a categorical model, a load failure: the Booster goes on
        print('compiled tree not used: %s: %s' % (type(e).__name__, e), file=sys.stderr, flush=True)
        return None


if __name__ == '__main__':
    for m in sys.argv[1:]:
        print(m, build(m), flush=True)
