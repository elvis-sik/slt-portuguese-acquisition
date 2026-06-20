#!/usr/bin/env bash
set +e
cd "/home/elvis/slt-portuguese"
export PYTHONUNBUFFERED=1
/usr/bin/timeout --signal=TERM --kill-after=60s 2h bash "results/_jobs/infra-gate-sampler-20260620T0155Z/command.sh"
rc=$?
echo $rc > "results/_jobs/infra-gate-sampler-20260620T0155Z/exit_code"
date -u +%FT%TZ > "results/_jobs/infra-gate-sampler-20260620T0155Z/end_utc"
if [[ $rc -eq 0 ]]; then echo completed > "results/_jobs/infra-gate-sampler-20260620T0155Z/status"; else echo failed > "results/_jobs/infra-gate-sampler-20260620T0155Z/status"; fi
if [[ "no" == "yes" ]]; then sudo shutdown -h now; fi
exit $rc
