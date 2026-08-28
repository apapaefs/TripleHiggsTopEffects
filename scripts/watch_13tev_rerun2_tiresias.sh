#!/usr/bin/env bash
set -euo pipefail

host=${TIRESIAS_HOST:-tiresias.servebeer.com}
remote_dir=${REMOTE_DIR:-/home/apapaefs/Projects/TripleHiggsTopEffects/artifacts/lhe/13tev-rerun2-tiresias}
local_dir=${LOCAL_DIR:-$HOME/OneDrive - Kennesaw State University/13tev-additional}
poll_interval=${POLL_INTERVAL:-300}
expected_events=${EXPECTED_EVENTS:-100000}

manifest=$local_dir/manifest.jsonl
source_manifest=$local_dir/manifest.tiresias-rerun2.jsonl
ssh_options=(
  -o BatchMode=yes
  -o ConnectTimeout=20
  -o ServerAliveInterval=15
  -o ServerAliveCountMax=2
)
points=(
  "ct2_k3_m5_k4_m50_reference"
  "ct2_k3_p1_k4_p1_ct2_p4"
)

timestamp() {
  date '+%Y-%m-%d %H:%M:%S %Z'
}

log() {
  printf '[%s] %s\n' "$(timestamp)" "$*"
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    log "Required command is unavailable: $1"
    exit 1
  fi
}

manifest_row() {
  local run_name=$1
  ssh "${ssh_options[@]}" "$host" \
    "if test -f '$remote_dir/manifest.jsonl'; then grep -F '\"run_name\": \"$run_name\"' '$remote_dir/manifest.jsonl' | tail -n 1; fi"
}

record_manifest_row() {
  local run_name=$1
  local row=$2
  local target

  for target in "$manifest" "$source_manifest"; do
    if [[ ! -f "$target" ]] || ! grep -Fq "\"run_name\": \"$run_name\"" "$target"; then
      printf '%s\n' "$row" >> "$target"
    fi
  done
}

transfer_point() {
  local run_name=$1
  local row=$2
  local filename=${run_name}.unweighted_events.lhe.gz
  local remote_file=$remote_dir/$filename
  local local_file=$local_dir/$filename
  local temporary=${local_file}.partial.$$
  local expected_sha actual_sha actual_events

  if [[ "$row" != *'"status": "generated"'* ||
        "$row" != *"\"generated_events\": $expected_events"* ||
        "$row" != *"\"requested_events\": $expected_events"* ]]; then
    log "$run_name has a manifest entry, but it is not a completed $expected_events-event sample yet."
    return 1
  fi

  expected_sha=${row#*\"lhe_sha256\": \"}
  expected_sha=${expected_sha%%\"*}
  if [[ ! "$expected_sha" =~ ^[[:xdigit:]]{64}$ ]]; then
    log "$run_name has no valid SHA-256 in its manifest entry."
    return 1
  fi

  if [[ -f "$local_file" ]]; then
    actual_sha=$(shasum -a 256 "$local_file" | awk '{print $1}')
    if [[ "$actual_sha" == "$expected_sha" ]]; then
      record_manifest_row "$run_name" "$row"
      log "$filename is already present with the expected checksum."
      return 0
    fi
    log "Refusing to overwrite $local_file because its checksum does not match Tiresias."
    return 1
  fi

  rm -f "$temporary"
  log "Copying $filename from $host."
  if ! scp "${ssh_options[@]}" "$host:$remote_file" "$temporary"; then
    rm -f "$temporary"
    log "Transfer failed; it will be retried."
    return 1
  fi

  if ! gzip -t "$temporary"; then
    rm -f "$temporary"
    log "The transferred gzip file is invalid; it will be retried."
    return 1
  fi
  actual_sha=$(shasum -a 256 "$temporary" | awk '{print $1}')
  if [[ "$actual_sha" != "$expected_sha" ]]; then
    rm -f "$temporary"
    log "Checksum mismatch for $filename; it will be retried."
    return 1
  fi
  actual_events=$(gzip -dc "$temporary" | grep -c '<event>')
  if [[ "$actual_events" -ne "$expected_events" ]]; then
    rm -f "$temporary"
    log "$filename contains $actual_events events, not $expected_events; it will be retried."
    return 1
  fi

  mv "$temporary" "$local_file"
  record_manifest_row "$run_name" "$row"
  log "Published $filename ($actual_events events, SHA-256 $actual_sha)."
}

for command in ssh scp shasum gzip grep awk; do
  require_command "$command"
done
if [[ ! "$poll_interval" =~ ^[1-9][0-9]*$ ]]; then
  log "POLL_INTERVAL must be a positive number of seconds."
  exit 1
fi
mkdir -p "$local_dir"

log "Watching $host:$remote_dir for ${#points[@]} completed samples."
while true; do
  remaining=0
  for run_name in "${points[@]}"; do
    row=''
    if ! row=$(manifest_row "$run_name"); then
      log "Could not query Tiresias for $run_name; it will be retried."
      remaining=$((remaining + 1))
      continue
    fi
    if [[ -z "$row" ]]; then
      remaining=$((remaining + 1))
      continue
    fi
    if ! transfer_point "$run_name" "$row"; then
      remaining=$((remaining + 1))
    fi
  done

  if [[ "$remaining" -eq 0 ]]; then
    log "Both remaining Tiresias samples are present and validated locally."
    exit 0
  fi
  log "$remaining sample(s) remain; checking again in $poll_interval seconds."
  sleep "$poll_interval"
done
