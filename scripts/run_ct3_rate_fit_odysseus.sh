#!/usr/bin/env bash
set -euo pipefail

repository_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
launcher_path=$repository_root/scripts/run_ct3_rate_fit_odysseus.sh

guard_setting() {
  local key=$1
  local config=$2
  awk -v key="$key" '
    index($0, key "=") == 1 {
      print substr($0, length(key) + 2)
      found = 1
      exit
    }
    END { if (!found) exit 1 }
  ' "$config"
}

if [[ "${THERMAL_GUARD_ATTACHED:-0}" != 1 ]]; then
  thermal_guard_config=${THERMAL_GUARD_CONFIG:-/etc/ipmi-thermal-guard.conf}
  thermal_guard_timer=${THERMAL_GUARD_TIMER:-ipmi-thermal-guard.timer}
  thermal_guard_wrapper=${THERMAL_GUARD_WRAPPER:-$repository_root/scripts/thermal_guard_wrapper.sh}
  if [[ ! -r "$thermal_guard_config" ]]; then
    echo "Thermal-guard configuration is not readable: $thermal_guard_config" >&2
    exit 1
  fi
  if [[ ! -x "$thermal_guard_wrapper" ]]; then
    echo "Thermal-guard wrapper is not executable: $thermal_guard_wrapper" >&2
    exit 1
  fi
  if ! command -v systemctl >/dev/null 2>&1 || ! systemctl is-active --quiet "$thermal_guard_timer"; then
    echo "Refusing to launch without an active $thermal_guard_timer." >&2
    exit 1
  fi
  thermal_guard_controller_script=${THERMAL_GUARD_CONTROLLER_SCRIPT:-$(guard_setting THERMAL_GUARD_CONTROLLER_SCRIPT "$thermal_guard_config")}
  thermal_guard_controller_action=${THERMAL_GUARD_CONTROLLER_ACTION:-$(guard_setting THERMAL_GUARD_CONTROLLER_ACTION "$thermal_guard_config")}
  thermal_guard_campaign_user=${THERMAL_GUARD_CAMPAIGN_USER:-$(guard_setting THERMAL_GUARD_CAMPAIGN_USER "$thermal_guard_config")}
  if [[ "$(id -un)" != "$thermal_guard_campaign_user" ]]; then
    echo "Thermal guard watches user $thermal_guard_campaign_user, not $(id -un)." >&2
    exit 1
  fi
  export THERMAL_GUARD_ATTACHED=1
  export THERMAL_GUARD_WRAPPER=$thermal_guard_wrapper
  export THERMAL_GUARD_CONTROLLER_SCRIPT=$thermal_guard_controller_script
  export THERMAL_GUARD_CONTROLLER_ACTION=$thermal_guard_controller_action
  echo "Thermal guard attached with marker: $thermal_guard_controller_script $thermal_guard_controller_action"
  exec "$thermal_guard_wrapper" \
    "$thermal_guard_controller_script" "$thermal_guard_controller_action" -- \
    "$launcher_path" "$@"
fi

cd "$repository_root"

mg5_root=${MG5_ROOT:-$repository_root/MG5_aMC_v3_5_16}
process_dir=${PROCESS_DIR:-$mg5_root/gg_hhh_restricted5}
python_bin=${PYTHON_BIN:-python3}
initial_events=${EVENTS:-20000}
highstat_events=${HIGHSTAT_EVENTS:-100000}
smoke_events=${SMOKE_EVENTS:-10}
total_cores=${TOTAL_CORES:-384}
cores_per_point=${CORES_PER_POINT:-96}
pdlabel=lhapdf
lhaid=93100
pdf_set=PDF4LHC21_40
scale_choice=4
scale_factor=0.5
fit_root=${FIT_ROOT:-$repository_root/artifacts/fits/ct3-rate}
candidate_dir=$fit_root/highstat-candidates
base_output=${OUTPUT_ROOT:-$repository_root/artifacts/lhe/ct3-rate-fit}
base_work=${WORK_ROOT:-$repository_root/.work/ct3-rate-fit}
base_logs=${LOG_ROOT:-$repository_root/logs/ct3-rate-fit}
baseline_points=$repository_root/scans/ct3.rate-fit-baseline.csv
contact_points=$repository_root/scans/ct3.rate-fit-contact.csv
validation_points=$repository_root/scans/ct3.rate-fit-validation.csv
smoke_points=$repository_root/scans/ct3.rate-fit-smoke.csv

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
  echo "$python_bin is unavailable." >&2
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

pdf_data=$(lhapdf-config --datadir)
lhapdf_lib=$(lhapdf-config --libdir)
lhapdf_python=$(lhapdf-config --pythonpath)
if [[ ! -d "$pdf_data/$pdf_set" ]]; then
  echo "$pdf_set is not installed in $pdf_data." >&2
  exit 1
fi
export LHAPDF_DATA_PATH="$pdf_data${LHAPDF_DATA_PATH:+:$LHAPDF_DATA_PATH}"
export LD_LIBRARY_PATH="$mg5_root/HEPTools/lib:$lhapdf_lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export PYTHONPATH="$lhapdf_python${PYTHONPATH:+:$PYTHONPATH}"

available_cores=$(nproc)
if (( total_cores > available_cores )); then
  echo "Requested $total_cores logical CPUs, but only $available_cores are available." >&2
  exit 1
fi
if (( cores_per_point <= 0 || cores_per_point > total_cores )); then
  echo "CORES_PER_POINT must be positive and no larger than TOTAL_CORES." >&2
  exit 1
fi

parallel_options=()
if [[ "${DRY_RUN:-0}" == 1 ]]; then
  parallel_options+=(--dry-run)
fi
if [[ "${PREPARE_ONLY:-0}" == 1 ]]; then
  parallel_options+=(--prepare-only)
fi
if [[ "${REBUILD_WORKERS:-0}" == 1 ]]; then
  parallel_options+=(--rebuild-workers)
fi
run_mode=(--resume)
if [[ "${FORCE:-0}" == 1 ]]; then
  run_mode=(--force)
fi
thermal_guard_options=(
  --thermal-guard-wrapper "$THERMAL_GUARD_WRAPPER"
  --thermal-guard-controller-script "$THERMAL_GUARD_CONTROLLER_SCRIPT"
  --thermal-guard-controller-action "$THERMAL_GUARD_CONTROLLER_ACTION"
)

point_count() {
  awk -F, '$0 !~ /^[[:space:]]*#/ && $1 != "name" && NF { count++ } END { print count + 0 }' "$1"
}

run_stage() {
  local energy_tag=$1
  local ebeam=$2
  local stage=$3
  local points=$4
  local expected=$5
  local events=$6
  local seed=$7
  if [[ "$(point_count "$points")" -ne "$expected" ]]; then
    echo "Expected $expected points in $points." >&2
    exit 1
  fi
  "$python_bin" scripts/run_parallel_scan.py \
    --ct3-points "$points" \
    --events "$events" \
    --total-cores "$total_cores" \
    --cores-per-point "$cores_per_point" \
    --ebeam "$ebeam" \
    --ct1 0 \
    --seed-start "$seed" \
    --pdlabel "$pdlabel" \
    --lhaid "$lhaid" \
    --dynamical-scale-choice "$scale_choice" \
    --scalefact "$scale_factor" \
    --no-systematics \
    --process-dir "$process_dir" \
    --work-dir "$base_work/$energy_tag/$stage-${events}" \
    --output-dir "$base_output/$energy_tag/$stage-${events}" \
    --log-dir "$base_logs/$energy_tag/$stage-${events}" \
    "${run_mode[@]}" \
    "${thermal_guard_options[@]}" \
    "${parallel_options[@]}"
}

energy_tags=(13tev 13p6tev 14tev)
energy_labels=(13 13.6 14)
beam_energies=(6500 6800 7000)

for index in "${!energy_tags[@]}"; do
  run_stage "${energy_tags[$index]}" "${beam_energies[$index]}" smoke "$smoke_points" 1 "$smoke_events" "$((40901 + index * 1000))"
done
if [[ "${SMOKE_ONLY:-0}" == 1 ]]; then
  exit 0
fi

for index in "${!energy_tags[@]}"; do
  run_stage "${energy_tags[$index]}" "${beam_energies[$index]}" baseline "$baseline_points" 15 "$initial_events" "$((41001 + index * 1000))"
done

if [[ "${DRY_RUN:-0}" == 1 || "${PREPARE_ONLY:-0}" == 1 ]]; then
  for index in "${!energy_tags[@]}"; do
    run_stage "${energy_tags[$index]}" "${beam_energies[$index]}" contact "$contact_points" 20 "$initial_events" "$((41101 + index * 1000))"
    run_stage "${energy_tags[$index]}" "${beam_energies[$index]}" validation "$validation_points" 6 "$initial_events" "$((41201 + index * 1000))"
  done
  exit 0
fi

gate_arguments=()
for index in "${!energy_tags[@]}"; do
  gate_arguments+=(--manifest "${energy_labels[$index]}=$base_output/${energy_tags[$index]}/baseline-${initial_events}/manifest.jsonl")
done
"$python_bin" scripts/validate_ct3_rate_gate.py \
  "${gate_arguments[@]}" \
  --output "$fit_root/baseline-gate.json"

for index in "${!energy_tags[@]}"; do
  run_stage "${energy_tags[$index]}" "${beam_energies[$index]}" contact "$contact_points" 20 "$initial_events" "$((41101 + index * 1000))"
  run_stage "${energy_tags[$index]}" "${beam_energies[$index]}" validation "$validation_points" 6 "$initial_events" "$((41201 + index * 1000))"
done

fit_arguments=()
validation_arguments=()
for index in "${!energy_tags[@]}"; do
  fit_arguments+=(--fit-manifest "${energy_labels[$index]}=$base_output/${energy_tags[$index]}/baseline-${initial_events}/manifest.jsonl")
  fit_arguments+=(--fit-manifest "${energy_labels[$index]}=$base_output/${energy_tags[$index]}/contact-${initial_events}/manifest.jsonl")
  validation_arguments+=(--validation-manifest "${energy_labels[$index]}=$base_output/${energy_tags[$index]}/validation-${initial_events}/manifest.jsonl")
done

"$python_bin" scripts/fit_ct3_rate.py \
  "${fit_arguments[@]}" \
  "${validation_arguments[@]}" \
  --output "$fit_root/preliminary" \
  --candidate-dir "$candidate_dir" \
  --skip-acceptance

for index in "${!energy_tags[@]}"; do
  safe_energy=${energy_labels[$index]/./p}
  fit_candidates=$candidate_dir/ct3.rate-fit-${safe_energy}tev-fit-highstat.csv
  validation_candidates=$candidate_dir/ct3.rate-fit-${safe_energy}tev-validation-highstat.csv
  if [[ "$(point_count "$fit_candidates")" -gt 0 ]]; then
    candidate_count=$(point_count "$fit_candidates")
    run_stage "${energy_tags[$index]}" "${beam_energies[$index]}" fit-highstat "$fit_candidates" "$candidate_count" "$highstat_events" "$((41301 + index * 1000))"
    fit_arguments+=(--fit-manifest "${energy_labels[$index]}=$base_output/${energy_tags[$index]}/fit-highstat-${highstat_events}/manifest.jsonl")
  fi
  if [[ "$(point_count "$validation_candidates")" -gt 0 ]]; then
    candidate_count=$(point_count "$validation_candidates")
    run_stage "${energy_tags[$index]}" "${beam_energies[$index]}" validation-highstat "$validation_candidates" "$candidate_count" "$highstat_events" "$((41401 + index * 1000))"
    validation_arguments+=(--validation-manifest "${energy_labels[$index]}=$base_output/${energy_tags[$index]}/validation-highstat-${highstat_events}/manifest.jsonl")
  fi
done

"$python_bin" scripts/fit_ct3_rate.py \
  "${fit_arguments[@]}" \
  "${validation_arguments[@]}" \
  --output "$fit_root"

echo "Completed the three-energy kappa3t rate fit and validation."
