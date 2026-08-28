#!/usr/bin/env bash
set -euo pipefail

repository_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$repository_root"

export EBEAM=${EBEAM:-7000}
export POINTS=${POINTS:-$repository_root/scans/ct3.14tev-mu65-shapes.csv}
export OUTPUT_DIR=${OUTPUT_DIR:-$repository_root/artifacts/lhe/14tev-ct3-mu65-shapes}
export WORK_DIR=${WORK_DIR:-$repository_root/.work/14tev-ct3-mu65-shapes}
export LOG_DIR=${LOG_DIR:-$repository_root/logs/14tev-ct3-mu65-shapes}
export FIGURE_OUTPUT=${FIGURE_OUTPUT:-$repository_root/artifacts/figures/14tev-ct3-mu65-benchmarks}
export SM_MANIFEST=${SM_MANIFEST:-$repository_root/artifacts/lhe/14tev-ct3-rate-matched-pdf4lhc21/manifest.jsonl}
export COLLIDER_LABEL=${COLLIDER_LABEL:-HL-LHC}
export EXPECTED_POINTS=${EXPECTED_POINTS:-2}
export EVENTS=${EVENTS:-100000}
export TOTAL_CORES=${TOTAL_CORES:-96}
export CORES_PER_POINT=${CORES_PER_POINT:-48}
export SEED_START=${SEED_START:-65001}
export LHAID=${LHAID:-93100}
export PDLABEL=${PDLABEL:-lhapdf}
export PDF_SET=${PDF_SET:-PDF4LHC21_40}
export DYNAMICAL_SCALE_CHOICE=${DYNAMICAL_SCALE_CHOICE:-4}
export SCALEFACT=${SCALEFACT:-0.5}
export SKIP_SMOKE=${SKIP_SMOKE:-1}
export SKIP_PLOT=1

"$repository_root/scripts/run_14tev_ct3_sm_shapes_odysseus.sh"

if [[ "${DRY_RUN:-0}" == 1 || "${PREPARE_ONLY:-0}" == 1 ]]; then
  exit 0
fi

manifest=$OUTPUT_DIR/manifest.jsonl
python3 scripts/plot_ct3_shapes.py \
  --sample "$SM_MANIFEST" 1 1 0 \
  --sample "$manifest" 2.1 23 -2.3 \
  --sample "$manifest" 2.2 0 2.2 \
  --expected-pdlabel "$PDLABEL" \
  --expected-lhaid "$LHAID" \
  --expected-dynamical-scale-choice "$DYNAMICAL_SCALE_CHOICE" \
  --expected-scalefact "$SCALEFACT" \
  --expected-beam-energy-gev "$EBEAM" \
  --m3h-range 400 1200 \
  --sum-pt-range 0 1200 \
  --separate-panels \
  --output "$FIGURE_OUTPUT" \
  --collider-label "$COLLIDER_LABEL"
