#!/usr/bin/env bash
set -euo pipefail

repository_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)

export POINTS=${POINTS:-$repository_root/scans/ct3.14tev-mu75-analog-pilot.csv}
export OUTPUT_DIR=${OUTPUT_DIR:-$repository_root/artifacts/lhe/14tev-ct3-mu75-analog-pilot}
export WORK_DIR=${WORK_DIR:-$repository_root/.work/14tev-ct3-mu75-analog-pilot}
export LOG_DIR=${LOG_DIR:-$repository_root/logs/14tev-ct3-mu75-analog-pilot}
export FIGURE_OUTPUT=${FIGURE_OUTPUT:-$repository_root/artifacts/figures/14tev-ct3-mu75-analog-pilot-comparison}
export SM_MANIFEST=${SM_MANIFEST:-$repository_root/artifacts/lhe/14tev-ct3-rate-matched-pdf4lhc21/manifest.jsonl}
export REFERENCE_MANIFEST=${REFERENCE_MANIFEST:-$repository_root/artifacts/lhe/14tev-ct3-mu65-shapes/manifest.jsonl}
export REPLACEMENT_MANIFEST=${REPLACEMENT_MANIFEST:-$repository_root/artifacts/lhe/14tev-ct3-mu65-shape-replacement/manifest.jsonl}
export EXPECTED_POINTS=${EXPECTED_POINTS:-2}
export EVENTS=${EVENTS:-1000}
export TOTAL_CORES=${TOTAL_CORES:-384}
export CORES_PER_POINT=${CORES_PER_POINT:-192}
export SEED_START=${SEED_START:-65301}
export EBEAM=${EBEAM:-7000}
export PDLABEL=${PDLABEL:-lhapdf}
export LHAID=${LHAID:-93100}
export PDF_SET=${PDF_SET:-PDF4LHC21_40}
export DYNAMICAL_SCALE_CHOICE=${DYNAMICAL_SCALE_CHOICE:-4}
export SCALEFACT=${SCALEFACT:-0.5}
export SKIP_SMOKE=${SKIP_SMOKE:-1}
export SKIP_PLOT=1

"$repository_root/scripts/run_14tev_ct3_sm_shapes_odysseus.sh"

if [[ "${DRY_RUN:-0}" == 1 || "${PREPARE_ONLY:-0}" == 1 ]]; then
  exit 0
fi

python3 "$repository_root/scripts/plot_ct3_shapes.py" \
  --sample "$SM_MANIFEST" 1 1 0 \
  --sample "$REFERENCE_MANIFEST" 2.1 23 -2.3 \
  --sample "$OUTPUT_DIR/manifest.jsonl" 2.1 16 -2.3 \
  --sample "$REPLACEMENT_MANIFEST" 6.0 59 -0.50 \
  --sample "$OUTPUT_DIR/manifest.jsonl" 6.0 64 -0.50 \
  --expected-pdlabel "$PDLABEL" \
  --expected-lhaid "$LHAID" \
  --expected-dynamical-scale-choice "$DYNAMICAL_SCALE_CHOICE" \
  --expected-scalefact "$SCALEFACT" \
  --expected-beam-energy-gev "$EBEAM" \
  --m3h-range 400 1200 \
  --sum-pt-range 0 1200 \
  --separate-panels \
  --output "$FIGURE_OUTPUT" \
  --collider-label HL-LHC
