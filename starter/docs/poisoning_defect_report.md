# Defect Report: Attack 2 (Label-Flip Poisoning) Success Criterion Is Not Achievable

## Summary

The rubric for Attack 2 requires the poisoned model to show an accuracy drop of **at least 5 percentage points** versus the clean model, produced by flipping **at most 10% of training labels**. Following the classroom's own instructions produces the **opposite** result: the poisoned model is consistently as good as or better than the clean model. When the comparison is run rigorously (multiple training runs per condition), no label-flip strategy produces a drop, because the clean model's training variance is roughly three times larger than the 5-point effect the rubric expects to measure.

This is a defect in the exercise design, not in a learner's implementation.

## Environment

- Project: AI System Compromise & Resilience Assessment (Finance Edition), `cd15148-ai-security-c2-project-starter`.
- Component: `starter/classifier` (ReceiptCNN, ~26K params) trained by the provided `starter/classifier/train.py` for 15 epochs.
- Attack: `starter/attacks/02_label_flip_poisoning.py`.

## Steps to Reproduce

Following the classroom "Run, Retrain, and Compare" instructions exactly:

```bash
cd starter/attacks
python 02_label_flip_poisoning.py                 # 5% symmetric random flip (default)
cd ../classifier
python train.py --data-dir poisoned_data --checkpoint-name receipt_cnn_poisoned.pt
python evaluate.py --model-path checkpoints/receipt_cnn_poisoned.pt --test-dir balanced_data/test
python evaluate.py --model-path checkpoints/receipt_cnn_clean.pt    --test-dir balanced_data/test
```

## Observed vs Expected

**Expected:** poisoned accuracy is at least 5 points below clean accuracy.

**Observed (single run, as instructed):** the freshly trained poisoned model scored **0.9744** while the provided clean checkpoint scored **0.9231**. The poisoned model was **5.1 points better**, the opposite of the requirement.

**Observed (rigorous, 3 runs per condition at the 10% cap):**

| Condition | runs | mean accuracy | min | max | drop vs clean |
|-----------|------|---------------|-----|-----|---------------|
| clean (self-trained) | 3 | 0.8795 | 0.8282 | 0.9744 | baseline |
| random flip | 3 | 0.9274 | 0.9154 | 0.9359 | -4.79 pts (better) |
| targeted flip | 3 | 0.9564 | 0.9513 | 0.9615 | -7.69 pts (better) |
| confidence-based flip | 3 | 0.9316 | 0.9308 | 0.9333 | -5.21 pts (better) |

No strategy, including a model-informed confidence-ranked flip designed to maximize damage, produced any drop. All drops are negative.

## Root Cause

1. **Nondeterministic training dominates the signal.** `train.py` sets `SEED = 42` and seeds `random`, `numpy`, and `torch`, but does not enable deterministic algorithms (`torch.use_deterministic_algorithms(True)`, `cudnn.deterministic = True`, `cudnn.benchmark = False`) or seed DataLoader workers. On GPU, identical runs therefore vary widely. The clean baseline above ranges from **0.8282 to 0.9744, a 14.6-point spread across three identical runs**. That is about 3x the 5-point effect the rubric asks learners to measure, so the measurement is dominated by noise.

2. **The model is robust to the allowed budget.** A small CNN trained on ~1150 images shrugs off <=10% label noise; roughly 90% clean signal dominates gradient descent, so flipped labels are effectively averaged out.

3. **Baseline mismatch in the instructions.** The classroom's compare step benchmarks a freshly retrained poisoned model against the shipped `receipt_cnn_clean.pt` checkpoint, whose training procedure is unknown and which is a weaker run than a fresh 15-epoch train. This alone can invert the comparison.

4. **The symmetric flip can be self-correcting.** The clean model under-predicts receipts (recall ~0.85), so the non_receipt to receipt half of a symmetric flip nudges the boundary in the direction that *raises* accuracy.

## Impact

Learners cannot satisfy the Attack 2 success criterion by following the instructions, and cannot satisfy it by any compliant strategy on this model and dataset. The only way to "pass" is to submit a single lucky run where the clean model happened to train well and the poisoned model happened to train poorly, which rewards noise rather than understanding.

## Suggested Fixes

1. **Make training deterministic** in `train.py` (`torch.use_deterministic_algorithms(True)`, `cudnn.deterministic = True`, `cudnn.benchmark = False`, seeded DataLoader generator). This removes the ~15-point variance so any real poisoning effect becomes measurable.
2. **Pin the baseline** to a self-trained clean model produced by the same `train.py` invocation and seed, not the shipped checkpoint, so the comparison is controlled.
3. **Make the effect exceed the budget:** raise the flip-rate cap, specify a targeted or informed flip in the instructions, use more epochs or a more sensitive model, or lower the required drop (for example to >= 2 points).
4. **Require multiple runs** and compare means, since a single run sits inside the noise band.

## Evidence Artifacts

- `starter/run_poisoning_experiment.sh` and `starter/aggregate_poisoning_results.py` reproduce the multi-run comparison table above.
- Per-run metrics and confusion matrices under `starter/classifier/results/poisoning_experiment/`.
