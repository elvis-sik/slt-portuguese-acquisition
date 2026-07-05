#!/usr/bin/env bash
# Local babysitter for the 7-checkpoint LLC trajectory on the pod.
# Polls every 4 min. Plays an alert sound + exits on: (a) crash/OOM (traj proc gone before done
# with <7 results), or (b) an INVALID TRAINED checkpoint (step_00400/500/600 with llc_mean<0 or
# sampler downhill). Early checkpoints reading negative are EXPECTED (pre-convergence) -> no alarm.
# On all-7-done: plays success chime + exits.
SSH=(ssh -o IdentitiesOnly=yes -i "$HOME/.ssh/id_ed25519" -o StrictHostKeyChecking=no -o ConnectTimeout=20 root@64.247.201.58 -p 18358)
PODDIR=/slt-portuguese-acquisition
alert(){ for s in Sosumi Basso Sosumi Basso; do afplay /System/Library/Sounds/$s.aiff 2>/dev/null; done; }
chime(){ for s in Glass Glass; do afplay /System/Library/Sounds/$s.aiff 2>/dev/null; done; }
deadcount=0
for i in $(seq 1 30); do
  out=$("${SSH[@]}" "cd $PODDIR || exit 1
    n=\$(ls results/h100_traj/*.json 2>/dev/null | wc -l)
    done=\$(grep -c TRAJ_FIXED_DONE results/traj_fixed.log 2>/dev/null)
    proc=\$(pgrep -f traj_fixed.sh | wc -l)
    echo \"META n=\$n done=\$done proc=\$proc\"
    for f in results/h100_traj/llc_*.json; do [ -f \"\$f\" ] || continue
      python3 -c \"import json;d=json.load(open('\$f'));ml=d.get('chain_meanLs',[]);s='\$f'.split('/')[-1][4:-5];up=all(x>=d['L0'] for x in ml) if ml else False;print('CK %s llc=%+.5f L0=%.5f up=%s pos=%s'%(s,d['llc_mean'],d['L0'],up,d['llc_mean']>0))\"
    done" 2>/dev/null | grep -E "^META|^CK")
  ts=$(date +%H:%M:%S)
  echo "[$ts poll $i]"; echo "$out"
  meta=$(echo "$out" | grep "^META")
  n=$(echo "$meta" | sed -n 's/.*n=\([0-9]*\).*/\1/p')
  done=$(echo "$meta" | sed -n 's/.*done=\([0-9]*\).*/\1/p')
  proc=$(echo "$meta" | sed -n 's/.*proc=\([0-9]*\).*/\1/p')

  # (b) invalid TRAINED checkpoint -> alert
  bad=$(echo "$out" | grep -E "^CK 0(0400|0500|0600)" | grep -E "up=False|pos=False")
  if [ -n "$bad" ]; then echo "!!! INVALID TRAINED CHECKPOINT:"; echo "$bad"; alert; echo "ALERT_INVALID"; exit 2; fi

  # success
  if [ "${done:-0}" = "1" ] || [ "${n:-0}" = "7" ]; then echo "ALL 7 DONE"; chime; echo "TRAJ_COMPLETE"; exit 0; fi

  # (a) crash/OOM: proc gone, not done, <7 results (confirm over 2 consecutive polls)
  if [ "${proc:-0}" = "0" ] && [ "${done:-0}" != "1" ]; then
    deadcount=$((deadcount+1))
    if [ "$deadcount" -ge 2 ]; then echo "!!! TRAJ PROCESS DIED (crash/OOM) with n=$n/7"; alert; echo "ALERT_CRASH"; exit 3; fi
  else deadcount=0; fi
  sleep 240
done
echo "monitor loop ended (timeout)"; exit 9
