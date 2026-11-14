from __future__ import annotations

from soiltrust.models import QualityIssue


def deterministic_explanation(status: str, score: int, issues: list[QualityIssue]) -> str:
    critical = [i.message for i in issues if i.severity == "critical"]
    warnings = [i.message for i in issues if i.severity == "warning"]

    if status == "ABSTAIN":
        reason = critical[0] if critical else "Evidence is insufficient."
        return (
            f"SoilTrust abstains from a field-level recommendation (reliability score {score}/100). "
            f"Primary reason: {reason} The system may still display source data and limitations, "
            "but it will not convert them into an agronomic instruction."
        )
    if status == "CAUTION":
        reason = warnings[0] if warnings else "One or more limitations require review."
        return (
            f"SoilTrust reports CAUTION (reliability score {score}/100). {reason} "
            "Use the result as contextual evidence, not as field-level ground truth."
        )
    return (
        f"SoilTrust reports PASS for the current deterministic checks (reliability score {score}/100). "
        "PASS means no implemented rule blocked the evidence; it is not proof of agronomic correctness."
    )
