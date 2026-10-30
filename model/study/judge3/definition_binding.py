"""Native-free access to the renderer's single definition/graph binding policy.

The canonical policy remains Document.definition_node. Like judgetool's shared
project_entries adapter, this adapter extracts that one function from trusted
source, so importing it never installs a pinned native reader or copies policy.
No files are written, no native API is imported, and no engine is run.
"""
import ast
from functools import lru_cache
import hashlib
from pathlib import Path
from types import SimpleNamespace

SOURCE = Path(__file__).with_name('render_pair.py')


def _require(condition, message):
    if not condition:
        raise ValueError(message)


@lru_cache(maxsize=2)
def _function(source):
    module = ast.parse(source.decode(), str(SOURCE))
    cls = next(node for node in module.body if isinstance(node, ast.ClassDef) and node.name == 'Document')
    function = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == 'definition_node')
    if function.decorator_list or [a.arg for a in function.args.args] != ['self', 'definition']:
        raise ValueError('canonical definition binding interface changed')
    namespace = {'require': _require}
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(SOURCE), 'exec'), namespace)
    return namespace['definition_node']


def definition_node(export_or_graph, definition):
    """Return the exact graph node or raise ValueError, never guess a closure.

    Accept a full native export, its definitions object, or its graph_nodes list.
    The caller binds that export to the source/program; cross-program node ids
    must not be combined. Ambiguous/unexported identities remain unavailable.
    """
    if isinstance(export_or_graph, list):
        graph = export_or_graph
    else:
        data = export_or_graph.get('definitions', export_or_graph)
        graph = data['graph_nodes']
    context = SimpleNamespace(availability={'graph_nodes': graph})
    return _function(SOURCE.read_bytes())(context, definition)


def binding_receipt():
    """Source digest can be checked against manifest.dependencies[SOURCE]."""
    source = SOURCE.read_bytes()
    return dict(schema='judge3-definition-binding-v1', source_path=str(SOURCE.resolve()),
                source_sha256=hashlib.sha256(source).hexdigest(),
                function='Document.definition_node', adapter_path=str(Path(__file__).resolve()),
                adapter_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
