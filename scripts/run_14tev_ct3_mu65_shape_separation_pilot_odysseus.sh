#!/usr/bin/env bash
set -euo pipefail

repository_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)

export POINTS=${POINTS:-$repository_root/scans/ct3.14tev-mu65-shape-separation-pilot.csv}
export OUTPUT_DIR=${OUTPUT_DIR:-$repository_root/artifacts/lhe/14tev-ct3-mu65-shape-separation-pilot}
export WORK_DIR=${WORK_DIR:-$repository_root/.work/14tev-ct3-mu65-shape-separation-pilot}
export LOG_DIR=${LOG_DIR:-$repository_root/logs/14tev-ct3-mu65-shape-separation-pilot}
export EXPECTED_POINTS=${EXPECTED_POINTS:-8}
export EVENTS=${EVENTS:-1000}
export TOTAL_CORES=${TOTAL_CORES:-96}
export CORES_PER_POINT=${CORES_PER_POINT:-12}
export SEED_START=${SEED_START:-65101}
export EBEAM=${EBEAM:-7000}
export PDLABEL=${PDLABEL:-lhapdf}
export LHAID=${LHAID:-93100}
export PDF_SET=${PDF_SET:-PDF4LHC21_40}
export DYNAMICAL_SCALE_CHOICE=${DYNAMICAL_SCALE_CHOICE:-4}
export SCALEFACT=${SCALEFACT:-0.5}
export SKIP_SMOKE=${SKIP_SMOKE:-1}
export SKIP_PLOT=${SKIP_PLOT:-1}

exec "$repository_root/scripts/run_14tev_ct3_sm_shapes_odysseus.sh"
