#!/usr/bin/env bash
set -euo pipefail

repository_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$repository_root"

mg5_root=${MG5_ROOT:-$repository_root/MG5_aMC_v3_5_16}
process_dir=${PROCESS_DIR:-$mg5_root/gg_hhh_restricted5}
points=${POINTS:-$repository_root/scans/ct3.13tev-sm-shapes.csv}
output_dir=${OUTPUT_DIR:-$repository_root/artifacts/lhe/13tev-ct3-sm-shapes}
work_dir=${WORK_DIR:-$repository_root/.work/13tev-ct3-sm-shapes}
log_dir=${LOG_DIR:-$repository_root/logs/13tev-ct3-sm-shapes}
smoke_points=${SMOKE_POINTS:-$repository_root/scans/ct3.13tev-sm-shapes-smoke.csv}
smoke_output_dir=${SMOKE_OUTPUT_DIR:-$repository_root/artifacts/lhe/13tev-ct3-sm-shapes-smoke}
python_bin=${PYTHON_BIN:-python3}

events=${EVENTS:-100000}
ebeam=${EBEAM:-6500}
ct1=0
expected_points=${EXPECTED_POINTS:-12}
total_cores=${TOTAL_CORES:-384}
cores_per_point=${CORES_PER_POINT:-96}
smoke_events=${SMOKE_EVENTS:-10}
smoke_cores=${SMOKE_CORES:-96}
smoke_seed=${SMOKE_SEED:-35999}
seed_start=${SEED_START:-36001}
pdlabel=${PDLABEL:-lhapdf}
lhaid=${LHAID:-331900}
pdf_set=${PDF_SET:-NNPDF40_lo_as_01180}
scale_choice=${DYNAMICAL_SCALE_CHOICE:-3}
figure_output=${FIGURE_OUTPUT:-$repository_root/artifacts/figures/13tev-ct3-sm-shapes}
collider_label=${COLLIDER_LABEL:-13 TeV}

point_count=$(awk -F, '
  $0 !~ /^[[:space:]]*#/ && $1 != "name" && NF { count++ }
  END { print count + 0 }
' "$points")
if [[ ! "$expected_points" =~ ^[1-9][0-9]*$ ]]; then
  echo "EXPECTED_POINTS must be a positive integer; received $expected_points." >&2
  exit 1
fi
if [[ "$point_count" -ne "$expected_points" ]]; then
  echo "Expected exactly $expected_points shape points in $points; found $point_count." >&2
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
module load "${HERWIG_MODULE:-herwig/730}"

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
  echo "Requested $total_cores logical CPUs, but only $available_cores are available." >&2
  exit 1
fi
if (( smoke_cores > available_cores )); then
  echo "Smoke test requests $smoke_cores logical CPUs, but only $available_cores are available." >&2
  exit 1
fi

scan_execution_arguments=()
parallel_execution_arguments=()
thermal_guard_arguments=()
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
if [[ -n "${THERMAL_GUARD_WRAPPER:-}" ]]; then
  if [[ -z "${THERMAL_GUARD_CONTROLLER_SCRIPT:-}" || -z "${THERMAL_GUARD_CONTROLLER_ACTION:-}" ]]; then
    echo "THERMAL_GUARD_WRAPPER requires THERMAL_GUARD_CONTROLLER_SCRIPT and THERMAL_GUARD_CONTROLLER_ACTION." >&2
    exit 1
  fi
  thermal_guard_arguments+=(
    --thermal-guard-wrapper "$THERMAL_GUARD_WRAPPER"
    --thermal-guard-controller-script "$THERMAL_GUARD_CONTROLLER_SCRIPT"
    --thermal-guard-controller-action "$THERMAL_GUARD_CONTROLLER_ACTION"
  )
fi

run_mode=(--resume)
if [[ "${FORCE:-0}" == 1 ]]; then
  run_mode=(--force)
fi

if [[ "${SKIP_SMOKE:-0}" != 1 && "${PREPARE_ONLY:-0}" != 1 ]]; then
  "$python_bin" scripts/run_scan.py \
    --scan ct3 \
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

"$python_bin" scripts/run_parallel_scan.py \
  --ct3-points "$points" \
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
  "${thermal_guard_arguments[@]}" \
  "${parallel_execution_arguments[@]}"

if [[ "${DRY_RUN:-0}" != 1 && "${PREPARE_ONLY:-0}" != 1 && "${SKIP_PLOT:-0}" != 1 ]]; then
  "$python_bin" scripts/plot_ct3_shapes.py \
    --manifest "$output_dir/manifest.jsonl" \
    --ct3-values 0 0.10 0.18 \
    --output "$figure_output" \
    --collider-label "$collider_label"
fi
