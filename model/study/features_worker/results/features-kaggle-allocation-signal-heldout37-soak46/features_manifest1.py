import json, os
p = '/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-kaggle-allocation-signal-heldout37-soak46/manifest.json'
m = json.load(open(p))
m['read_plan'] = {
    'written': 'before the first read of any observable against a target',
    'observables': {
        'nodes': 'count of nodes at the cut',
        'forms': 'count of forms at the cut',
        'proposals': 'draws or tries at the cut',
        'best_out': 'largest state gain of outfeat.out_features over nodes at the cut; a task with no scored node reads 0',
        'shape_forms': 'count of forms with a Position column whose rows give exactly the cells of the output grid on every train pair',
        'area, baseline': 'mean of height times width over train inputs and outputs, oriented so that a smaller grid scores higher',
        'covered, reference only': 'gold cover events; never in a joint score',
    },
    'direction': 'a larger observable scores as closer to a candidate; no direction is flipped after a read',
    'targets': {
        'total': "sum of `total` over gold's forms, parents context; a task with an undrawable form ranks above every other task",
        'under 25 bits': "gold's worst form under 25 bits and every form drawable",
        'lowest third, substitute': "the census has no positive task on 25 bits, so a second binary target reads gold's worst form at or under the bar that holds the lowest third of tasks with every form drawable, with undrawable tasks negative; it is a substitute for the asked bar and is labelled as such",
    },
    'joint': 'logistic regression, C 1, balanced classes, for the binary targets, and ridge, alpha 1, on the within-arm rank of total; inputs are within-arm percentile ranks of log1p of each observable, best_out plain; 5 task folds, 5 repeats, mean out-of-fold score; the bootstrap reads the out-of-fold scores',
    'pooling': 'pair comparisons and rank correlations stay inside an arm; a task with k rows gives each row weight 1/k; the bootstrap resamples tasks, 2,000 draws, percentile 95% interval',
}
m['training_eligibility'] = "No row here is training-eligible. The joint model's weights are fit on held tasks by cross-fit. Any weights for the kernel must be refit on non-held tasks."
with open(p + '.new', 'w') as f:
    json.dump(m, f, indent=1)
os.replace(p + '.new', p)
