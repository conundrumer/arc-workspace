"""Source-bound public DET reader/header receipts for the shared projector.

No native evaluation, row acquisition, callable formatting or graph copy.
"""
import hashlib
from pathlib import Path
if __package__:
    from .common import digest
    from .reader_projection import side_readers,det_transport
else:
    from common import digest
    from reader_projection import side_readers,det_transport


def mapper_receipt():
    source=Path(__file__).with_name('reader_projection.py').resolve()
    return dict(schema='mech3-reader-mapper-source-v1',source_path=str(source),
        source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        adapter_path=str(Path(__file__).resolve()),
        adapter_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())


def side_receipt(export,raw_binding,point):
    """Union selection is the caller's policy; mappings stay one per reader."""
    readers=side_readers(export,raw_binding,point)
    return dict(schema='mech3-det-side-reader-receipt-v1',complete=True,mapper=mapper_receipt(),
        export_sha256=digest(export),raw_binding_sha256=digest(raw_binding),body_path=point,
        readers=readers,reader_inventory_complete=True)


def receipt(record,exports,bindings):
    """Approved union target transport, preserving separate per-reader views."""
    value=det_transport(record,exports,bindings)
    value['mapper']=mapper_receipt()
    return value
