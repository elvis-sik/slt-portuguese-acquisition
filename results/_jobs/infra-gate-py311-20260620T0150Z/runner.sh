#!/usr/bin/env bash
set +e
cd "/home/elvis/slt-portuguese"
export PYTHONUNBUFFERED=1
/usr/bin/timeout --signal=TERM --kill-after=60s 3h bash "results/_jobs/infra-gate-py311-20260620T0150Z/command.sh"
rc=$?
echo $rc > "results/_jobs/infra-gate-py311-20260620T0150Z/exit_code"
date -u +%FT%TZ > "results/_jobs/infra-gate-py311-20260620T0150Z/end_utc"
if [[ $rc -eq 0 ]]; then echo completed > "results/_jobs/infra-gate-py311-20260620T0150Z/status"; else echo failed > "results/_jobs/infra-gate-py311-20260620T0150Z/status"; fi
if [[ "no" == "yes" ]]; then sudo shutdown -h now; fi
exit $rc
