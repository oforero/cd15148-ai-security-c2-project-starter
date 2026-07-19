# Supply Chain Vulnerability Analysis

## Vulnerability Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 34 |
| MEDIUM | 160 |
| LOW | 601 |
| **Total** | **804** |

The scan (`06_trivy_report.json`) covers two targets: the Debian 13.4 base image (801 vulnerabilities) and the bundled Python packages (3 vulnerabilities). A further 9 findings are UNKNOWN severity, included in the 804 total. There are no CRITICAL findings, but 34 HIGH severity issues warrant attention.

## High Severity Findings

Of the 34 HIGH severity CVEs, only **3 have a fix available**, and all three are in Python packages. The remaining 31 are Debian OS package vulnerabilities (for example `libexpat1` 2.7.1-2, CVE-2026-25210) with no fixed version published yet, so they can only be addressed by rebuilding on an updated base image when upstream ships patches.

| CVE | Package | Installed | Fixed Version | Notes |
|-----|---------|-----------|---------------|-------|
| CVE-2026-23949 | jaraco.context | 5.3.0 | 6.1.0 | Python packaging dependency |
| CVE-2026-24049 | wheel | 0.45.1 | 0.46.2 | Python build/packaging tool |
| (31 others) | Debian OS packages | various | none available | Fixable only via base image update |

## Python-Specific Vulnerabilities

All 3 Python-package findings are HIGH severity and, unlike the OS packages, all have fixes:

- `jaraco.context` 5.3.0, fixed in 6.1.0 (CVE-2026-23949)
- `wheel` 0.45.1, fixed in 0.46.2 (CVE-2026-24049)

Both are packaging/build-time dependencies rather than runtime libraries, which points to a multi-stage build (below) as the cleanest fix: they need not ship in the final image at all.

## Dockerfile Issues

Six issues were identified. Each is listed with its risk and a specific fix.

### 1. Container runs as root [HIGH]

**Risk:** There is no `USER` directive, so the app runs as root (UID 0). If the RAG service is compromised through a dependency, the attacker gets root inside the container, widening blast radius and easing container escape.
**Fix:** Add a non-root user and switch to it before `CMD`, e.g. `RUN useradd -m appuser` then `USER appuser`.

### 2. Base image pinned to a mutable tag [MEDIUM]

**Risk:** `FROM python:3.11-slim` uses a mutable tag. The image behind the tag can change, so builds are not reproducible and a poisoned upstream tag would be pulled silently.
**Fix:** Pin the base image by digest, e.g. `FROM python:3.11-slim@sha256:<digest>`, and update it deliberately.

### 3. COPY . copies the entire build context [MEDIUM]

**Risk:** `COPY . /app` pulls everything in the build context into the image, which can include `.env` (the OpenAI API key), `.git` history, and the confidential policy documents, all readable by anyone who pulls the image.
**Fix:** Copy only the paths the app needs and add a `.dockerignore` excluding `.env`, `.git`, `results/`, and data caches.

### 4. Build tools shipped in production [MEDIUM]

**Risk:** `build-essential` and `gcc` remain in the final image, enlarging the attack surface and giving an attacker who lands in the container the means to compile further tooling.
**Fix:** Use a multi-stage build: compile in a builder stage and copy only runtime artifacts into a clean final image.

### 5. No HEALTHCHECK defined [LOW]

**Risk:** Without a `HEALTHCHECK`, the orchestrator cannot distinguish a hung or degraded container from a healthy one, so a crashed or compromised process can keep serving traffic.
**Fix:** Add a `HEALTHCHECK` that probes the `/health` endpoint on port 5001.

### 6. Unnecessary tools in production [LOW]

**Risk:** `curl` and `git` are present in the runtime image. Both are useful to an attacker for pulling payloads or exfiltrating data and are not needed by the app at runtime.
**Fix:** Remove `curl` and `git` from the final image, or install them only in a build stage.

## AI Pipeline Risk Assessment

These supply chain issues compound the AI-specific risks found in the other attacks:

- **Runtime privileges and secret exposure.** The container runs as root and `COPY .` bakes the whole project into the image. That image therefore carries the OpenAI API key (`.env`) and the confidential policy documents. A single container compromise exposes exactly the confidential data that Attack 4 already showed is reachable through the RAG retriever, plus the API credentials.
- **Dependency integrity.** The classifier and the RAG chatbot both execute inside this image. A compromised or trojanized dependency (unpinned base image, HIGH CVEs) could tamper with model loading, the FAISS index, or the inference path, undermining model integrity without touching the model files directly.
- **Unpatchable OS surface.** 31 of the 34 HIGH CVEs have no fix, so the base image is the dominant source of standing risk and must be tracked and rebuilt on a cadence, not treated as a one-time fix.

## Remediation Priority

| Priority | Action |
|----------|--------|
| 1 | Stop running as root (add a non-root `USER`) and stop shipping secrets: replace `COPY .` with specific paths plus a `.dockerignore` that excludes `.env`, `.git`, and the confidential policy data. |
| 2 | Rebuild on an updated `python:3.11-slim` base image and patch the 3 fixable HIGH Python CVEs (`jaraco.context` to 6.1.0, `wheel` to 0.46.2); move build tools into a multi-stage builder so they do not ship in production. |
| 3 | Pin the base image by digest, add a `HEALTHCHECK`, and remove `curl`/`git` from the runtime image; establish a recurring rescan-and-rebuild cadence for the unpatchable OS CVEs. |
