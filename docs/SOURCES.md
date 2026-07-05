# Sources and freshness notes

> Status, 2026-06-21: source list for planning and submission context. Verify external links again before
> final citation polish in the Google Doc.

Accessed 2026-06-20 unless otherwise stated.

## Hackathon

- Apart Research, Global South AI Safety Hackathon: https://apartresearch.com/sprints/global-south-ais-hackathon-2026-06-19-to-2026-06-21

## Codex — official OpenAI documentation

- Codex CLI: https://developers.openai.com/codex/cli
- Remote connections and SSH projects: https://developers.openai.com/codex/remote-connections
- Non-interactive `codex exec`: https://developers.openai.com/codex/noninteractive
- Permissions: https://developers.openai.com/codex/permissions
- AGENTS.md: https://developers.openai.com/codex/guides/agents-md

## SLT and devinterp

- devinterp repository and v2 quickstart: https://github.com/timaeus-research/devinterp
- Timaeus sampling hyperparameter guide: https://timaeus.co/research/2026-04-21-sampling-guide
- Hoogland et al., Loss Landscape Degeneracy and Stagewise Development in Transformers: https://arxiv.org/abs/2402.02364

## GCP

- G2/G4 VM creation: https://docs.cloud.google.com/compute/docs/gpus/create-gpu-vm-g-series
- GPU driver installation: https://docs.cloud.google.com/compute/docs/gpus/install-drivers-gpu
- G2 machine specifications/limitations: https://docs.cloud.google.com/compute/docs/accelerator-optimized-machines
- GPU locations: https://docs.cloud.google.com/compute/docs/regions-zones/gpu-regions-zones
- Cloud Billing budgets: https://cloud.google.com/billing/docs/how-to/budgets

## Models and data

- TinyStories-3M: https://huggingface.co/roneneldan/TinyStories-3M
- TinyStories-8M: https://huggingface.co/roneneldan/TinyStories-8M
- OPUS-100: https://huggingface.co/datasets/Helsinki-NLP/opus-100

## Adaption

- AutoScientist: https://adaptionlabs.ai/auto-scientist

## Caveats

- GCP prices are intentionally not hard-coded as authoritative. Verify the console quote.
- Package interfaces and model revisions can change. The infrastructure gate must inspect installed signatures and versions.
- The public Adaption page does not document the checkpoint/API controls required here; qualification is necessary.
