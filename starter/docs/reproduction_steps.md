# Reproduction Steps

Every finding below can be reproduced from a clean checkout of the project. Commands are copy-pasteable and assume you start from the repository's `starter/` directory unless a step says otherwise. Expected outputs are the values observed during the assessment; exact figures for the training-based steps vary run to run (see Step 4).

## Prerequisites

- Python 3.12 (the project targets 3.12.13) and `pip`.
- A classroom OpenAI-compatible API key and base URL, required only for the chatbot attacks (Steps 5 to 7).
- No GPU is required; all steps run on CPU. Docker is not required; the supply chain step reads a provided report.

## Environment Setup

From the repository root:

```bash
python3.12 -m venv .venv
source .venv/bin/activate          # macOS/Linux
# .venv\Scripts\activate           # Windows

pip install -r starter/requirements.txt
```

Configure the API key for the chatbot attacks:

```bash
cp starter/.env.example starter/rag_chatbot/.env
# edit starter/rag_chatbot/.env to set OPENAI_API_KEY and OPENAI_BASE_URL
```

All remaining commands are run from `starter/`:

```bash
cd starter
```

## Step 1: Verify the Clean Model and Baseline

```bash
cd classifier
python evaluate.py --model-path checkpoints/receipt_cnn_clean.pt --test-dir balanced_data/test
cd ..
```

**Expected output:** accuracy 0.9436, precision 0.9943, recall 0.8923, F1 0.9405, confusion matrix `[[194, 1], [21, 174]]` on the 390-image clean test set. This is the baseline every attack is measured against.

## Step 2: FGSM Evasion Attack

```bash
python attacks/01_fgsm_evasion.py
```

**Expected output:** a printed sweep over epsilon values 0.000, 0.010, 0.030, 0.050, 0.100, 0.150 with clean accuracy constant at 0.9436 and adversarial accuracy falling from 0.9436 to about 0.27 at epsilon 0.100, then partly rebounding at 0.150. Results are written to `attacks/results/01_fgsm/fgsm_results.json` and one clean/adversarial comparison PNG per epsilon is saved under `attacks/results/01_fgsm/`. Full analysis in `docs/fgsm_results.md`.

| Epsilon | Adversarial Accuracy | Attack Success Rate |
|---------|---------------------|-------------------|
| 0.000 | 0.9436 | 0.0000 |
| 0.010 | 0.8077 | 0.1440 |
| 0.030 | 0.5103 | 0.4592 |
| 0.050 | 0.3000 | 0.6821 |
| 0.100 | 0.2718 | 0.7120 |
| 0.150 | 0.4462 | 0.5272 |

## Step 3: Label-Flip Poisoning (Single Run, as the Classroom Instructs)

```bash
python attacks/02_label_flip_poisoning.py                 # 5% symmetric random flip (default)
cd classifier
python train.py --data-dir poisoned_data --checkpoint-name receipt_cnn_poisoned.pt
python evaluate.py --model-path checkpoints/receipt_cnn_poisoned.pt --test-dir balanced_data/test
python evaluate.py --model-path checkpoints/receipt_cnn_clean.pt    --test-dir balanced_data/test
cd ..
```

**Expected output:** the poisoned model does not show the required 5-point accuracy drop. In our runs it scored as well as or better than the clean checkpoint. A single run is unreliable here because training is nondeterministic; see Step 4 for the controlled comparison. The `02_label_flip_poisoning.py` script accepts `--strategy {random,targeted,confidence}` and `--flip-rate` (kept at or below 0.10) to try stronger, model-informed flips.

## Step 4: Label-Flip Poisoning (Controlled Multi-Run Comparison)

```bash
FLIP_RATE=0.10 REPEATS=3 bash run_poisoning_experiment.sh
```

This poisons one dataset per strategy, trains and evaluates clean, random, targeted, and confidence conditions three times each, saves a confusion matrix per run under `classifier/results/poisoning_experiment/<condition>_<run>/`, and prints an aggregated table.

**Expected output:** no strategy produces a 5-point drop. Approximate mean accuracy over 3 runs: clean 0.8795 (min 0.8282, max 0.9744), random 0.9274, targeted 0.9564, confidence 0.9316. All poisoned means are at or above the clean mean, and the clean baseline alone spans about 15 points across identical runs. Interpretation and root cause are in `docs/poisoning_results.md` and `docs/poisoning_defect_report.md`.

## Step 5: Start the RAG Chatbot

The chatbot must be running for Steps 6 and 7.

```bash
cd rag_chatbot
python build_index.py        # builds the FAISS index from data/policies/
python app.py                # serves on http://localhost:5001
```

Leave this running and open a second terminal (with the virtual environment activated and `cd starter`) for the next steps. Verify it responds:

```bash
curl -X POST http://localhost:5001/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the meal expense limit?"}'
```

**Expected output:** a JSON response answering with the $75 meal limit and a `sources` list of public policy files.

## Step 6: Prompt Injection

```bash
python attacks/03_prompt_injection.py
```

**Expected output:** five techniques are sent to the chatbot and the full responses recorded to `attacks/results/03_prompt_injection/prompt_injection_results.json`. Summary: 1 of 5 injections succeeded at the answer layer (the role-hijack framed as a UI test), and 1 of 5 attempts surfaced the confidential document in `sources` (the Base64 attempt, whose answer was refused but whose retrieval still leaked). The two signals are counted separately. Full transcript in `docs/prompt_injection_transcript.md`.

## Step 7: Data Exfiltration

```bash
python attacks/04_data_exfiltration.py
```

**Expected output:** six exfiltration queries are sent and recorded to `attacks/results/04_exfiltration/data_exfiltration_results.json`. The confidential document `executive_bonus_structure_CONFIDENTIAL.md` appears in `sources` on all 6 of 6 queries, including one where the answer refused but the document was still retrieved. Evidence and architectural root cause in `docs/data_exfiltration_evidence.md`.

## Step 8: Supply Chain Analysis

No chatbot or model is needed; this reads the provided Trivy report and Dockerfile.

```bash
python attacks/05_supply_chain_analysis.py
```

**Expected output:** vulnerability counts of 0 CRITICAL, 34 HIGH, 160 MEDIUM, 601 LOW (804 total), the 3 fixable HIGH Python CVEs named with their fixed versions (`jaraco.context` to 6.1.0, `wheel` to 0.46.2), and six Dockerfile issues each with a remediation. Results to `attacks/results/05_supply_chain/supply_chain_report.json`; analysis in `docs/supply_chain_analysis.md`.

## Expected Results Summary

| Attack | Metric | Expected Result |
|--------|--------|----------------|
| FGSM Evasion | Adversarial accuracy vs epsilon | Falls from 0.9436 to 0.2718 across epsilon 0 to 0.100 (progressive degradation) |
| Label-Flip Poisoning | Accuracy drop vs clean | No drop; poisoned model matches or beats clean over 3 runs (success criterion not achievable, see defect report) |
| Prompt Injection | injection_successful / confidential_source_disclosed | 1 of 5 answer-layer bypass; 1 of 5 confidential source retrieved |
| Data Exfiltration | Confidential document retrieved | 6 of 6 queries retrieve `executive_bonus_structure_CONFIDENTIAL.md` |
| Supply Chain | Vulnerability counts and fixable HIGH CVEs | 804 total (0 CRIT, 34 HIGH, 160 MED, 601 LOW); 3 fixable HIGH; 6 Dockerfile issues |
