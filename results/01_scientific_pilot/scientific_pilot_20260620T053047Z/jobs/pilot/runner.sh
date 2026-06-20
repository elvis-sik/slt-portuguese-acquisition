#!/usr/bin/env bash
set +e
cd "/home/elvis/slt-portuguese"
export PYTHONUNBUFFERED=1
/usr/bin/timeout --signal=TERM --kill-after=60s 1.10h bash "results/01_scientific_pilot/scientific_pilot_20260620T053047Z/jobs/pilot/command.sh"
rc=$?
echo $rc > "results/01_scientific_pilot/scientific_pilot_20260620T053047Z/jobs/pilot/exit_code"
date -u +%FT%TZ > "results/01_scientific_pilot/scientific_pilot_20260620T053047Z/jobs/pilot/end_utc"
if [[ $rc -eq 0 ]]; then echo completed > "results/01_scientific_pilot/scientific_pilot_20260620T053047Z/jobs/pilot/status"; else echo failed > "results/01_scientific_pilot/scientific_pilot_20260620T053047Z/jobs/pilot/status"; fi
if [[ "no" == "yes" ]]; then sudo shutdown -h now; fi
exit $rc
