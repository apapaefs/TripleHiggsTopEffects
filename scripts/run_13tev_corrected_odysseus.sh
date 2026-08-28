#!/usr/bin/env bash
set -euo pipefail

repository_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)

export HERWIG_MODULE=${HERWIG_MODULE:-herwig/730}
export PYTHON_BIN=${PYTHON_BIN:-python3}
export TOTAL_CORES=${TOTAL_CORES:-384}
export CORES_PER_POINT=${CORES_PER_POINT:-96}
export SHARD_COUNT=${SHARD_COUNT:-3}
export SHARD_INDICES=${SHARD_INDICES:-0,2}
export EXPECTED_POINTS=${EXPECTED_POINTS:-37}
export SEED_START=${SEED_START:-34001}

exec "$repository_root/scripts/run_13tev_corrected_tiresias.sh"
