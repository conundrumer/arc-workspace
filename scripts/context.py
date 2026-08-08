"""Print the solver docs and lib.dl in the projection a solver session reads.

Reading this output stands in for reading `docs/wf-solver/` and
`programs/lib.dl` in full. See dl.context for what each part drops.
"""

from dl.context import appendix

if __name__ == "__main__":
    print(appendix(), end="")
