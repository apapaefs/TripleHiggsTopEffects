#!/usr/bin/env bash
set -euo pipefail

repository_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$repository_root"

mg5_root=${MG5_ROOT:-$repository_root/MG5_aMC_v3_5_16}
process_dir=${PROCESS_DIR:-$mg5_root/gg_hhh_restricted5}
points=${POINTS:-$repository_root/scans/ct2.13tev-rerun2.csv}
output_dir=${OUTPUT_DIR:-$repository_root/artifacts/lhe/13tev-rerun2-tiresias}
work_dir=${WORK_DIR:-$repository_root/.work/13tev-rerun2-tiresias}
log_dir=${LOG_DIR:-$repository_root/logs/13tev-rerun2-tiresias}
python_bin=${PYTHON_BIN:-python3.10}

events=${EVENTS:-100000}
ebeam=${EBEAM:-6500}
ct1=${CT1:-0}
cores_per_point=${CORES_PER_POINT:-96}
# Continue after the three-point Tiresias rerun seeds (23001--23003).
seed_start=${SEED_START:-23004}
pdlabel=${PDLABEL:-lhapdf}
lhaid=${LHAID:-331900}
pdf_set=${PDF_SET:-NNPDF40_lo_as_01180}
scale_choice=${DYNAMICAL_SCALE_CHOICE:-3}

point_count=$(awk -F, '
  $0 !~ /^[[:space:]]*#/ && $1 != "name" && NF { count++ }
  END { print count + 0 }
' "$points")
if [[ "$point_count" -ne 2 ]]; then
  echo "Expected exactly two points in $points; found $point_count." >&2
  exit 1
fi
total_cores=$((point_count * cores_per_point))

if [[ -r /etc/profile.d/modules.sh ]]; then
  set +u
  source /etc/profile.d/modules.sh
  set -u
fi
if ! type module >/dev/null 2>&1; then
  echo "Environment Modules is unavailable." >&2
  exit 1
fi
module load "${HERWIG_MODULE:-herwig/stable-full-py3-rivet4}"

if ! command -v "$python_bin" >/dev/null 2>&1; then
  echo "$python_bin is unavailable; Python 3.10 or newer is required." >&2
  exit 1
fi
if ! command -v lhapdf-config >/dev/null 2>&1; then
  echo "lhapdf-config is unavailable after loading the Herwig module." >&2
  exit 1
fi
if [[ ! -x "$process_dir/bin/generate_events" ]]; then
  echo "Generated process not found at $process_dir." >&2
  exit 1
fi

mg5_heptools_lib=$mg5_root/HEPTools/lib
if [[ ! -f "$mg5_heptools_lib/libcollier.so" ]]; then
  echo "MadGraph Collier library not found in $mg5_heptools_lib." >&2
  exit 1
fi

pdf_data=$(lhapdf-config --datadir)
lhapdf_lib=$(lhapdf-config --libdir)
lhapdf_python=$(lhapdf-config --pythonpath)
if [[ ! -d "$pdf_data/$pdf_set" ]]; then
  echo "$pdf_set is not installed in $pdf_data." >&2
  exit 1
fi
export LHAPDF_DATA_PATH="$pdf_data${LHAPDF_DATA_PATH:+:$LHAPDF_DATA_PATH}"
export LD_LIBRARY_PATH="$mg5_heptools_lib:$lhapdf_lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export PYTHONPATH="$lhapdf_python${PYTHONPATH:+:$PYTHONPATH}"

if command -v nproc >/dev/null 2>&1; then
  available_cores=$(nproc)
else
  available_cores=$(getconf _NPROCESSORS_ONLN)
fi
if (( total_cores > available_cores )); then
  echo "Need $total_cores logical CPUs for $point_count x $cores_per_point, but only $available_cores are available." >&2
  exit 1
fi

parallel_execution_arguments=()
if [[ "${DRY_RUN:-0}" == 1 ]]; then
  parallel_execution_arguments+=(--dry-run)
fi
if [[ "${PREPARE_ONLY:-0}" == 1 ]]; then
  parallel_execution_arguments+=(--prepare-only)
fi
if [[ "${REBUILD_WORKERS:-0}" == 1 ]]; then
  parallel_execution_arguments+=(--rebuild-workers)
fi

run_mode=(--resume)
if [[ "${FORCE:-0}" == 1 ]]; then
  run_mode=(--force)
fi

exec "$python_bin" scripts/run_parallel_scan.py \
  --ct2-points "$points" \
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
