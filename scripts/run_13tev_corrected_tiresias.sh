#!/usr/bin/env bash
set -euo pipefail

repository_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$repository_root"

mg5_root=${MG5_ROOT:-$repository_root/MG5_aMC_v3_5_16}
process_dir=${PROCESS_DIR:-$mg5_root/gg_hhh_restricted5}
output_dir=${OUTPUT_DIR:-$repository_root/artifacts/lhe/13tev-kappa-corrected}
work_dir=${WORK_DIR:-$repository_root/.work/13tev-kappa-corrected}
log_dir=${LOG_DIR:-$repository_root/logs/13tev-kappa-corrected}
smoke_points=${SMOKE_POINTS:-$repository_root/scans/ct2.13tev-corrected-smoke.csv}
smoke_output_dir=${SMOKE_OUTPUT_DIR:-$repository_root/artifacts/lhe/13tev-kappa-corrected-smoke}
python_bin=${PYTHON_BIN:-python3.10}

ct2_points=(
  "$repository_root/scans/ct2.13tev.csv"
  "$repository_root/scans/ct2.13tev-additional.csv"
)
ct3_points=(
  "$repository_root/scans/ct3.13tev.csv"
  "$repository_root/scans/ct3.13tev-additional.csv"
)

events=${EVENTS:-100000}
ebeam=${EBEAM:-6500}
ct1=0
total_cores=${TOTAL_CORES:-192}
cores_per_point=${CORES_PER_POINT:-96}
shard_count=${SHARD_COUNT:-3}
shard_indices_csv=${SHARD_INDICES:-1}
expected_points=${EXPECTED_POINTS:-18}
smoke_events=${SMOKE_EVENTS:-10}
smoke_cores=${SMOKE_CORES:-96}
smoke_seed=${SMOKE_SEED:-32999}
seed_start=${SEED_START:-33001}
pdlabel=${PDLABEL:-lhapdf}
lhaid=${LHAID:-331900}
pdf_set=${PDF_SET:-NNPDF40_lo_as_01180}
scale_choice=${DYNAMICAL_SCALE_CHOICE:-3}

all_point_count=$(awk -F, '
  $0 !~ /^[[:space:]]*#/ && $1 != "name" && NF { count++ }
  END { print count + 0 }
' "${ct2_points[@]}" "${ct3_points[@]}")
if [[ "$all_point_count" -ne 55 ]]; then
  echo "Expected exactly 55 corrected source points; found $all_point_count." >&2
  exit 1
fi
if [[ ! "$shard_count" =~ ^[1-9][0-9]*$ ]]; then
  echo "SHARD_COUNT must be a positive integer." >&2
  exit 1
fi
IFS=, read -r -a shard_indices <<< "$shard_indices_csv"
selected_point_count=$(awk -F, -v shard_count="$shard_count" -v indices="$shard_indices_csv" '
  BEGIN {
    split(indices, values, ",")
    for (i in values) selected[values[i]] = 1
  }
  $0 !~ /^[[:space:]]*#/ && $1 != "name" && NF {
    if (selected[point_index % shard_count]) count++
    point_index++
  }
  END { print count + 0 }
' "${ct2_points[@]}" "${ct3_points[@]}")
if [[ "$selected_point_count" -ne "$expected_points" ]]; then
  echo "Expected $expected_points selected points; found $selected_point_count." >&2
  exit 1
fi
if (( cores_per_point <= 0 || total_cores < cores_per_point )); then
  echo "CORES_PER_POINT must be positive and no larger than TOTAL_CORES." >&2
  exit 1
fi

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

"$python_bin" scripts/validate_13tev_corrected_campaign.py \
  --process-dir "$process_dir"

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
  echo "Requested $total_cores logical CPUs, but only $available_cores are available." >&2
  exit 1
fi
if (( smoke_cores > available_cores )); then
  echo "Smoke test requests $smoke_cores logical CPUs, but only $available_cores are available." >&2
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

run_mode=(--resume)
if [[ "${FORCE:-0}" == 1 ]]; then
  run_mode=(--force)
fi

if [[ "${SKIP_SMOKE:-0}" != 1 && "${PREPARE_ONLY:-0}" != 1 ]]; then
  "$python_bin" scripts/run_scan.py \
    --scan ct2 \
    --points "$smoke_points" \
    --events "$smoke_events" \
    --cores "$smoke_cores" \
    --survey-splitting "$smoke_cores" \
    --ebeam "$ebeam" \
    --ct1 "$ct1" \
    --seed-start "$smoke_seed" \
    --pdlabel "$pdlabel" \
    --lhaid "$lhaid" \
    --dynamical-scale-choice "$scale_choice" \
    --no-systematics \
    --process-dir "$process_dir" \
    --output-dir "$smoke_output_dir" \
    "${run_mode[@]}" \
    "${scan_execution_arguments[@]}"
fi
if [[ "${SMOKE_ONLY:-0}" == 1 ]]; then
  exit 0
fi

point_arguments=()
for points in "${ct2_points[@]}"; do
  point_arguments+=(--ct2-points "$points")
done
for points in "${ct3_points[@]}"; do
  point_arguments+=(--ct3-points "$points")
done
point_arguments+=(--shard-count "$shard_count")
for shard_index in "${shard_indices[@]}"; do
  point_arguments+=(--shard-index "$shard_index")
done

exec "$python_bin" scripts/run_parallel_scan.py \
  "${point_arguments[@]}" \
  --events "$events" \
  --total-cores "$total_cores" \
  --cores-per-point "$cores_per_point" \
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
