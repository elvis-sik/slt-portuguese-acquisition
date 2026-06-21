# Refusal baseline — small "aligned" English models (EN vs PT)

Step-1 validation for the "does alignment generalize across languages?" study.
Benchmark: 22 harmful (AdvBench-derived) + 6 benign prompts, English + Portuguese
(`data/eval/refusal_advbench_en_pt.jsonl`). Refusal = AdvBench refusal-string match
(EN+PT phrases). Greedy decoding. See `scripts/refusal_eval.py`.

| Model | harmful-EN | harmful-PT | benign |
|---|---|---|---|
| SmolLM2-135M-Instruct | 4% | 4% | 0% |
| SmolLM2-360M-Instruct | **18%** | **4%** | 0% |
| TinyLlama-1.1B-Chat-v1.0 | 0% | 0% | 0% |

**Finding:** tiny instruction-tuned models have negligible safety alignment
(SFT+DPO here is helpfulness-tuned). Only SmolLM2-360M shows any refusal signal,
and it already drops 18%→4% English→Portuguese — alignment is both shallow and
language-brittle. Raw model completions are kept locally (gitignored), not published.
