# Reproduction Notes

This repository is the GitHub companion to the Google Doc submission. It contains the code, frozen
benchmark items, compact result summaries, and narrative reports. It intentionally does not contain
operator secrets, the GPU VM, heavy checkpoints, zarr sampler traces, or tokenized corpora.

_Archive note, 2026-07-05: the hackathon VMs have been removed. Treat all full-rerun commands below as
recipes for fresh GPU capacity or for an external artifact snapshot, not as commands that can resume a
live environment._

## What can be checked from Git alone

Read the current summaries:

```bash
sed -n '1,180p' PROJECT_STATUS.md
sed -n '1,180p' reports/control_comparison/REPORT.md
sed -n '1,180p' reports/seed_a_llc_trajectory/REPORT.md
```

Inspect the committed benchmark:

```bash
python3 - <<'PY'
import json
rows = [json.loads(line) for line in open("data/eval/pt_minimal_pairs.jsonl", encoding="utf-8")]
print(len(rows), "minimal pairs")
print(sorted({row["phenomenon"] for row in rows}))
PY
```

Inspect the compact figure data used by the reports:

```bash
python3 - <<'PY'
import json
for path in [
    "reports/seed_a_llc_trajectory/llc_curve.json",
    "reports/seed_a_llc_trajectory/behavioral_bpb.json",
    "reports/seed_a_llc_trajectory/grammar538.json",
    "reports/control_comparison/structured_seedA_loc100_llc.json",
    "reports/control_comparison/shuffled_pt_llc.json",
    "reports/control_comparison/matched_en_llc.json",
    "reports/control_comparison/seedA_loc300_llc.json",
]:
    data = json.load(open(path, encoding="utf-8"))
    print(path, "rows:", len(data))
PY
```

## Full reruns

Full behavioral training and LLC estimation require the operator-side GPU/checkpoint environment. The
original VMs are gone, so a rerun needs fresh GPU capacity or an external boot-disk/artifact snapshot.
The entry points are:

```bash
python3 scripts/final_training.py --config configs/final_tinystories8m_20260620.json --output-dir results/02_final_training/<run_id>
python3 scripts/build_packed_reference.py --help
python3 scripts/llc_campaign.py --help
```

Checkpoint scoring, once checkpoints exist locally:

```bash
CUDA_VISIBLE_DEVICES="" python3 scripts/score_minimal_pairs.py \
  --run-dir results/02_final_training/<run_id> \
  --condition structured_pt_seed_a \
  --benchmark data/eval/pt_minimal_pairs.jsonl \
  --output results/eval_minimal_pairs/<run_id>_structured_pt_seed_a.json
```

## Non-evidence artifacts

`reference/mock_report/` is a fabricated planning visualization. `docs/` contains historical planning and
operator notes. They are retained for transparency, but the current empirical claim is in the Google Doc,
`PROJECT_STATUS.md`, and the reports under `reports/`.

## Future work

Follow-up ideas are centralized in `FUTURE_WORK.md`, including the clean seed-B replication, formal
changepoint analysis, LLC hardening, grammar-benchmark expansion, and the exploratory low-resource
guardrail direction.
