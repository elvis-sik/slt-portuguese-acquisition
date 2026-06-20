#!/usr/bin/env bash
set +e
cd "/home/elvis/slt-portuguese"
export PYTHONUNBUFFERED=1
/usr/bin/timeout --signal=TERM --kill-after=60s 0.12h bash "results/00_infrastructure_gate/infra_gate_20260620T044200Z/jobs/check-env/command.sh"
rc=$?
echo $rc > "results/00_infrastructure_gate/infra_gate_20260620T044200Z/jobs/check-env/exit_code"
date -u +%FT%TZ > "results/00_infrastructure_gate/infra_gate_20260620T044200Z/jobs/check-env/end_utc"
if [[ $rc -eq 0 ]]; then echo completed > "results/00_infrastructure_gate/infra_gate_20260620T044200Z/jobs/check-env/status"; else echo failed > "results/00_infrastructure_gate/infra_gate_20260620T044200Z/jobs/check-env/status"; fi
if [[ "no" == "yes" ]]; then sudo shutdown -h now; fi
exit $rc
