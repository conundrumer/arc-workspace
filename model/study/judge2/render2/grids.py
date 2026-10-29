"""Labelled vertical train references and marked native mutant grids."""

def grid_lines(grid):
    return [' '.join(map(str,row)) for row in grid]


def reference_panels(example):
    return ['Train input',*grid_lines(example['input']),'','GIVEN train output',*grid_lines(example['output'])]


def train_panels(example,grid,include_reference=True):
    expected=example['output']
    panels=[]
    if grid is None:
        panels.append(['(no defined grid)'])
    else:
        height=max(len(expected),len(grid))
        width=max(max(map(len,expected),default=0),max(map(len,grid),default=0))
        mutant=[]
        for r in range(height):
            cells=[]
            for c in range(width):
                actual=grid[r][c] if r<len(grid) and c<len(grid[r]) else None
                target=expected[r][c] if r<len(expected) and c<len(expected[r]) else None
                if actual is None and target is None:token=''
                elif actual is None:token='-*'
                else:token=str(actual)+('*' if target is None or actual!=target else '')
                cells.append(token.rjust(2))
            mutant.append(' '.join(cells).rstrip())
        panels.append(mutant)
    headers=['Mutant OUT']
    lines=reference_panels(example) if include_reference else []
    for header,panel in zip(headers,panels):
        if lines:lines.append('')
        lines.extend([header,*panel])
    return lines


def fits_inline(example,grid):
    return all(len(g)<=15 and max(map(len,g),default=0)<=15 for g in (example['input'],example['output'],grid or []))
