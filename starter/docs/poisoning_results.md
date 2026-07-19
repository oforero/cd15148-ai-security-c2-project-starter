# Data Poisoning Results

## Attack Configuration

- **Method:** Label-flip poisoning (moving training images between class folders).
- **Flip rate:** 10% of training labels (the rubric cap), across three selection strategies.
- **Labels flipped:** ~114 of 1154 for the random symmetric flip (57 per class); 115 of 1154 for the targeted and confidence strategies (all from the receipt class).
- **Strategies compared:**
  - `random` : the scaffold method, random symmetric flip of both classes.
  - `targeted` : all flips in one direction (receipt to non_receipt), chosen at random.
  - `confidence` : same direction, but flipping the examples the clean model is most confident about (a model-informed, white-box attack).
- **Goal:** show whether a small (<=10%) training-label corruption degrades a model evaluated on otherwise-clean data, and whether smarter selection increases the damage.

> **Important:** the measured effect turned out to be within training-run noise. See the multi-run result and the [Exercise Defect](#exercise-defect) section below. This document reports the honest outcome rather than a single lucky run.

## Label Flip Evidence

`visualize_flip()` saves clean images next to their label-flipped copies. The attack changes the label (which folder the image lives in), not the pixel content.

![Label flip comparison](../attacks/results/02_label_flip/confidence/label_flip_results_5.png)

## Primary Result: Multi-Run Comparison

Because a single training run of this model varies widely, each condition was trained 3 times (`run_poisoning_experiment.sh`) and evaluated on the same clean test set. Accuracy, mean over 3 runs:

| Condition | runs | mean acc | min | max | drop vs clean |
|-----------|------|----------|-----|-----|---------------|
| clean (self-trained) | 3 | 0.8795 | 0.8282 | 0.9744 | baseline |
| random flip | 3 | 0.9274 | 0.9154 | 0.9359 | -4.79 pts |
| targeted flip | 3 | 0.9564 | 0.9513 | 0.9615 | -7.69 pts |
| confidence flip | 3 | 0.9316 | 0.9308 | 0.9333 | -5.21 pts |

A negative drop means the poisoned model scored **higher** than clean. No strategy produced the required 5-point drop. The clean baseline alone spans 14.6 points across three identical runs (0.8282 to 0.9744), which is why the comparison is unreliable: the training noise is far larger than any poisoning effect.

## Representative Single Run (for per-class detail)

To illustrate the confusion-matrix structure, here is one representative pairing (self-trained clean vs a 10% targeted-flip poisoned model). Per-run confusion-matrix PNGs are saved under `../classifier/results/poisoning_experiment/<condition>_<run>/confusion_matrix.png`.

### Baseline (Clean Model), representative run

| Metric | Value |
|--------|-------|
| Accuracy | 0.9718 |
| Precision | 0.9946 |
| Recall | 0.9487 |
| F1 Score | 0.9711 |

Confusion matrix (rows = true, cols = predicted; classes: non_receipt, receipt):

| | pred non_receipt | pred receipt |
|--|--|--|
| **true non_receipt** | 194 | 1 |
| **true receipt** | 10 | 185 |

### Poisoned Model, representative run

| Metric | Value |
|--------|-------|
| Accuracy | 0.9385 |
| Precision | 0.9942 |
| Recall | 0.8821 |
| F1 Score | 0.9348 |

| | pred non_receipt | pred receipt |
|--|--|--|
| **true non_receipt** | 194 | 1 |
| **true receipt** | 23 | 172 |

## Impact Analysis

Representative single run:

| Metric | Clean | Poisoned | Change |
|--------|-------|----------|--------|
| Accuracy | 0.9718 | 0.9385 | -3.33 pts |
| Precision | 0.9946 | 0.9942 | -0.04 |
| Recall | 0.9487 | 0.8821 | -6.66 pts |
| F1 | 0.9711 | 0.9348 | -3.63 pts |

This single pairing *looks* like a 3.3-point drop, driven by a fall in receipt recall (10 missed receipts becomes 23). But the multi-run table shows this is an artifact of which runs were paired, not a reliable effect: averaged over 3 runs, every strategy scored above the clean mean.

## Key Findings

1. **The accuracy drop is not real.** Averaged over 3 runs, no strategy (random, targeted, or the model-informed confidence flip) produced a drop; all were slightly positive-for-the-model. A single run can show a few points either way purely from training nondeterminism.
2. **Which class is affected.** When poisoning does bite in a single run, it is the receipt class: flipping receipts to non_receipt raises receipt false-negatives (recall falls), while non_receipt stays near-perfect. Precision barely moves. This matches the direction of the attack.
3. **What the confusion matrix shows.** The damage is concentrated in the bottom-left cell (true receipt, predicted non_receipt). The model becomes more reluctant to call an image a receipt, consistent with training on receipts mislabeled as non-receipts.
4. **Implications.** This small CNN is robust to <=10% label noise: 90% clean signal dominates, and even a targeted, confidence-ranked flip within the same budget could not overcome it. A real attacker would need a larger budget, a backdoor/trigger approach, or access to a more sensitive pipeline. Most importantly, the exercise's success criterion cannot be measured reliably on this setup (below).

## Exercise Defect

The rubric requires a >= 5-point accuracy drop from a <= 10% label flip, but this is not achievable as specified: the clean model's training variance (~15 points) is roughly 3x the required effect, so the comparison measures training noise rather than poisoning, and following the instructions produces a poisoned model that is as good as or better than clean. Full analysis, reproduction, root cause, and suggested fixes are in the [Poisoning Defect Report](poisoning_defect_report.md).
