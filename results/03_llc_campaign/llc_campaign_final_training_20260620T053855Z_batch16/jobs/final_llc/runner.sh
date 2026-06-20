#!/usr/bin/env bash
set +e
cd "/home/elvis/slt-portuguese"
export PYTHONUNBUFFERED=1
/usr/bin/timeout --signal=TERM --kill-after=60s 4.75h bash "results/03_llc_campaign/llc_campaign_final_training_20260620T053855Z_batch16/jobs/final_llc/command.sh"
rc=$?
echo $rc > "results/03_llc_campaign/llc_campaign_final_training_20260620T053855Z_batch16/jobs/final_llc/exit_code"
date -u +%FT%TZ > "results/03_llc_campaign/llc_campaign_final_training_20260620T053855Z_batch16/jobs/final_llc/end_utc"
if [[ $rc -eq 0 ]]; then echo completed > "results/03_llc_campaign/llc_campaign_final_training_20260620T053855Z_batch16/jobs/final_llc/status"; else echo failed > "results/03_llc_campaign/llc_campaign_final_training_20260620T053855Z_batch16/jobs/final_llc/status"; fi
if [[ "no" == "yes" ]]; then sudo shutdown -h now; fi
exit $rc
