#!/usr/bin/env bash
set -euo pipefail

repository_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$repository_root"

mg5_root=${MG5_ROOT:-$repository_root/MG5_aMC_v3_5_16}
process_dir=${PROCESS_DIR:-$mg5_root/gg_hhh_restricted5}
output_dir=${OUTPUT_DIR:-$repository_root/artifacts/lhe/13tev}
work_dir=${WORK_DIR:-$repository_root/.work/13tev-parallel}
log_dir=${LOG_DIR:-$repository_root/logs/13tev-parallel}
ct2_points=${CT2_POINTS:-$repository_root/scans/ct2.13tev.csv}
ct3_points=${CT3_POINTS:-$repository_root/scans/ct3.13tev.csv}
events=${EVENTS:-100000}
ebeam=${EBEAM:-6500}
ct1=${CT1:-1}
seed_start=${SEED_START:-13001}
pdlabel=${PDLABEL:-lhapdf}
lhaid=${LHAID:-331900}
pdf_set=${PDF_SET:-NNPDF40_lo_as_01180}
scale_choice=${DYNAMICAL_SCALE_CHOICE:-3}

if [[ -n "${TOTAL_CORES:-}" ]]; then
  total_cores=$TOTAL_CORES
elif command -v nproc >/dev/null 2>&1; then
  total_cores=$(nproc)
else
  total_cores=$(getconf _NPROCESSORS_ONLN)
fi

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
if [[ ! -d "$pdf_data/$pdf_set" ]]; then
  echo "$pdf_set is not installed in $pdf_data." >&2
  exit 1
fi

scan_execution_arguments=()
parallel_execution_arguments=()
if [[ "${DRY_RUN:-0}" == 1 ]]; then
  scan_execution_arguments+=(--dry-run)
  parallel_execution_arguments+=(--dry-run)
fi
if [[ "${PREPARE_ONLY:-0}" == 1 ]]; then
  parallel_execution_arguments+=(--prepare-only)
fi
if [[ "${REBUILD_WORKERS:-0}" == 1 ]]; then
  parallel_execution_arguments+=(--rebuild-workers)
fi
if [[ "${ALLOW_OVERSUBSCRIPTION:-0}" == 1 ]]; then
  parallel_execution_arguments+=(--allow-oversubscription)
fi

run_mode=(--resume)
if [[ "${FORCE:-0}" == 1 ]]; then
  run_mode=(--force)
fi

if [[ "${SKIP_SMOKE:-0}" != 1 && "${PREPARE_ONLY:-0}" != 1 ]]; then
  python3 scripts/run_scan.py \
    --scan ct2 \
    --points scans/ct2.13tev-smoke.csv \
    --events "${SMOKE_EVENTS:-10}" \
    --cores 1 \
    --ebeam "$ebeam" \
    --ct1 "$ct1" \
    --pdlabel "$pdlabel" \
    --lhaid "$lhaid" \
    --dynamical-scale-choice "$scale_choice" \
    --no-systematics \
    --process-dir "$process_dir" \
    --output-dir "$output_dir" \
    "${run_mode[@]}" \
    "${scan_execution_arguments[@]}"
fi

python3 scripts/run_parallel_scan.py \
  --ct2-points "$ct2_points" \
  --ct3-points "$ct3_points" \
  --events "$events" \
  --total-cores "$total_cores" \
  --ebeam "$ebeam" \
  --ct1 "$ct1" \
  --seed-start "$seed_start" \
  --pdlabel "$pdlabel" \
  --lhaid "$lhaid" \
  --dynamical-scale-choice "$scale_choice" \
  --no-systematics \
  --process-dir "$process_dir" \
  --work-dir "$work_dir" \
  --output-dir "$output_dir" \
  --log-dir "$log_dir" \
  "${run_mode[@]}" \
  "${parallel_execution_arguments[@]}"
