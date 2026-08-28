#!/usr/bin/env bash
set -euo pipefail

repository_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
launcher_path=$repository_root/scripts/run_14tev_ct3_sm_shapes_odysseus.sh

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

  thermal_guard_controller_script=${THERMAL_GUARD_CONTROLLER_SCRIPT:-}
  thermal_guard_controller_action=${THERMAL_GUARD_CONTROLLER_ACTION:-}
  thermal_guard_campaign_user=${THERMAL_GUARD_CAMPAIGN_USER:-}
  if [[ -z "$thermal_guard_controller_script" ]]; then
    thermal_guard_controller_script=$(guard_setting THERMAL_GUARD_CONTROLLER_SCRIPT "$thermal_guard_config")
  fi
  if [[ -z "$thermal_guard_controller_action" ]]; then
    thermal_guard_controller_action=$(guard_setting THERMAL_GUARD_CONTROLLER_ACTION "$thermal_guard_config")
  fi
  if [[ -z "$thermal_guard_campaign_user" ]]; then
    thermal_guard_campaign_user=$(guard_setting THERMAL_GUARD_CAMPAIGN_USER "$thermal_guard_config")
  fi
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

export EBEAM=${EBEAM:-7000}
export POINTS=${POINTS:-$repository_root/scans/ct3.14tev-sm-shapes.csv}
export OUTPUT_DIR=${OUTPUT_DIR:-$repository_root/artifacts/lhe/14tev-ct3-sm-shapes}
export WORK_DIR=${WORK_DIR:-$repository_root/.work/14tev-ct3-sm-shapes}
export LOG_DIR=${LOG_DIR:-$repository_root/logs/14tev-ct3-sm-shapes}
export SMOKE_POINTS=${SMOKE_POINTS:-$repository_root/scans/ct3.14tev-sm-shapes-smoke.csv}
export SMOKE_OUTPUT_DIR=${SMOKE_OUTPUT_DIR:-$repository_root/artifacts/lhe/14tev-ct3-sm-shapes-smoke}
export FIGURE_OUTPUT=${FIGURE_OUTPUT:-$repository_root/artifacts/figures/14tev-ct3-sm-shapes}
export COLLIDER_LABEL=${COLLIDER_LABEL:-HL-LHC}

exec "$repository_root/scripts/run_13tev_ct3_sm_shapes_odysseus.sh"
