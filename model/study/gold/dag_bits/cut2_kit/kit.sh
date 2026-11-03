#!/bin/bash
# kit.sh: builds the pod kit gold-v3-dagcut2-kit.tar.gz and checks it on the Mac.
#   1. prepare: lines.json (from the base tar), tasks.txt, skipped.txt, weights.json, base-rows.json (checks every base_sha and pod row code: stops on a mismatch)
#   2. the Mac's row of the check stem (check-task.txt: run mac99.sh first, which picks a stem that commits; otherwise 409aa875, which does not) -> check-expected.json
#   3. build: the tar, its sha256 and manifest.json (the refit of mac99.sh goes in the manifest if refit.json exists)
#   4. in a clean folder from the tar: `import gold_dagcut2_run` on the kit's files alone, then the runner on the check stem, compared with check-expected.json by gold_dagcut2_check.py
# ETA about 3 to 6 minutes (two runs of the check stem, a tar of about 9 MB). check.sh itself is the pod step: PY=<python> bash check.sh 16 in the kit.
# Run from any folder: bash kit.sh
cd "$(dirname "$0")"
HERE=$PWD
H=/Users/davidlu/code/arc-workspace/scripts/run_heavy.py
D=/Users/davidlu/code/arc-workspace/work/lm/data-study
PY=$D/ast/run/runtime-kaggle-py313/venv/bin/python
set -e
python3 gold_dagcut2_kit.py prepare
stem=$(cat check-task.txt)
rm -rf out-expect
mkdir out-expect
$H --cpus 1 --need soon bash gold_dagcut2_env.sh gold_dagcut2_run.py check-task.txt lines.json weights.json base-rows.json out-expect/rows-0.jsonl 0 1
python3 gold_dagcut2_kit.py expect out-expect/rows-0.jsonl
python3 gold_dagcut2_kit.py build
tmp=$(mktemp -d)
tar xzf gold-v3-dagcut2-kit.tar.gz -C "$tmp"
kit=$tmp/gold-v3-dagcut2-kit
cd "$kit"
export ARC_ROOT=$kit SAMPLER_CODE=$kit/model/study/sampler SEARCH_MODELS=$kit/models SEARCH_GOLDS=$kit/golds-stub.json ORCUT_SO_SHA256=4538e2630f39d751117a59354494a1d4035d873177c6e9abffe3927a71661371 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 ARCLOG_THREADS=1 RAYON_NUM_THREADS=1 POD_FORM_SECONDS=120
export PYTHONPATH=$kit:$kit/model/study/sampler:$D/ast/run/runtime-ba0754492/py313-path:$D/sampler/fit-torch:$D/sampler/sampler-worker/front:$D/sampler/search-worker/poolsearch
$H --cpus 1 --need soon "$PY" -c "import gold_dagcut2_run; print('import ok from the kit files alone')"
$H --cpus 1 --need soon "$PY" -u gold_dagcut2_run.py check-task.txt lines.json weights.json base-rows.json out-check.jsonl 0 1
"$PY" gold_dagcut2_check.py rows out-check.jsonl check-expected.json
echo "kit ok: $HERE/gold-v3-dagcut2-kit.tar.gz, check stem $stem"
