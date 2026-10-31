"""Exact storage-only predecessor keys for private gzip and framed JSONL.

Never drops a source, setting, runtime or kept-context identity. The predecessor
substitutes only exact authenticated storage transitions below, in the adapter map
and in the declared evaluator implementation aggregate. Cached values/receipts
are returned unchanged; no key scan, copying, migration or native replay.
"""
import ast
from copy import deepcopy
from functools import lru_cache
import hashlib
from pathlib import Path

BEFORE = '3a6dbe3d0b63890e055de0c98a05f6893aec347fcdcc2e48ecd94d2f1098f60c'
AFTER = 'cef0fc0ad6e34a83fad2dbf6f389de50a4074ca41c17b302a6c793ded54250a7'
# Source receipt: codex-adm/n-eval2-private-gzip/source.json, patch ba1c2101...
# Only CURRENT private save/read_evidence + codec receipt changed. Acquisitions,
# native schema/projection/row/kept semantics are unchanged in that exact patch.


def signature(path):
    value = path.stat()
    return (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns)


@lru_cache(maxsize=256)
def file_sha(path, file_signature):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@lru_cache(maxsize=8)
def implementation_names(path, file_signature):
    """Read the actual evaluator declaration, never maintain a parallel list."""
    tree = ast.parse(Path(path).read_text())
    expressions = [node.value for node in ast.walk(tree)
                   if isinstance(node, ast.keyword) and node.arg == 'implementation_sha256']
    if len(expressions) != 1:
        return None
    expression = expressions[0]
    if (not isinstance(expression, ast.Call) or len(expression.args) != 1
            or not isinstance(expression.args[0], ast.DictComp)):
        return None
    comprehension = expression.args[0]
    if len(comprehension.generators) != 1:
        return None
    try:
        names = ast.literal_eval(comprehension.generators[0].iter)
    except (ValueError, TypeError, SyntaxError):
        return None
    if (not isinstance(names, (tuple, list)) or len(set(names)) != len(names)
            or any(not isinstance(name, str) for name in names)):
        return None
    return tuple(names)


# Exact storage-only changes. Values are (after, before); no wildcard SHA.
# The evaluator transition additionally removes its one newly declared framed
# storage dependency when reconstructing the old implementation aggregate.
STORAGE_TRANSITIONS = [
    # Exact opt-in prepared-parent publication only; default codec bytes and
    # acquisition behavior unchanged. prefix-feature-join/performance-r2/source.json.
    ({'judge3/paused_storage.py': ('e03605ba81eff6763973e37976951f1bfd60f1109f22a5104c21d5f3ab90fa59', '166d8cf47427bc8c36e485e5a3b9a44631194c825da64ae06b664a2bb16a4b82')}, {}),
    ({'judge3/dataset_format.py': ('1870226b0a0c2e243346c12bb6bdeece6e92b1e1de91a5e02e6eb90bc2915078', 'e6fafd17402e18f917a697ece3f62c8656d78fab98a39f94a26ce35a2736df28')}, {}),

    # Prefix private report gzip + stat-invalidated source receipt cache only.
    # Exact source proof: codex-adm/n-eval2-prefix-storage/source.json.
    ({'prefix_universe.py': (
        '47c676ef0c54d77e7c2571404287404e45a95f2279615958727b6dbcad194b9f',
        'ba7b89b2d8998bf7f21e58a35a74be87c9a2c177b3da56eef69d70826073a9cd')}, {}),
    ({'current_native_names.py': (AFTER, BEFORE)}, {}),
    ({'normalized_gold.py': ('dcba33318fa9cdb772693716c426c49587dd3ef54cc1468c9fcaf3e11324b778',
                             'abd8ca57debb074156ed92275e5b0934664f8872b9658f79f910ebe31112c566')}, {}),
    ({'judgetool/evaluator.py': (
        '333da6b5898b85d2ff9013ae5d1e7e0f5df40f09614e8c9de086e2d1d38a8e81',
        '410c5b2f77bd741c7a00a92f8ecd43aa2f16ef1c4291d89521377b275c4c0588')},
     {'../judge3/framed_jsonl.py': 'b51eeb1b9123290184bd824bffa25e0f11eadc4e9f9c4027e3b13337460642f3'}),
    ({'judge3/render_pair.py': ('3fc3d896d34be1873f32c6929ddbf7d78911c88f049d0396511d74c224f2ca10', '94835d026a725be8d20bdc4d081c449665dedcba86d556b9232cbcc6cc7cbc7c')}, {}),
    ({'judge3/nonrender_metadata.py': ('82570d859bd75cffd19b919a9a4a4b9e21fbe1027fff9441d20219e5a160d5d8', '6cc7823a923bb8960a27078fa15feac9195483242f4a20e9b598258e2161b47c')}, {}),
]


def predecessor_identities(identity, *, code_root, evaluator_path, digest):
    """Enumerate only compositions of exact, authenticated storage changes.

    The full current adapter map and evaluator aggregate must first match actual
    files. Every native/runtime/settings/source/kept field remains unchanged.
    """
    root = Path(code_root).resolve(); evaluator = Path(evaluator_path).resolve()
    try:
        names = implementation_names(str(evaluator), signature(evaluator))
        if names is None:return []
        sources = {name: file_sha(str((evaluator.parent / name).resolve()),
                                signature((evaluator.parent / name).resolve())) for name in names}
        if digest(sources) != identity['runtime']['implementation_sha256']:return []
        for path, expected in identity['adapter'].items():
            actual = Path(path).resolve()
            if file_sha(str(actual), signature(actual)) != expected:return []
    except (OSError, KeyError, TypeError, ValueError, SyntaxError):return []
    pending = [(dict(identity['adapter']), sources)]; seen = {digest(identity)}; output = []
    for adapter, implementation in pending:
        for changes, added_runtime in STORAGE_TRANSITIONS:
            old_adapter = dict(adapter); old_implementation = dict(implementation); matched = False
            for relative, (after, before) in changes.items():
                path = (root / relative).resolve(); bound = []
                if str(path) in old_adapter:bound.append(('adapter', str(path)))
                bound += [('runtime', name) for name in old_implementation
                          if (evaluator.parent / name).resolve() == path]
                if not bound:break
                if any((old_adapter if kind == 'adapter' else old_implementation)[name] != after
                       for kind, name in bound):break
                for kind, name in bound:
                    (old_adapter if kind == 'adapter' else old_implementation)[name] = before
                matched = True
            else:
                if not matched or any(old_implementation.get(name) != sha
                                      for name, sha in added_runtime.items()):continue
                for name in added_runtime:
                    del old_implementation[name]
                    dependency = str((evaluator.parent / name).resolve())
                    if dependency in old_adapter:
                        if old_adapter[dependency] != added_runtime[name]:break
                        del old_adapter[dependency]
                else:
                    dependency = None
                if dependency is not None:continue
                predecessor = deepcopy(identity)
                predecessor['adapter'] = old_adapter
                predecessor['runtime']['implementation_sha256'] = digest(old_implementation)
                key = digest(predecessor)
                if key not in seen:
                    seen.add(key); output.append(predecessor); pending.append((old_adapter, old_implementation))
    return output


def prefix_predecessor_scopes(scope, *, code_root, evaluator_path, digest):
    """Return exact storage-only predecessors of a PREFIX computational scope.

    The caller excludes worker_implementation before making the computation key.
    All remaining fields are preserved, including full native/runtime/settings
    receipts. Authentication and transition composition use the case-cache engine
    above. No files, row packets or stored receipts are copied or rewritten.
    """
    root = Path(code_root).resolve()
    try:
        code = scope['code']
        if not isinstance(code, dict):return []
        paths = {}
        for name in code:
            relative = Path(name)
            if relative.is_absolute() or '..' in relative.parts:return []
            path = (root / relative).resolve()
            if not path.is_relative_to(root) or str(path) in paths:return []
            paths[str(path)] = name
        identity = dict(adapter={path: code[name] for path, name in paths.items()},
                        runtime=deepcopy(scope['runtime_receipt']))
        predecessors = predecessor_identities(identity, code_root=root,
                                               evaluator_path=evaluator_path, digest=digest)
    except (KeyError, TypeError, ValueError):return []
    output = []
    for predecessor in predecessors:
        previous = deepcopy(scope)
        previous['code'] = {paths[path]: sha for path, sha in predecessor['adapter'].items()}
        previous['runtime_receipt'] = predecessor['runtime']
        changes = {name: {'current': code.get(name), 'predecessor': previous['code'].get(name)}
                   for name in sorted(set(code) | set(previous['code']))
                   if code.get(name) != previous['code'].get(name)}
        proof = dict(schema='prefix-storage-predecessor-v1',
                     current_scope_sha256=digest(scope), predecessor_scope_sha256=digest(previous),
                     code_substitutions=changes,
                     current_implementation_sha256=scope['runtime_receipt']['implementation_sha256'],
                     predecessor_implementation_sha256=previous['runtime_receipt']['implementation_sha256'],
                     algorithm_sha256=file_sha(str(Path(__file__).resolve()), signature(Path(__file__).resolve())))
        output.append(dict(scope=previous, proof=proof))
    return output
