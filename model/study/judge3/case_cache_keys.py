"""One exact storage-only predecessor for CURRENT private evidence gzip.

Never drops a source, setting, runtime or kept-context identity. The predecessor
substitutes only the two authenticated source SHAs below, in the adapter map
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


def predecessor_identities(identity, *, code_root, evaluator_path, digest):
    """Return [] unless the complete current declared closure authenticates.

    The caller tries the unchanged current key first. An emitted predecessor is
    a single exact alternate key, never an exemption from checking other fields.
    """
    module = (Path(code_root) / 'current_native_names.py').resolve()
    evaluator = Path(evaluator_path).resolve()
    try:
        current_sha = file_sha(str(module), signature(module))
        if current_sha != AFTER or identity['adapter'].get(str(module)) != AFTER:
            return []
        names = implementation_names(str(evaluator), signature(evaluator))
        if names is None:
            return []
        sources = {name: file_sha(str((evaluator.parent / name).resolve()),
                                signature((evaluator.parent / name).resolve()))
                   for name in names}
        if digest(sources) != identity['runtime']['implementation_sha256']:
            return []
        changed = [name for name in names if (evaluator.parent / name).resolve() == module]
        if len(changed) != 1 or sources[changed[0]] != AFTER:
            return []
    except (OSError, KeyError, TypeError, ValueError, SyntaxError):
        return []
    old_sources = dict(sources)
    old_sources[changed[0]] = BEFORE
    predecessor = deepcopy(identity)
    predecessor['adapter'][str(module)] = BEFORE
    predecessor['runtime']['implementation_sha256'] = digest(old_sources)
    return [predecessor]
