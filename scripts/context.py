"""Print the solver docs and lib.dl in the projection a solver session reads.
dl.context renders the projection.
"""

from dl.context import appendix

if __name__ == "__main__":
    print(appendix(), end="")
