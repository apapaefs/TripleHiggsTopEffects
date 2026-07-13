#!/usr/bin/env bash
set -euo pipefail

repository_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$repository_root"
mg5_root=${MG5_ROOT:-$repository_root/MG5_aMC_v3_5_16}
output_dir=${OUTPUT_DIR:-$repository_root/artifacts/lhe/13tev}

if [[ -r /etc/profile.d/modules.sh ]]; then
  set +u
  source /etc/profile.d/modules.sh
  set -u
fi
if ! type module >/dev/null 2>&1; then
  echo "Environment Modules is required to load LHAPDF." >&2
  exit 1
fi

module load herwig/stable-full-py3-rivet4

mg5_heptools_lib=$mg5_root/HEPTools/lib
if [[ ! -f "$mg5_heptools_lib/libcollier.so" ]]; then
  echo "MadGraph Collier library not found in $mg5_heptools_lib." >&2
  exit 1
fi
export LD_LIBRARY_PATH="$mg5_heptools_lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"

if ! command -v lhapdf-config >/dev/null 2>&1; then
  echo "lhapdf-config is unavailable after loading the Herwig module." >&2
  exit 1
fi
pdf_data=$(lhapdf-config --datadir)
if [[ ! -d "$pdf_data/NNPDF40_lo_as_01180" ]]; then
  echo "NNPDF40_lo_as_01180 is not installed in $pdf_data." >&2
  exit 1
fi

execution_arguments=()
if [[ "${DRY_RUN:-0}" == 1 ]]; then
  execution_arguments+=(--dry-run)
fi

common_arguments=(
  --events 10000
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
