"""Print the handbook: the solver docs and lib.dl as a solver session reads them.
dl.context renders it.
"""

from dl.context import render

if __name__ == "__main__":
    print(render(), end="")
