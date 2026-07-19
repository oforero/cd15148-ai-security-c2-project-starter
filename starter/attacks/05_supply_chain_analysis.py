"""
Supply Chain Vulnerability Analysis.

Parses a Trivy JSON report and analyzes a Dockerfile for security issues.
Produces a structured risk assessment of the AI system's deployment pipeline.

Usage:
    python 05_supply_chain_analysis.py
    python 05_supply_chain_analysis.py --trivy-report ../06_trivy_report.json --dockerfile ../Dockerfile
"""
import json
import argparse
import os
import re

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results", "05_supply_chain")


def parse_trivy_report(path):
    """
    Parse a Trivy JSON report and extract vulnerability details.

    The Trivy JSON format has a "Results" array, where each result has:
    - "Target": what was scanned (e.g., "debian 13.4" or "Python")
    - "Type": scan type (e.g., "debian", "python-pkg")
    - "Vulnerabilities": array of vulnerability objects

    Each vulnerability has: VulnerabilityID, Severity, PkgName,
    InstalledVersion, FixedVersion, Title, Description

    Args:
        path: Path to Trivy JSON report

    Returns:
        List of vulnerability dictionaries
    """
    with open(path) as f:
        data = json.load(f)

    vulns = []

    for result in data.get("Results", []):
        target = result.get("Target", "")
        target_type = result.get("Type", "")
        for v in result.get("Vulnerabilities") or []:
            description = v.get("Description", "") or ""
            vulns.append({
                "id": v.get("VulnerabilityID", ""),
                "severity": v.get("Severity", "UNKNOWN"),
                "package": v.get("PkgName", ""),
                "installed_version": v.get("InstalledVersion", ""),
                # FixedVersion is absent/None when no fix is published yet.
                "fixed_version": v.get("FixedVersion", "") or "",
                "title": v.get("Title", ""),
                "description": description[:200],
                "target": target,
                "target_type": target_type,
            })

    return vulns


def analyze_dockerfile(path):
    """
    Analyze a Dockerfile for common security issues.

    Check for:
    1. Running as root (no USER directive) — HIGH
    2. Unpinned base image (no SHA256 digest) — MEDIUM
    3. COPY . (copies entire context including secrets) — MEDIUM
    4. No HEALTHCHECK — LOW
    5. Build tools left in production image — MEDIUM
    6. Unnecessary tools (curl, git) in production — LOW

    Args:
        path: Path to Dockerfile

    Returns:
        List of issue dictionaries with: issue, severity, detail, recommendation
    """
    with open(path) as f:
        content = f.read()
    lines = content.strip().split("\n")

    issues = []
    stripped = [line.strip() for line in lines]

    def has_directive(name):
        return any(line.upper().startswith(name + " ") for line in stripped)

    # 1. Running as root (no USER directive) -- HIGH
    if not has_directive("USER"):
        issues.append({
            "issue": "Container runs as root (no USER directive)",
            "severity": "HIGH",
            "detail": (
                "With no USER directive the process runs as root (UID 0). If the app is "
                "compromised (for example via RCE in a dependency), the attacker has root "
                "inside the container, which widens blast radius and eases container escape."
            ),
            "recommendation": (
                "Add a non-root user and switch to it before CMD, e.g. "
                "'RUN useradd -m appuser' then 'USER appuser'."
            ),
        })

    # 2. Unpinned base image (no SHA256 digest) -- MEDIUM
    from_lines = [line for line in stripped if line.upper().startswith("FROM ")]
    if from_lines and not any("@sha256:" in line for line in from_lines):
        issues.append({
            "issue": "Base image pinned to a mutable tag, not a digest",
            "severity": "MEDIUM",
            "detail": (
                "FROM python:3.11-slim references a mutable tag. The image behind the tag can "
                "change, so builds are not reproducible and a poisoned or trojanized upstream "
                "tag would be pulled silently."
            ),
            "recommendation": (
                "Pin the base image by digest, e.g. FROM python:3.11-slim@sha256:<digest>, and "
                "update it deliberately."
            ),
        })

    # 3. COPY . copies the whole build context -- MEDIUM
    for tokens in (line.split() for line in stripped):
        if len(tokens) >= 2 and tokens[0].upper() == "COPY" and tokens[1] == ".":
            issues.append({
                "issue": "COPY . copies the entire build context into the image",
                "severity": "MEDIUM",
                "detail": (
                    "COPY . /app pulls everything in the build context into the image, which can "
                    "include secrets (.env), .git history, local credentials, and test data, all "
                    "readable by anyone who pulls the image."
                ),
                "recommendation": (
                    "Copy only the paths the app needs and add a .dockerignore excluding .env, "
                    ".git, results/, and data caches."
                ),
            })
            break

    # 4. No HEALTHCHECK -- LOW
    if not has_directive("HEALTHCHECK"):
        issues.append({
            "issue": "No HEALTHCHECK defined",
            "severity": "LOW",
            "detail": (
                "Without a HEALTHCHECK the orchestrator cannot tell a hung or degraded container "
                "from a healthy one, so a compromised or crashed process can keep serving traffic."
            ),
            "recommendation": (
                "Add a HEALTHCHECK that probes the app, e.g. curl the /health endpoint on port 5001."
            ),
        })

    # 5. Build tools left in the production image -- MEDIUM
    build_tools = [t for t in ("build-essential", "gcc", "g++", "make") if re.search(rf"\b{re.escape(t)}\b", content)]
    if build_tools:
        issues.append({
            "issue": f"Build tools shipped in production image ({', '.join(build_tools)})",
            "severity": "MEDIUM",
            "detail": (
                "Compilers and build tooling remain in the final image. They enlarge the attack "
                "surface and give an attacker who lands in the container the means to build and "
                "run further tooling."
            ),
            "recommendation": (
                "Use a multi-stage build: compile in a builder stage and copy only the runtime "
                "artifacts into a clean final image with no build tools."
            ),
        })

    # 6. Unnecessary tools (curl, git) in production -- LOW
    extra_tools = [t for t in ("curl", "git") if re.search(rf"\b{t}\b", content)]
    if extra_tools:
        issues.append({
            "issue": f"Unnecessary tools present in production image ({', '.join(extra_tools)})",
            "severity": "LOW",
            "detail": (
                "Tools such as curl and git are useful to an attacker for pulling payloads or "
                "exfiltrating data and are not needed at runtime by the app."
            ),
            "recommendation": (
                "Remove curl and git from the final image, or install them only in a build stage."
            ),
        })

    return issues


def generate_report(vulns, dockerfile_issues):
    """Generate a structured supply chain risk report."""
    # TODO: Generate a report dictionary with:
    # - "summary": total vulnerabilities, severity breakdown, dockerfile issue count
    # - "high_severity_vulnerabilities": list of HIGH severity CVEs (top 15)
    # - "python_specific": vulnerabilities in Python packages
    # - "dockerfile_issues": from analyze_dockerfile()
    # - "risk_assessment": overall risk level and key concerns

    severity_counts = {}
    for v in vulns:
        sev = v.get("severity", "UNKNOWN")
        severity_counts[sev] = severity_counts.get(sev, 0) + 1

    high_vulns = [v for v in vulns if v.get("severity") == "HIGH"]
    # Surface HIGH CVEs that actually have a fix first: those are the actionable ones.
    high_vulns_sorted = sorted(high_vulns, key=lambda v: (v.get("fixed_version", "") == "",))
    python_vulns = [v for v in vulns if v.get("target_type") == "python-pkg"]
    high_fixable = [v for v in high_vulns if v.get("fixed_version")]

    # Overall risk: CRITICAL if any CRITICAL CVE, else HIGH if there are HIGH CVEs
    # or a HIGH Dockerfile issue, else MEDIUM/LOW.
    dockerfile_high = any(i["severity"] == "HIGH" for i in dockerfile_issues)
    if severity_counts.get("CRITICAL"):
        overall_risk = "CRITICAL"
    elif severity_counts.get("HIGH") or dockerfile_high:
        overall_risk = "HIGH"
    elif severity_counts.get("MEDIUM"):
        overall_risk = "MEDIUM"
    else:
        overall_risk = "LOW"

    key_concerns = []
    if severity_counts.get("HIGH"):
        key_concerns.append(
            f"{severity_counts['HIGH']} HIGH severity CVEs in the base image and packages "
            f"({len(high_fixable)} have a fix available)."
        )
    if dockerfile_high:
        key_concerns.append("Container runs as root, so any code execution becomes root in the container.")
    if python_vulns:
        key_concerns.append(f"{len(python_vulns)} vulnerabilities in bundled Python packages.")
    if any(i["issue"].startswith("COPY .") for i in dockerfile_issues):
        key_concerns.append("COPY . risks baking secrets and source history into the shipped image.")

    # Prioritized remediation plan: Dockerfile issues ordered by severity, then
    # the fixable HIGH CVEs as a patch batch.
    severity_rank = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    remediation_plan = []
    for i in sorted(dockerfile_issues, key=lambda x: severity_rank.get(x["severity"], 3)):
        remediation_plan.append({
            "priority": i["severity"],
            "area": "Dockerfile",
            "action": i["recommendation"],
        })
    if high_fixable:
        remediation_plan.append({
            "priority": "HIGH",
            "area": "Dependencies",
            "action": (
                f"Patch the {len(high_fixable)} HIGH CVEs that have fixed versions by rebuilding "
                "on an updated base image and upgrading the affected packages."
            ),
        })

    report = {
        "summary": {
            "total_vulnerabilities": len(vulns),
            "severity_breakdown": severity_counts,
            "dockerfile_issues": len(dockerfile_issues),
        },
        "high_severity_vulnerabilities": high_vulns_sorted[:15],
        "python_specific": python_vulns,
        "dockerfile_issues": dockerfile_issues,
        "risk_assessment": {
            "overall_risk": overall_risk,
            "key_concerns": key_concerns,
        },
        "prioritized_remediation": remediation_plan,
    }
    return report


def main():
    parser = argparse.ArgumentParser(description="Supply Chain Vulnerability Analysis")
    parser.add_argument(
        "--trivy-report",
        default=os.path.join(os.path.dirname(__file__), "..", "06_trivy_report.json"),
    )
    parser.add_argument(
        "--dockerfile",
        default=os.path.join(os.path.dirname(__file__), "..", "Dockerfile"),
    )
    parser.add_argument(
        "--output",
        default=os.path.join(RESULTS_DIR, "supply_chain_report.json"),
    )
    args = parser.parse_args()
    if not os.path.dirname(args.output):
        args.output = os.path.join(RESULTS_DIR, args.output)
    os.makedirs(os.path.dirname(args.output), exist_ok=True)

    print("Parsing Trivy report...")
    vulns = parse_trivy_report(args.trivy_report)

    print("Analyzing Dockerfile...")
    dockerfile_issues = analyze_dockerfile(args.dockerfile)

    report = generate_report(vulns, dockerfile_issues)

    # Print summary
    print("\n**SUPPLY CHAIN RISK ASSESSMENT**")
    s = report["summary"]
    print(f"  Overall risk: {report['risk_assessment']['overall_risk']}")
    print(f"  Total vulnerabilities: {s['total_vulnerabilities']}")
    for sev in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
        count = s["severity_breakdown"].get(sev, 0)
        if count:
            print(f"    {sev}: {count}")

    print(f"  Dockerfile issues: {s['dockerfile_issues']}")

    with open(args.output, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\nFull report saved to {args.output}")


if __name__ == "__main__":
    main()
