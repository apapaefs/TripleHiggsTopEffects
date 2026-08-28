#!/usr/bin/env bash
set -euo pipefail

repository_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$repository_root"

replacement_manifest=${MANIFEST:-$repository_root/artifacts/lhe/14tev-ct3-k4zero-k3p1p9-production/manifest.jsonl}
launcher_log=${LAUNCHER_LOG:-$repository_root/logs/14tev-ct3-k4zero-k3p1p9-production-launcher.log}
original_manifest=$repository_root/artifacts/lhe/14tev-ct3-rate-matched-production/manifest.jsonl
output=${FIGURE_OUTPUT:-$repository_root/artifacts/figures/14tev-ct3-rate-matched-production}
poll_seconds=${POLL_SECONDS:-60}
timeout_seconds=${TIMEOUT_SECONDS:-43200}

if [[ ! "$poll_seconds" =~ ^[1-9][0-9]*$ ]]; then
  echo "POLL_SECONDS must be a positive integer; received $poll_seconds." >&2
  exit 2
fi
if [[ ! "$timeout_seconds" =~ ^[1-9][0-9]*$ ]]; then
  echo "TIMEOUT_SECONDS must be a positive integer; received $timeout_seconds." >&2
  exit 2
fi

deadline=$((SECONDS + timeout_seconds))
echo "Waiting for the k3=1.9, k4=0, kappa3t=0.40 replacement sample: $(date -Is)"
while true; do
  record_count=0
  if [[ -f "$replacement_manifest" ]]; then
    record_count=$(awk 'NF { count++ } END { print count + 0 }' "$replacement_manifest")
  fi
  if [[ "$record_count" -ge 1 ]] && \
     grep -q '^Completed all 1 parallel scan points\.$' "$launcher_log"; then
    break
  fi
  if grep -Eq '^error:|Traceback \(most recent call last\)' "$launcher_log"; then
    echo "Production launcher reported a failure; see $launcher_log" >&2
    exit 1
  fi
  if (( SECONDS >= deadline )); then
    echo "Timed out waiting for production after $timeout_seconds seconds." >&2
    exit 1
  fi
  sleep "$poll_seconds"
done

python3 scripts/plot_ct3_shapes.py \
  --sample artifacts/lhe/14tev-ct3-sm-shapes/manifest.jsonl 1 1 0 \
  --sample "$original_manifest" 2.10 17 -0.20 \
  --sample "$replacement_manifest" 1.9 0 0.40 \
  --output "$output" \
  --collider-label HL-LHC

echo "Production figures completed: $(date -Is)"
