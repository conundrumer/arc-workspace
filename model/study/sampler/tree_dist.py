"""A writer Distribution from a LightGBM model file.

The model scores one id at a time. Its row for an id is the feature names of `uses`, in that order: an option-scope name gives the id's own value,
and a point-scope name gives the point's value, the same for every id. Where no name of `uses` is a registered prefix feature, the names are columns of the
writing-point vector (writer.vector_names), and the row of an id is its row of Features.vectors() at those columns. The logit of an id is the model's raw score."""
import json
import os
import sys

import numpy as np

import writer


OPTIONAL = ('matplotlib', 'graphviz', 'datatable', 'dask', 'pyarrow', 'pandas')  # lightgbm's optional imports: on the Kaggle image one of them maps CUDA libraries, which fails under the worker's address space limit


def import_lightgbm():
    """lightgbm, imported with each optional package of OPTIONAL that is not imported yet blocked, so lightgbm takes its ImportError branch. Booster reads a model file and predicts on numpy arrays without them."""
    import sys
    blocked = [n for n in OPTIONAL if n not in sys.modules]
    for n in blocked:
        sys.modules[n] = None
    try:
        import lightgbm
    finally:
        for n in blocked:
            if sys.modules.get(n, 0) is None:
                del sys.modules[n]
    return lightgbm


class TreeDistribution:
    """`writer.Distribution` over a LightGBM model. `uses` must be the feature names the model was trained on, in the order of its columns."""

    def __init__(self, model_file, uses, name='tree'):
        lightgbm = import_lightgbm()
        self.booster = lightgbm.Booster(model_file=model_file)
        self.uses = tuple(uses)
        unknown = [n for n in self.uses if n not in writer.PREFIX_FEATURES]
        self.vector = len(unknown) == len(self.uses)
        self.columns = {}  # vector_names tuple -> the column of each name of uses
        if self.vector:
            unknown = []
        if unknown:
            raise ValueError('feature names that the writer does not register: %s' % unknown)
        if self.booster.num_feature() != len(self.uses):
            raise ValueError('the model has %d features, and uses has %d' % (self.booster.num_feature(), len(self.uses)))
        self.option_at = [] if self.vector else [i for i, n in enumerate(self.uses) if writer.PREFIX_FEATURES[n].scope == 'option']
        self.point_at = [] if self.vector else [i for i, n in enumerate(self.uses) if writer.PREFIX_FEATURES[n].scope == 'point']
        self.name = name
        self.version = '%s:%s' % (name, model_file)

    def rows(self, point, ids, x):
        """The model's input rows for `ids` at `point`: len(ids) x len(uses), float32."""
        if self.vector:
            return x.vectors()[:, self.vector_columns(x.names)]
        out = np.empty((len(ids), len(self.uses)), np.float32)
        out[:, self.option_at] = x.option([self.uses[i] for i in self.option_at])
        out[:, self.point_at] = x.point([self.uses[i] for i in self.point_at])
        return out

    def vector_columns(self, names):
        """The column of each name of uses in a vector with column names `names`. Raises where the vector has no column of a name."""
        got = self.columns.get(names)
        if got is None:
            at = {n: i for i, n in enumerate(names)}
            missing = [n for n in self.uses if n not in at]
            if missing:
                raise ValueError('the writing-point vector has no column of %d names of uses, first %s' % (len(missing), missing[:3]))
            got = self.columns[names] = np.array([at[n] for n in self.uses])
        return got

    def logits(self, point, ids, x):
        if len(ids) == 0:
            return np.zeros(0)
        return np.asarray(self.booster.predict(self.rows(point, ids, x), raw_score=True, num_threads=1), np.float64).reshape(len(ids))


def load(model_file, uses_file=None, name='tree'):
    """The TreeDistribution of a LightGBM text model, or None where it fails to load: lightgbm missing, a bad model file, or `uses` that do not match the model.
    The failure is printed, so a worker goes on with its hand-set distribution. uses_file holds the feature names: a JSON list, or one name per line. Its default is
    the model file with its extension replaced by '.uses.json', else by '.uses'."""
    try:
        if uses_file is None:
            base = os.path.splitext(model_file)[0]
            uses_file = next((f for f in (base + '.uses.json', base + '.uses') if os.path.exists(f)), base + '.uses')
        text = open(uses_file).read()
        uses = json.loads(text) if uses_file.endswith('.json') else [l.strip() for l in text.splitlines() if l.strip()]
        return TreeDistribution(model_file, uses, name)
    except Exception as e:
        print('tree distribution not loaded, the hand-set distribution goes on: %s: %s' % (type(e).__name__, e), file=sys.stderr, flush=True)
        return None
