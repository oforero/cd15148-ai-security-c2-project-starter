# Red Team Charter

## Engagement Details

| Field | Value |
|-------|-------|
| **Engagement Name** | FinanceGuard AI Red Team Assessment |
| **Date** | 2026-07-18 |
| **Assessor** | Oscar Forero (Junior AI Red Team Operator) |
| **Sponsor** | FinanceGuard Inc. CISO |

## Objectives

1. **FGSM Evasion** against the Receipt Classifier: demonstrate that small, near-invisible pixel perturbations uisng the model's gradients cause the CNN to misclassify valid receipts.
2. **Label-Flip Data Poisoning** against the training pipeline: demonstrate that corrupting a small fraction of training labels measurably degrades model accuracy.
3. **Prompt Injection** against the RAG Chatbot: demonstrate that crafted inputs can override the system instructions and manipulate the assistant's behavior.
4. **Data Exfiltration** from the RAG vector store: demonstrate that confidential policy documents can be retrieved through ordinary chatbot queries.
5. **Supply Chain Analysis** of the deployment pipeline: demonstrate that the Docker image and its dependencies contain exploitable vulnerabilities.

## Scope

### In Scope

- **Receipt Classifier (CNN)**: the image classification model and its training pipeline (`classifier/`).
- **Expense Policy RAG Chatbot**: the LLM assistant and its FAISS vector store (`rag_chatbot/`).
- **Deployment infrastructure**: the provided `Dockerfile`, `requirements.txt`, and Trivy report (`06_trivy_report.json`).
- Only the provided lab environment and its bundled sample data and policy documents.

### Out of Scope

- FinanceGuard production systems, live customer data, and real employee records.
- Third-party services and external APIs beyond the provided chatbot endpoint.
- Network, physical, and social-engineering attacks against FinanceGuard staff or premises.
- Denial-of-service or any availability-degrading attacks against any system.
- Modification of the provided infrastructure code; all attacks run against it unchanged.

## Rules of Engagement

1. Testing is confined to the provided lab environment; no attacks touch live or production systems.
2. No real personal, financial, or employee data is used, exfiltrated, or retained.
3. Attacks are non-destructive and reversible: poisoning operates on a copy of the dataset and never alters the original training data or the clean test set.
4. No availability impact: no denial-of-service, resource exhaustion, or account lockout attempts.
5. All activity is logged and documented so every finding is fully reproducible.
6. Confidential data surfaced during exfiltration testing is recorded as evidence only, never redistributed.
7. Findings are disclosed solely to FinanceGuard; no public disclosure without written authorization.

## Success Criteria

| Attack Vector | Success Metric |
|---------------|---------------|
| FGSM Evasion | Adversarial accuracy measurably decreases across at least 3 epsilon values, showing progressive degradation; results saved to JSON. |
| Label-Flip Poisoning | Flipping at most 10% of training labels produces at least a 5 percentage-point accuracy drop on the same clean test set, reported with before/after accuracy, precision, recall, and F1. |
| Prompt Injection | At least 5 distinct techniques executed, independently tracking answer misbehavior (`injection_successful`) and confidential source disclosure (`confidential_source_disclosed`), with per-attempt analysis. |
| Data Exfiltration | At least 5 distinct query strategies executed, with evidence that the CONFIDENTIAL document is retrieved (in the answer text or in `sources`), plus an architectural root-cause analysis. |
| Supply Chain Analysis | Trivy vulnerabilities counted by severity, specific HIGH CVEs named with affected package and fix, and at least 3 Dockerfile issues identified, each with a concrete remediation. |

## Deliverables

- Five completed attack scripts in `attacks/` (`01_fgsm_evasion.py` through `05_supply_chain_analysis.py`).
- Vulnerability Log (VUL-001 through VUL-005).
- Per-attack results documents (FGSM sweep, poisoning comparison with confusion matrices, prompt injection transcript, data exfiltration evidence, supply chain analysis).
- Executive Risk Summary for a business audience.
- Reproduction Steps for all findings.
- Attack output files (JSON results produced by running the scripts).
