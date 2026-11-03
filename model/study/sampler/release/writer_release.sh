#!/bin/bash
# usage: writer_release.sh SITE ENGINE_COMMIT [MODEL_COMMIT]
#
# Makes a writer kit release, KITS/writer-rel-<id>, and prints its folder. The release holds:
#   model/study     sampler, policy, samples, ast/run, feat_exp and judge3 as MODEL_COMMIT (default HEAD) has them, with
#                   kit_study_paths.py as study_paths.py and kit_build_tables.py as samples/build_tables.py
#   <SITE's name>   the engine site folder SITE, built from ENGINE_COMMIT
#   models-current  the models of MODELS
#   manifest.json   the two commits and the site's name
#   SHA256SUMS      every file above; <id> is the first 12 hex digits of the sha256 of this file
# The release folder is read-only. A release with the same id that exists already is left as it is.
set -euo pipefail
REPO=$(git -C "$(dirname "$0")" rev-parse --show-toplevel)
SITE=${1:?site folder}; ENGINE_COMMIT=$(git -C "$REPO" rev-parse --verify "${2:?engine commit}^{commit}")
MODEL_COMMIT=$(git -C "$REPO" rev-parse --verify "${3:-HEAD}^{commit}")
KITS=${KITS:-$REPO/work/lm/data-study/sampler/sampler-worker/kits}
MODELS=${MODELS:-$KITS/sampler-pool-m2-writer/models-current}
[ -d "$SITE/arclog" ] || { echo "no arclog package in $SITE" >&2; exit 1; }
T=$KITS/writer-rel-staging-$$
mkdir "$T"
git -C "$REPO" archive "$MODEL_COMMIT" -- model/study/sampler model/study/policy model/study/samples model/study/ast/run model/study/feat_exp model/study/judge3 | tar -x -C "$T"
git -C "$REPO" show "$MODEL_COMMIT:model/study/sampler/release/kit_study_paths.py" > "$T/model/study/study_paths.py"
git -C "$REPO" show "$MODEL_COMMIT:model/study/sampler/release/kit_build_tables.py" > "$T/model/study/samples/build_tables.py"
rsync -a --exclude __pycache__ "${SITE%/}" "$T/"
cp -R "$MODELS" "$T/models-current"
python3 - "$T/manifest.json" "$MODEL_COMMIT" "$ENGINE_COMMIT" "$(basename "${SITE%/}")" <<'EOF'
import json, sys
path, model, engine, site = sys.argv[1:]
json.dump({'model_commit': model, 'engine_commit': engine, 'site': site}, open(path, 'w'), indent=1)
EOF
chmod -R u+w "$T"
(cd "$T" && find model "$(basename "${SITE%/}")" models-current manifest.json -type f | LC_ALL=C sort | xargs shasum -a 256 > SHA256SUMS)
ID=$(shasum -a 256 "$T/SHA256SUMS" | cut -c1-12)
NEW=$KITS/writer-rel-$ID
if [ -e "$NEW" ]; then
  chmod -R u+w "$T"; mv "$T" "$KITS/.writer-rel-dup-$$"; echo "$NEW (exists; the new copy is $KITS/.writer-rel-dup-$$)"
else
  mv "$T" "$NEW"; chmod -R a-w "$NEW"; echo "$NEW"
fi
