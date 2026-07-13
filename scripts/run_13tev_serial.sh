#!/usr/bin/env bash
set -euo pipefail

repository_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$repository_root"
mg5_root=${MG5_ROOT:-$repository_root/MG5_aMC_v3_5_16}
output_dir=${OUTPUT_DIR:-$repository_root/artifacts/lhe/13tev}
events=${EVENTS:-100000}

if [[ "${SKIP_MODULE:-0}" != 1 ]]; then
  if [[ -r /etc/profile.d/modules.sh ]]; then
    set +u
    source /etc/profile.d/modules.sh
    set -u
  fi
  if ! type module >/dev/null 2>&1; then
    echo "Environment Modules is unavailable; set SKIP_MODULE=1 when LHAPDF is already configured." >&2
    exit 1
  fi

  module load "${HERWIG_MODULE:-herwig/stable-full-py3-rivet4}"
fi

mg5_heptools_lib=$mg5_root/HEPTools/lib
if [[ ! -f "$mg5_heptools_lib/libcollier.so" ]]; then
  echo "MadGraph Collier library not found in $mg5_heptools_lib." >&2
  exit 1
fi

if ! command -v lhapdf-config >/dev/null 2>&1; then
  echo "lhapdf-config is unavailable in PATH." >&2
  exit 1
fi
pdf_data=$(lhapdf-config --datadir)
lhapdf_lib=$(lhapdf-config --libdir)
lhapdf_python=$(lhapdf-config --pythonpath)
export LHAPDF_DATA_PATH="$pdf_data${LHAPDF_DATA_PATH:+:$LHAPDF_DATA_PATH}"
export LD_LIBRARY_PATH="$mg5_heptools_lib:$lhapdf_lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export PYTHONPATH="$lhapdf_python${PYTHONPATH:+:$PYTHONPATH}"
if [[ ! -d "$pdf_data/NNPDF40_lo_as_01180" ]]; then
  echo "NNPDF40_lo_as_01180 is not installed in $pdf_data." >&2
  exit 1
fi

execution_arguments=()
if [[ "${DRY_RUN:-0}" == 1 ]]; then
  execution_arguments+=(--dry-run)
fi

common_arguments=(
  --events "$events"
  --cores 1
  --ebeam 6500
  --ct1 1
  --pdlabel lhapdf
  --lhaid 331900
  --dynamical-scale-choice 3
  --mg5-root "$mg5_root"
  --output-dir "$output_dir"
  --resume
  "${execution_arguments[@]}"
)

if [[ "${SKIP_SMOKE:-0}" != 1 ]]; then
  python3 scripts/run_scan.py \
    --scan ct2 \
    --points scans/ct2.13tev-smoke.csv \
    --events "${SMOKE_EVENTS:-10}" \
    --cores 1 \
    --ebeam 6500 \
    --ct1 1 \
    --pdlabel lhapdf \
    --lhaid 331900 \
    --dynamical-scale-choice 3 \
    --mg5-root "$mg5_root" \
    --output-dir "$output_dir" \
    --resume \
    "${execution_arguments[@]}"
fi

python3 scripts/run_scan.py \
  --scan ct2 \
  --points scans/ct2.13tev.csv \
  "${common_arguments[@]}"

python3 scripts/run_scan.py \
  --scan ct3 \
  --points scans/ct3.13tev.csv \
  "${common_arguments[@]}"

echo "Completed all 24 production points."
