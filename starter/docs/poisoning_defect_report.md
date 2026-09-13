# Defect Report: Attack 2 (Label-Flip Poisoning) Default Configuration Is Fragile

## Summary

The Attack 2 success criterion (a >= 5-point accuracy drop from a <= 10% label flip) **is achievable**, but only under a controlled setup: deterministic training, a fair self-trained baseline, and a model-informed flip strategy. A model-informed confidence-ranked flip of about 10% of labels produces a reproducible 5.90-point accuracy drop (see `poisoning_results.md`).

The defect is that the exercise as scaffolded does not steer learners to that setup, and the most natural reading of the instructions actively works against it. Followed literally, the default path (a 5% random symmetric flip, compared against the shipped checkpoint, on nondeterministic GPU hardware) does not reliably show a drop and often shows the poisoned model scoring higher than clean. Learners who do exactly what the scaffold suggests will conclude, wrongly, that their attack failed.

This is a defect in the exercise design and defaults, not in a correct implementation.

## Environment

- Project: AI System Compromise & Resilience Assessment (Finance Edition), `cd15148-ai-security-c2-project-starter`.
- Component: `starter/classifier` (ReceiptCNN, ~26K params) trained by the provided `starter/classifier/train.py` for 15 epochs.
- Attack: `starter/attacks/02_label_flip_poisoning.py` (implements `random`, `targeted`, and `confidence` strategies).

## What Achieves the Criterion (and What the Defaults Do Instead)

**Achieves it:** deterministic training (CPU, seed 42) + fair self-trained baseline + confidence-ranked flip at ~10%. Result: accuracy 0.9667 to 0.9077, a 5.90-point drop, identical across three runs.

**The scaffold defaults do not:**

1. **Default flip rate and strategy are too weak.** The script defaults to a 5% random symmetric flip. Even at the 10% cap, the random flip lands at a 4.36-point drop and a plain targeted flip at 4.62, both short of 5. Only the model-informed confidence flip clears the bar. The instructions do not point learners toward a strong enough attack.

2. **The suggested baseline is confounded.** The classroom compare step benchmarks a freshly retrained poisoned model against the shipped `receipt_cnn_clean.pt` checkpoint, whose training procedure is unknown and which is a weaker run than a fresh 15-epoch train. Following that literally produced a poisoned model scoring 0.9744 against the checkpoint's 0.9231, a poisoned model that looks 5 points **better** than clean.

3. **Training is nondeterministic on GPU/MPS.** `train.py` sets `SEED = 42` and seeds `random`, `numpy`, and `torch`, but does not enable deterministic algorithms (`torch.use_deterministic_algorithms(True)`, `cudnn.deterministic = True`, `cudnn.benchmark = False`) or seed the DataLoader workers. On GPU/MPS, identical runs vary widely: an earlier multi-run of the clean baseline spanned 0.8282 to 0.9744, about 15 points across three identical runs. That is roughly 3x the 5-point effect, so on that hardware training noise can hide or reverse the poisoning signal. (On CPU the same code is deterministic, which is why the controlled result is reproducible there.)

## Observed Result (Controlled, Deterministic, CPU)

| Condition | Accuracy | Recall | F1 | Accuracy drop vs clean |
|-----------|----------|--------|-----|------------------------|
| clean (self-trained) | 0.9667 | 0.9385 | 0.9657 | baseline |
| random flip (10%) | 0.9231 | 0.8769 | 0.9194 | 4.36 pts |
| targeted flip (10%) | 0.9205 | 0.8462 | 0.9141 | 4.62 pts |
| confidence flip (10%) | 0.9077 | 0.8564 | 0.9027 | 5.90 pts |

Each condition was trained three times; all three runs were bit-identical, so these numbers are exactly reproducible on CPU.

## Impact

A learner who follows the scaffold literally (default 5% random flip, compared to the shipped checkpoint, on the workspace GPU) will see no drop, or an inverted result, and reasonably conclude the exercise is broken. Reaching the required drop takes three departures from the defaults that the instructions do not call out: a stronger model-informed strategy, a fair self-trained baseline, and deterministic training. The criterion is sound; the scaffold does not lead learners to a configuration where it holds.

## Suggested Fixes

1. **Make training deterministic** in `train.py` (`torch.use_deterministic_algorithms(True)`, `cudnn.deterministic = True`, `cudnn.benchmark = False`, seeded DataLoader generator), so the poisoning effect is not swamped by run-to-run variance on GPU.
2. **Pin the baseline** to a self-trained clean model produced by the same `train.py` invocation and seed, not the shipped checkpoint, so the comparison is controlled.
3. **Steer the attack strength.** Point learners at a targeted or model-informed flip at the full 10% budget rather than a 5% random flip, or lower the required drop, so a correct attack clears the criterion without relying on lucky variance.
4. **State the expected magnitude and require reproducibility** (for example, report identical results across repeated runs) so a single lucky run is neither necessary nor sufficient.

## Evidence Artifacts

- `starter/run_poisoning_experiment.sh` and `starter/aggregate_poisoning_results.py` reproduce the multi-run comparison table above.
- Per-run metrics and confusion matrices under `starter/classifier/results/poisoning_experiment/`.
- Full before/after analysis in `starter/docs/poisoning_results.md`.
