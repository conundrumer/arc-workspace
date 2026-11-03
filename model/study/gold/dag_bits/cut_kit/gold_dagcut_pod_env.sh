#!/bin/bash
# usage: gold_dagcut_pod_env.sh ARG... : runs the Mac runtime python (runtime-ba0754492) in this folder, with the models-base priors and the sampler code of orcut-fast/kit-model, as dag-kit runs. DAG_STAGES defaults to dagcut and ORCUT_KEPT_NODES to 48.
HERE=$(cd "$(dirname "$0")" && pwd)
export DAG_STAGES=${DAG_STAGES-dagcut}
HERE_CODE=$HERE exec bash "$HERE/../combined-kit/gold_combined_env.sh" "$@"
