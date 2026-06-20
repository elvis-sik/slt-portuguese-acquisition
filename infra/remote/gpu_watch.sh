#!/usr/bin/env bash
set -euo pipefail
INTERVAL="${1:-10}"
while true; do
  date -u +%FT%TZ
  nvidia-smi --query-gpu=timestamp,name,utilization.gpu,memory.used,memory.total,power.draw,temperature.gpu \
    --format=csv,noheader
  sleep "$INTERVAL"
done
