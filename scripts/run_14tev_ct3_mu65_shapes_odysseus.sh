#!/usr/bin/env bash
set -euo pipefail

repository_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$repository_root"

export EBEAM=${EBEAM:-7000}
export POINTS=${POINTS:-$repository_root/scans/ct3.14tev-mu65-shape-replacement.csv}
export OUTPUT_DIR=${OUTPUT_DIR:-$repository_root/artifacts/lhe/14tev-ct3-mu65-shape-replacement}
export WORK_DIR=${WORK_DIR:-$repository_root/.work/14tev-ct3-mu65-shape-replacement}
export LOG_DIR=${LOG_DIR:-$repository_root/logs/14tev-ct3-mu65-shape-replacement}
export FIGURE_OUTPUT=${FIGURE_OUTPUT:-$repository_root/artifacts/figures/14tev-ct3-mu65-benchmarks}
export SM_MANIFEST=${SM_MANIFEST:-$repository_root/artifacts/lhe/14tev-ct3-rate-matched-pdf4lhc21/manifest.jsonl}
export REFERENCE_MANIFEST=${REFERENCE_MANIFEST:-$repository_root/artifacts/lhe/14tev-ct3-mu65-shapes/manifest.jsonl}
export COLLIDER_LABEL=${COLLIDER_LABEL:-HL-LHC}
export EXPECTED_POINTS=${EXPECTED_POINTS:-1}
export EVENTS=${EVENTS:-100000}
export TOTAL_CORES=${TOTAL_CORES:-96}
export CORES_PER_POINT=${CORES_PER_POINT:-96}
export SEED_START=${SEED_START:-65201}
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
  --sample "$REFERENCE_MANIFEST" 2.1 23 -2.3 \
  --sample "$manifest" 6.0 59 -0.50 \
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

if [[ "${UPDATE_DRAFT:-1}" == 1 ]]; then
  install -m 0644 \
    "$FIGURE_OUTPUT-m3h.pdf" \
    "$repository_root/HHH_YR5/14tev-ct3-mu65-benchmarks-m3h.pdf"
  install -m 0644 \
    "$FIGURE_OUTPUT-sum-pth.pdf" \
    "$repository_root/HHH_YR5/14tev-ct3-mu65-benchmarks-sum-pth.pdf"
fi

if [[ "${COMPILE_DRAFT:-1}" == 1 ]]; then
  (
    cd "$repository_root/HHH_YR5"
    latexmk -g -pdf -interaction=nonstopmode -halt-on-error \
      main_k3t_extended.tex main_k3t_extended_redline.tex
  )
fi
