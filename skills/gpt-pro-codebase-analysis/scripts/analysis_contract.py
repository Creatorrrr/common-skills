from __future__ import annotations

REQUIRED_OUTPUT_SECTIONS = [
    "Scope and assumptions",
    "Short system map",
    "Top findings (prioritized)",
    "Evidence for each finding",
    "Confirmed facts vs inference",
    "Test-gap recommendations",
    "Refactoring or redesign recommendations",
    "Quick wins vs deeper changes",
    "Suggested next design steps",
]


def render_required_output_sections() -> str:
    return "\n".join(f"{index}. {name}" for index, name in enumerate(REQUIRED_OUTPUT_SECTIONS, start=1))
