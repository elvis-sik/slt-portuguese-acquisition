#!/usr/bin/env bash
set +e
cd "/home/elvis/slt-portuguese"
export PYTHONUNBUFFERED=1
/usr/bin/timeout --signal=TERM --kill-after=60s 5.50h bash "results/02_final_training/final_training_20260620T053855Z/jobs/final_behavior/command.sh"
rc=$?
echo $rc > "results/02_final_training/final_training_20260620T053855Z/jobs/final_behavior/exit_code"
date -u +%FT%TZ > "results/02_final_training/final_training_20260620T053855Z/jobs/final_behavior/end_utc"
if [[ $rc -eq 0 ]]; then echo completed > "results/02_final_training/final_training_20260620T053855Z/jobs/final_behavior/status"; else echo failed > "results/02_final_training/final_training_20260620T053855Z/jobs/final_behavior/status"; fi
if [[ "no" == "yes" ]]; then sudo shutdown -h now; fi
exit $rc
