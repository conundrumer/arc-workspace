"""Bits of each candidate of a stem, form by form, against the form it replaces. Prints one JSON row per candidate.

  gold_cover_look.py TASK
"""
import json, os, sys
task = sys.argv[1]
src = open('gold_cover_one.py').read().split('\nt0 = time.time()\nrow = dict(task=task, candidates')[0].replace('task, lines_path, crossing_path, covers_path = sys.argv[1:5]', "task, lines_path, crossing_path, covers_path = sys.argv[1], 'lines.json', 'crossing.json', 'covers.json'")
sys.argv = ['x', task]
exec(src.replace("here = os.path.dirname(os.path.abspath(__file__))", "here = os.getcwd()"))
for c in covers:
    i = c['line']
    ls = lines[:i] + c['forms'] + lines[i + 1:]
    print(json.dumps(dict(task=task, line=i, gold_form=lines[i], gold_bits=form_bits(lines, i), forms=c['forms'], bits=[form_bits(ls, i + k) for k in range(len(c['forms']))], source=c['source'])), flush=True)
