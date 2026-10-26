"""The replies that the resource daemon (`scripts/resource_daemon.py`) gives a call of protocol
`heavy_protocol.LEGACY_VERSION`, which `scripts/run_heavy.py` of a checkout that has not taken the
current protocol sends: the daemon starts such a call at once, as it starts a current one, and gives it
the lines that client takes as a grant, the registry in the shape its `queue` prints, and the answer
its `need` prints.

Standard library only, Python 3.9."""

from __future__ import annotations

from typing import Any, Dict, List

from heavy_core import gib_up
from heavy_protocol import DEFAULT_CPUS


def current(request: Dict[str, Any]) -> Dict[str, Any]:
    """The legacy `request` as the current protocol gives it."""
    return {**request, "cpus": request.get("cpus") or DEFAULT_CPUS}


def granted(cpus: int) -> List[Dict[str, Any]]:
    """The lines that tell a legacy call it is not cut and starts."""
    gib = 1 + cpus
    return [{"status": "accepted", "cpus": cpus, "gib": gib, "cut": False, "limit_cpus": cpus, "limit_gib": gib},
            {"status": "granted"}]


def changed(need: str) -> Dict[str, Any]:
    """The line that tells a legacy call the need was changed and its job runs."""
    return {"status": "changed", "need": need, "waiting": False}


def registry(record: Dict[str, Any]) -> Dict[str, Any]:
    """The registry `record` in the shape a legacy `queue` prints: no job waits, and each job gives
    the GiB it measures and no minutes."""
    machine = record["machine"]
    jobs = [{**job, "gib": gib_up(job["footprint_kib"]), "minutes": None}
            for job in record["jobs"]]
    return {**record, "hold": record["fault"], "waiting": [], "jobs": jobs,
            "budget": {"cpus": machine["cpus"], "reserve_cpus": 0, "outside_gib": machine["outside_gib"]}}
