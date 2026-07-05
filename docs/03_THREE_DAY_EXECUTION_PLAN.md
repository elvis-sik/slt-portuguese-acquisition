# Three-day execution plan

> Status, 2026-06-21: historical execution plan. The project has run; current outputs are summarized in
> `PROJECT_STATUS.md` and the reports under `reports/`.

The schedule is organized around scientific gates rather than calendar optimism. Stop adding scope when a gate is not secure.

## Phase 0: infrastructure gate

Target: complete within roughly 1–2 hours of operator/agent time.

1. Provision one on-demand GCP L4 VM.
2. Verify `nvidia-smi`, CUDA-enabled PyTorch, package imports, disk space, and network/cache access.
3. Load TinyStories-3M.
4. Run 100 training steps, save checkpoint, reload, compare loss.
5. Run a 200-step sampler smoke test and generate one trace.
6. Benchmark 50 warm-up plus 200 measured training steps at sequence lengths 64 and 128.
7. Benchmark two short sampler chains with intended observables.
8. Recalculate project time and cost.

Gate:

- end-to-end loop works;
- peak VRAM leaves at least 25% headroom;
- no architecture/API incompatibility;
- revised median total charged runtime ≤10 hours;
- pre-contingency planned cost ≤$35.

If the GPT-Neo architecture is incompatible with current `devinterp`, switch immediately to a similarly small Hugging Face-compatible GPT-NeoX/Pythia-style model or a minimal causal transformer. Do not spend half the hackathon on compatibility debugging.

## Phase 1: scientific pilot

Target: 3–5 hours of work, usually less than two charged GPU-hours.

Use TinyStories-3M and 0.5–1 million target tokens.

1. Build a small frozen parallel-data slice and evaluation splits.
2. Run three short learning-rate trials on structured Portuguese.
3. Run one structured and one shuffled trajectory.
4. Validate Portuguese BPB, lexical probe, grammar margin, and English retention.
5. Test the best two or three sampler configurations at early, middle, and late checkpoints.
6. Inspect every chain trace and revise the Fermi model.

Gate:

- structured Portuguese validation improves;
- grammar evaluation passes sanity tests;
- structured/shuffled behavior differs in the expected direction;
- one common sampler configuration works across three checkpoints;
- a final 8M campaign still fits the budget.

Pivot to a controlled Portuguese-like micro-language when natural Portuguese shows no interpretable grammar signal within the pilot or when a clean compositional split cannot be built quickly. Retain a small natural-Portuguese replication as external validity.

## Phase 2: final behavior trajectories

Run in this order:

1. structured Portuguese seed A;
2. token-shuffled Portuguese;
3. matched English;
4. structured Portuguese seed B.

Evaluate every checkpoint as soon as it is saved. The first main seed and controls create a coherent minimum report even if replication is reduced.

Freeze all data, checkpoint, and behavior outputs before inspecting the final LLC trajectory.

## Phase 3: LLC campaign

Order by scientific value:

1. main Portuguese seed A at five fixed checkpoints;
2. two behavior-bracketing checkpoints;
3. main seed B at early/candidate/late points;
4. shuffled control at early/candidate/late points;
5. matched English at early/candidate/late points;
6. extra chains or one nearby sampler setting around the candidate interval;
7. null-temperature/noise diagnostic;
8. optional intervention.

If time becomes scarce, remove Spanish, broad component localization, and dense control checkpoints before removing diagnostics or the shuffled control.

## Phase 4: analysis and report

Minimum report artifacts:

- behavioral trajectory figure;
- LLC trajectory with chain uncertainty;
- sampler diagnostic figure;
- final-condition table;
- seed/checkpoint changepoint table;
- runtime/cost/reproducibility table;
- explicit limitations on transient checkpoints and sampler sensitivity.

Write the report from real result files only. Use the mock report as a layout reference, not a numerical template.

## Bounded autonomy schedule

Codex may autonomously:

- implement code;
- run CPU smoke tests;
- run the 3M pilot within the declared two-hour GPU budget;
- perform the predeclared sampler sweep;
- reject invalid runs and rerun one corrected setting;
- generate diagnostics and update manifests.

Human approval is required before:

- provisioning or resizing a paid VM;
- beginning the final 8M campaign;
- adding more than two incremental GPU-hours;
- changing the primary hypothesis or control definitions after seeing results;
- using Adaption-selected recipes in the confirmatory run;
- publishing, deleting the VM, or deleting raw runs.

## Scope-cut order

When projected runtime exceeds the remaining budget:

1. remove Spanish;
2. remove broad susceptibility scans;
3. reduce second-seed LLC to three checkpoints;
4. keep only three LLC points per control;
5. reduce main seed from seven to five LLC points;
6. reduce draws modestly only after running-mean stability is demonstrated;
7. never drop below two chains or omit diagnostics.
