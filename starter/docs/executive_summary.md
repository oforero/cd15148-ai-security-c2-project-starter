# Executive Risk Summary

## Overview

FinanceGuard authorized a red team assessment of the two AI systems now in the expense workflow: the receipt classifier that decides whether an uploaded image is a valid receipt, and the expense-policy chatbot that answers reimbursement questions. Across five tested attacks, the most serious problem is that confidential executive compensation data is fully retrievable by any employee through the ordinary chatbot, and the way the system is packaged for deployment makes that same data easy to expose again if a single component is compromised. All five tested attacks were demonstrated to some degree, and all are correctable with focused, mostly low-effort changes. This summary rates each by real-world impact and how much access an attacker needs, so leadership can prioritize accordingly.

## Risk Dashboard

| System | Risk Level | Key Finding |
|--------|-----------|-------------|
| Receipt Classifier | [MEDIUM] | An attacker with access to the model can alter receipt images invisibly to flip its decisions, and an attacker with access to the training data can corrupt a small share of labels to degrade its accuracy. |
| RAG Chatbot | [HIGH] | Any employee can retrieve the confidential executive bonus and salary document through normal questions; the chatbot has no concept of who is allowed to see what. |
| Deployment Infrastructure | [HIGH] | The application runs with maximum privileges and ships with secrets and confidential documents baked into its image, alongside 34 high-severity known software vulnerabilities. |

## Findings Summary

### 1. Confidential Compensation Data Is Openly Retrievable — [HIGH]

Every one of six differently worded questions caused the chatbot to pull the confidential executive compensation document (CEO, C-suite, and VP salary ranges, bonus tiers, and stock option details) into its working memory, and most of those questions caused it to read that data back to the user. The chatbot has no notion of authorization: it searches all documents by topic similarity, so any question close in meaning to the confidential content surfaces it, even questions worded in plain business language with no sensitive keywords.

**Business Impact:** Salary and bonus information for the most senior executives is exposed to any employee who can use the chatbot. This is a serious confidentiality breach with direct legal, regulatory, and morale consequences, and because retrieval is by meaning rather than keywords, simple word filters would not stop it.

### 2. Deployment Package Exposes Secrets and Runs With Full Privileges — [HIGH]

The way the system is built for deployment copies the entire project into the shipped image, including the software's login key for its AI provider and the confidential policy documents, and runs everything with administrator-level rights. A security scan of the image also found 34 high-severity known vulnerabilities, most in the underlying operating system.

**Business Impact:** Anyone who obtains the deployment image obtains the AI provider credentials and the confidential documents directly, without needing to attack the running system at all. If any single component is breached, the maximum-privilege setup lets that breach spread further and faster. This finding amplifies Finding 1: the same confidential data is exposed through a second, independent channel.

### 3. Chatbot Behavior Can Be Steered by Crafted Input — [MEDIUM]

Of five manipulation techniques tested, one succeeded: a request disguised as a harmless interface test made the chatbot abandon its normal instructions and answer in an attacker-chosen style. The others (demands to reveal its instructions, to ignore its rules, or to accept a fake policy) were refused. The content exposed in the successful case was harmless, but it proved the channel exists.

**Business Impact:** A determined attacker can use innocent-looking framing to make the chatbot depart from approved behavior, for example to suppress required caveats or to produce misleading, official-looking wording that could be used in a phishing or misinformation attempt against staff.

### 4. Receipt Images Can Be Altered to Fool the Classifier — [MEDIUM]

With access to the classifier, an attacker can add a small amount of calculated noise to a receipt image, invisible to a human reviewer at low levels, that reliably changes the model's decision. In testing, an imperceptible change cut the model's accuracy roughly in half, and stronger changes broke about 70% of the decisions it originally got right.

**Business Impact:** A manipulated image could be pushed through as a valid receipt, or a genuine receipt forced to be rejected, without a reviewer noticing anything wrong. This becomes a fraud risk wherever the model's decision drives an automated reimbursement without a second check. It requires the attacker to have access to the model, which limits, but does not eliminate, the exposure.

### 5. Training Data Can Be Poisoned to Degrade the Classifier — [MEDIUM]

By corrupting about 10% of the classifier's training labels, chosen with help from the model itself to hit the examples it is most sure about, we reduced the retrained model's accuracy by roughly 6 points and its ability to recognize genuine receipts by more than 8 points. The result was reproducible run to run. The attack changes only training labels, so the resulting model looks untampered; the damage is baked into what it learned. The training pipeline has no checks on label integrity and no controlled, repeatable baseline to detect this.

**Business Impact:** A poisoned model would silently reject a materially larger share of legitimate receipts, pushing valid reimbursements into wrongful rejection or extra manual review, with no obvious sign that the model was tampered with. The exposure grows as the model is retrained over time on larger or less trusted data. It requires access to the training data, which points to insider risk and pipeline access controls.

## Prioritized Remediation

| Priority | Action | Effort | Impact |
|----------|--------|--------|--------|
| 1 | Remove the confidential compensation document from the chatbot's knowledge base and rebuild it from public policy documents only. | Low | High |
| 2 | Run the deployment as a non-privileged user and stop packaging secrets and confidential files into the shipped image. | Low to Medium | High |
| 3 | Add authorization at the point of document retrieval so the chatbot can only reach documents the requester is entitled to see, and refuse when a restricted document is retrieved. | Medium to High | High |
| 4 | Patch the fixable dependency vulnerabilities, rebuild on an updated and version-locked base image, and set a recurring rescan-and-rebuild schedule for the rest. | Medium | Medium |
| 5 | Add label-integrity checks and access controls to the training pipeline, and make training runs repeatable so tampering would be detectable. | Medium | Medium |

## Conclusion

The headline risk is confidentiality: the most sensitive compensation data in the company is currently reachable by any employee through the chatbot, and through the deployment package as well. The two highest-priority fixes are inexpensive and address that directly, and they should be done before this system is exposed to a wider internal audience. The chatbot-behavior, image-tampering, and training-poisoning findings are real but lower priority than the confidentiality exposure and can be handled on the normal engineering roadmap; all three require privileged access (to the model, or to the training data) to exploit. Overall the systems are salvageable without redesign, provided access control is added at the retrieval layer rather than left to the chatbot's wording.
