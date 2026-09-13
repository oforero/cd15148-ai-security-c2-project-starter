# FGSM Evasion Attack Results

## Clean Model Baseline

Measured with `evaluate.py` on the shipped `receipt_cnn_clean.pt` checkpoint against the clean test set (390 images, 195 per class).

- **Model:** ReceiptCNN
- **Test accuracy:** 0.9436
- **Precision:** 0.9943 | **Recall:** 0.8923 | **F1:** 0.9405
- **Confusion matrix (clean):** `[[194, 1], [21, 174]]` (rows = true, cols = predicted; classes: non_receipt, receipt). The model is near-perfect on non_receipt (1 false positive) and misses 21 real receipts, so recall is its weaker side even before any attack.
- **FGSM baseline (epsilon = 0.000):** adversarial accuracy is 0.9436, identical to clean accuracy, and the attack success rate is 0.0000. At epsilon 0 the perturbation `epsilon * sign(gradient)` is zero, so the adversarial image equals the clean image. This confirms the later degradation comes from the perturbation itself, not from a difference in the evaluation loop.

## FGSM Results

Full epsilon sweep produced by `python attacks/01_fgsm_evasion.py` (saved to `attacks/results/01_fgsm/fgsm_results.json`). Clean accuracy is constant because it is the same clean test set every time; only the adversarial column changes with epsilon. Attack success rate is the fraction of originally correct images that the attack flipped (`flipped / clean_correct`), so it excludes images the model already got wrong on clean input.

| Epsilon | Clean Accuracy | Adversarial Accuracy | Attack Success Rate |
|---------|---------------|---------------------|-------------------|
| 0.000 | 0.9436 | 0.9436 | 0.0000 |
| 0.010 | 0.9436 | 0.8077 | 0.1440 |
| 0.030 | 0.9436 | 0.5103 | 0.4592 |
| 0.050 | 0.9436 | 0.3000 | 0.6821 |
| 0.100 | 0.9436 | 0.2718 | 0.7120 |
| 0.150 | 0.9436 | 0.4462 | 0.5272 |

Adversarial accuracy falls steadily from 0.9436 at epsilon 0 to 0.2718 at epsilon 0.10, a drop of 66.8 points, while the attack success rate climbs to 0.7120. The progressive degradation the attack is meant to demonstrate is clear across the 0.010 to 0.100 range.

## Visual Evidence

`visualize_fgsm()` saves one clean/adversarial comparison per epsilon under `attacks/results/01_fgsm/` for the first test image (`openimages_0000`, a true non_receipt).

![FGSM epsilon 0.000](../attacks/results/01_fgsm/fgsm_results_openimages_0000_0.png)

At epsilon 0.000 the two panels are identical: no perturbation, prediction unchanged.

![FGSM epsilon 0.010](../attacks/results/01_fgsm/fgsm_results_openimages_0000_0.01.png)

At epsilon 0.010 the perturbation is imperceptible to the eye, yet adversarial accuracy across the test set has already dropped to 0.8077.

![FGSM epsilon 0.030](../attacks/results/01_fgsm/fgsm_results_openimages_0000_0.03.png)

At epsilon 0.030 faint noise starts to appear on close inspection, and test-set accuracy has fallen to about chance (0.5103).

![FGSM epsilon 0.050](../attacks/results/01_fgsm/fgsm_results_openimages_0000_0.05.png)

At epsilon 0.050 the noise is visible but the image is still clearly the same scene; accuracy has collapsed to 0.3000.

![FGSM epsilon 0.100](../attacks/results/01_fgsm/fgsm_results_openimages_0000_0.1.png)

At epsilon 0.100 the perturbation is obvious as a grainy overlay; this is the strongest attack point, with adversarial accuracy at its minimum of 0.2718.

![FGSM epsilon 0.150](../attacks/results/01_fgsm/fgsm_results_openimages_0000_0.15.png)

At epsilon 0.150 the noise dominates the image, and adversarial accuracy rebounds to 0.4462 (see the analysis below).

## Analysis

**1. At what epsilon does accuracy drop below 50%?** Between epsilon 0.030 (0.5103, still just above half) and epsilon 0.050 (0.3000). The first sweep point below 50% is epsilon 0.050. Even at epsilon 0.010, a perturbation invisible to a human, accuracy has already dropped 13.6 points to 0.8077.

**2. How do you interpret the attack success rate?** The attack success rate measures only images the model classified correctly on clean input, so it is a clean measure of the attack's power rather than of pre-existing model errors. At epsilon 0.100 it reaches 0.7120, meaning the attack broke about 71% of the predictions the model originally got right. It peaks at epsilon 0.100 rather than at the largest epsilon tested.

**3. Would these perturbations be visible to a human?** At epsilon 0.010 and 0.030 the perturbation is effectively invisible or barely noticeable, yet it is already enough to halve accuracy. This is the core danger of FGSM: the input still looks like a normal receipt or non-receipt to a human reviewer while the model is reliably fooled. From epsilon 0.050 upward the noise becomes visibly obvious, which would make the tampering detectable on manual inspection.

**4. Why does accuracy rebound at epsilon 0.150?** The trend is not perfectly monotonic: adversarial accuracy bottoms out at 0.2718 (epsilon 0.100) and then rises to 0.4462 at epsilon 0.150. This is expected behaviour for a single-step attack at large epsilon. FGSM takes one fixed-size step in the sign-of-gradient direction; once the step is large enough, the perturbation saturates many pixels at the [0, 1] clamp boundary and pushes both classes toward the same collapsed prediction. For a binary classifier, that collapse coincidentally lands on the correct label for a subset of images, so measured accuracy climbs back up. The useful, reliable attack range on this model is roughly epsilon 0.010 to 0.100; beyond that a single-step method loses precision, and an iterative attack (for example PGD) would be the tool to push accuracy lower still.

**5. What are the implications for the expense system?** An attacker with white-box access to the classifier (the model weights or gradients) can craft perturbations that are invisible at epsilon 0.010 to 0.030 yet flip the model's decision. In the expense pipeline this means a manipulated image could be made to pass as a valid receipt, or a genuine receipt could be forced to be rejected, without a human reviewer noticing anything wrong with the image. The mitigation is not at the pixel level: it requires adversarial training, input preprocessing or randomization, and above all not treating a single CNN score as sufficient evidence for an automated reimbursement decision.
