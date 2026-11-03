"""The old module name of `query_hash.py`, kept for `row_store.py`, which imports it as `DH` (`DH.arclog`, `DH.VERSION`, `DH.definition_hash`). Delete this file when `row_store.py` imports `query_hash`.
"""
from query_hash import VERSION, arclog, query_hash as definition_hash  # noqa: F401
