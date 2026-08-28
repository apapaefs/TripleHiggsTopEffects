#!/usr/bin/env bash
set -euo pipefail

# Keep the configured controller marker in this process's command line while
# the real command runs in the same process group. Odysseus's root thermal
# guard finds the marker and pauses/resumes the complete group.

if [[ $# -lt 4 ]]; then
  echo "usage: $0 CONTROLLER_SCRIPT CONTROLLER_ACTION -- COMMAND [ARGS...]" >&2
  exit 2
fi

controller_script=$1
controller_action=$2
separator=$3
if [[ -z "$controller_script" || -z "$controller_action" || "$separator" != -- ]]; then
  echo "ERROR: invalid thermal-guard marker or missing -- separator" >&2
  exit 2
fi
shift 3

child_pid=""
forward_signal() {
  local signal_name=$1
  if [[ -n "$child_pid" ]]; then
    kill "-$signal_name" "$child_pid" 2>/dev/null || true
  fi
}

trap 'forward_signal TERM' TERM
trap 'forward_signal INT' INT
trap 'forward_signal HUP' HUP

"$@" &
child_pid=$!

# A trapped signal can interrupt wait before the child has exited. Keep
# waiting so that the wrapper marker remains present for the child's lifetime.
while true; do
  status=0
  wait "$child_pid" || status=$?
  if ! kill -0 "$child_pid" 2>/dev/null; then
    exit "$status"
  fi
done
