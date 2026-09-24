"""The determination plan's joint enumeration."""

from dl.determination_plan import render_determination_plan


def plan(results):
    return render_determination_plan((results, [], set()))


