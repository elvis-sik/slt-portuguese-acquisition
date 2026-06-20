# Research protocol

## 1. Research question and operational definitions

The target phenomenon is a change from early lexical/distributional adaptation to held-out compositional grammatical generalization during Portuguese continued pretraining.

A **behavioral transition candidate** is a localized change in the slope of a continuous held-out grammar log-probability margin, supported by a predeclared changepoint analysis and replicated in the second main seed.

A **geometric transition candidate** is a localized change in an SLT-derived estimate such as the Local Learning Coefficient (LLC), measured using a fixed localized posterior protocol and accompanied by acceptable chain diagnostics.

The central test is temporal alignment plus control specificity. The study does not require that either curve be mathematically discontinuous.

## 2. Models

Pilot model: `roneneldan/TinyStories-3M`.

Final model: `roneneldan/TinyStories-8M`.

At runtime, record exact parameter counts rather than assuming the names are exact counts. Preserve the original tokenizer and architecture. The initial checkpoint should be an English-trained causal LM. No instruction tuning is needed.

## 3. Training

Use full-parameter next-token continued pretraining.

Initial final configuration:

| Item | Starting value |
|---|---:|
| Sequence length | 128 tokens |
| Global batch | 32 sequences |
| Tokens/optimizer step | 4,096 |
| Target tokens/trajectory | 8 million |
| Approximate optimizer steps | 1,953 |
| Optimizer | AdamW |
| LR pilot | 3e-5, 1e-4, 3e-4 |
| Initial final LR | 1e-4, subject to pilot |
| Weight decay | 0 initially |
| Training precision | FP32 initially; BF16 only after comparison |
| SGLD precision | FP32 |

Do not pretrain an English model from scratch. The experiment concerns adaptation from an existing English checkpoint.

## 4. Data and controls

Preferred source: a filtered English-Portuguese parallel corpus such as OPUS-100. Use Portuguese sides for the main trajectory and exactly corresponding English sides for the matched English control.

Construct immutable train, validation, sampler-reference, and grammar-evaluation splits. The sampler-reference set must never overlap with training batches or the behavioral test set.

Conditions:

1. **Structured Portuguese:** natural Portuguese token sequences.
2. **Token-shuffled Portuguese:** the same Portuguese training examples with tokens shuffled inside each sequence according to a saved deterministic mapping. Preserve sequence lengths and broad token frequencies while destroying order.
3. **Matched English:** the parallel English sentences, matched by example and training budget.
4. **Second Portuguese seed:** same data and hyperparameters, different initialization of data order/dropout.

Do not add Spanish until these conditions are complete.

### Filtering record

Record counts after every filter:

- language-ID failures;
- duplicate pairs;
- empty or markup-heavy samples;
- extreme source/target length ratios;
- sequences shorter than the minimum or longer than the maximum;
- train/eval leakage;
- byte and token totals;
- tokenizer fertility: model tokens per UTF-8 byte and per whitespace word.

## 5. Checkpoints

Save by cumulative target tokens, not merely optimizer step:

```text
0, 25k, 50k, 100k, 200k, 400k,
800k, 1.5M, 3M, 5M, 8M tokens
```

The actual schedule may shift after the pilot, but it must be fixed before the final LLC inspection.

Behavioral metrics are calculated at every checkpoint.

LLC checkpoints:

- five fixed log-spaced checkpoints;
- the two checkpoints bracketing the largest derivative in a behavioral metric selected without viewing LLC;
- a maximum of two additional points if the candidate interval is too wide.

Document the selection algorithm and the timestamp at which it was frozen.

## 6. Behavioral metrics

### Target validation bits per byte

Compute total token negative log likelihood in nats, divide by the UTF-8 byte count represented by the scored text, and convert nats to bits:

\[
\mathrm{BPB} = \frac{\mathrm{NLL}_{\mathrm{nats}}}{N_{\mathrm{bytes}}\ln 2}.
\]

This is preferable to raw cross-language token perplexity because an English-oriented tokenizer may segment Portuguese differently.

### Grammar minimal-pair margin

For each grammatical/ungrammatical pair, compute a contrastive margin on the differing continuation:

\[
m_i = \log P(s_i^{+}) - \log P(s_i^{-}).
\]

Report the distribution, mean/median margin, bootstrap interval, and thresholded accuracy. The continuous margin is primary; accuracy is secondary. Construct agreement, article-noun, adjective-noun, and subject-verb cases with held-out lexical combinations. Include nonce or templated cases if possible to reduce memorization.

### Lexical acquisition

Use a predeclared word-completion or translation-choice probe with held-out contexts. Report accuracy and continuous log-probability margins. Avoid evaluating on the exact training sentences.

### English retention

Evaluate the unchanged English validation set at every checkpoint. Report relative BPB change and absolute BPB.

## 7. LLC sampling protocol

At each selected checkpoint, define a localized posterior centered at checkpoint weights and use RMSProp-SGLD unless diagnostics justify another sampler.

Use one fixed Portuguese sampler-reference set for all checkpoints of the structured Portuguese trajectory. Use the corresponding condition-specific reference set for each control. Keep fixed:

- reference-set identity and size;
- sequence length;
- loss reduction/normalization;
- batch size;
- inverse-temperature convention;
- localization convention;
- sampler optimizer;
- burn-in, draw count, and draw spacing;
- parameter subset, normally the full trainable model;
- numerical precision.

Tune one global sampler configuration through a coarse-to-fine sweep described in `docs/02_SLT_BAYESIAN_COMPLICATIONS.md`. Never select a different “best” configuration for every checkpoint.

## 8. Diagnostics required for every reportable LLC

- baseline checkpoint loss;
- per-chain sampling-loss traces;
- running LLC estimate per chain;
- between-chain dispersion;
- autocorrelation or effective-sample-size proxy;
- parameter displacement from the center checkpoint;
- NaN/spike checks;
- exact sampler settings;
- sensitivity at one nearby parameter setting in the headline transition region;
- a null-temperature or noise diagnostic where supported.

Reject or label exploratory any checkpoint whose chains keep moving downhill, fail to plateau, disagree substantially, or leave the intended local region.

## 9. Changepoint analysis

Predeclare a simple comparison:

- null model: one linear trend versus log target tokens;
- alternative: two-segment piecewise-linear trend with one changepoint;
- model comparison: BIC and cross-validated error;
- uncertainty: seed-level estimates and bootstrap over evaluation items where applicable.

A reportable joint candidate requires:

1. supported LLC slope/level change;
2. nearby change in continuous grammar margin;
3. replication or compatible uncertainty in the second Portuguese seed;
4. absence of the same joint pattern in shuffled Portuguese and matched English;
5. acceptable sampler diagnostics.

Do not infer simultaneity more precisely than checkpoint density permits.

## 10. Causal extension

Only after the primary result is clear:

1. identify one component using a predeclared localized susceptibility or restricted measurement;
2. branch from a checkpoint before the transition;
3. compare no-freeze, candidate-component freeze, and matched-control freeze;
4. continue training under an equal token budget;
5. report both grammar and target validation loss.

Freezing reduces capacity, so this is limited causal evidence rather than circuit identification.

## 11. Outcomes and interpretation

- **Aligned transition in structured Portuguese only:** evidence for an SLT-informed developmental marker.
- **Grammar transition without LLC change:** language learning occurred, but this LLC setup did not detect it.
- **LLC change without behavioral change:** possible internal restructuring, incomplete probes, or sampler artifact.
- **Smooth behavior and smooth LLC:** informative null result.
- **Sampler invalid on transient checkpoints:** methodological result; pivot to a controlled micro-language or report limitations rather than fabricate geometry.

## 12. Reproducibility record

Every run manifest must contain Git commit, command, config hash, seed, model/tokenizer revision, parameter count, data split hashes, package versions, GPU/driver, precision, optimizer, cumulative tokens and bytes, runtime, estimated cost, checkpoint hashes, and exit status.
