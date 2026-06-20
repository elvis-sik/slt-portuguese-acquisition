#!/usr/bin/env bash
set +e
cd "/home/elvis/slt-portuguese"
export PYTHONUNBUFFERED=1
/usr/bin/timeout --signal=TERM --kill-after=60s 0.22h bash "results/recipe_search/recipe_search_20260620T171838Z_lr1e-4_wiki1m/jobs/recipe_attempt/command.sh"
rc=$?
echo $rc > "results/recipe_search/recipe_search_20260620T171838Z_lr1e-4_wiki1m/jobs/recipe_attempt/exit_code"
date -u +%FT%TZ > "results/recipe_search/recipe_search_20260620T171838Z_lr1e-4_wiki1m/jobs/recipe_attempt/end_utc"
if [[ $rc -eq 0 ]]; then echo completed > "results/recipe_search/recipe_search_20260620T171838Z_lr1e-4_wiki1m/jobs/recipe_attempt/status"; else echo failed > "results/recipe_search/recipe_search_20260620T171838Z_lr1e-4_wiki1m/jobs/recipe_attempt/status"; fi
if [[ "no" == "yes" ]]; then sudo shutdown -h now; fi
exit $rc
