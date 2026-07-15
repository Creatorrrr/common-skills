from __future__ import annotations

REQUIRED_OUTPUT_SECTIONS = [
    "Verdict",
    "Scope and coverage",
    "Prioritized findings",
    "Unknowns and missing context",
    "Recommended actions",
]

FINDING_FIELDS = [
    "severity",
    "confidence",
    "claim",
    "evidence",
    "impact",
    "recommendation",
    "validation",
]


def render_required_output_sections() -> str:
    return "\n".join(f"{index}. {name}" for index, name in enumerate(REQUIRED_OUTPUT_SECTIONS, start=1))


def render_finding_contract() -> str:
    return ", ".join(FINDING_FIELDS)
