"""Small, explicit capability registry; unknown models fail closed, never guessed.
Official documentation checked 2026-09-05; see references/model-profiles.md.
"""
from __future__ import annotations
from typing import Any

PROFILES = {
    "gpt-5.6-sol": {"family": "gpt-5.6", "context_window": 1_050_000,
                    "max_output_tokens": 128_000, "efforts": ["none", "low", "medium", "high", "xhigh", "max"],
                    "reasoning_modes": ["standard", "pro"], "default_mode": "pro",
                    "contexts": ["auto", "current_turn", "all_turns"]},
    "gpt-6-astra": {"family": "gpt-6-astra", "context_window": 1_050_000,
                    "max_output_tokens": 128_000, "efforts": ["low", "medium", "high", "xhigh", "max"],
                    "reasoning_modes": [], "default_mode": "native", "contexts": ["auto"]},
}
ALIASES = {"gpt-5.6": "gpt-5.6-sol"}


def profile_for(model: str) -> dict[str, Any]:
    key = ALIASES.get(model, model)
    if key not in PROFILES:
        raise ValueError(f"Unverified model {model!r}. Add a documentation-backed profile and tests; no automatic model substitution.")
    return PROFILES[key]


def reasoning_config(model: str, mode: str, effort: str, context: str = "auto") -> dict[str, str]:
    profile = profile_for(model)
    if effort not in profile["efforts"]:
        raise ValueError(f"{model} does not support reasoning effort {effort!r}.")
    effective = profile["default_mode"] if mode == "auto" else mode
    result = {"effort": effort}
    if profile["reasoning_modes"]:
        if effective not in profile["reasoning_modes"]:
            raise ValueError(f"Unsupported reasoning mode {effective!r} for {model}.")
        if effective == "pro" and effort in {"none", "low"}:
            raise ValueError("GPT-5.6 Pro mode requires reasoning effort medium or higher.")
        result["mode"] = effective
    elif effective not in {"native", "standard"}:
        raise ValueError(f"{model} has no verified reasoning.mode={effective!r}; use --reasoning-mode auto.")
    if context not in profile["contexts"]:
        raise ValueError(f"Unverified reasoning.context={context!r} for {model}; use auto.")
    if context != "auto":
        result["context"] = context
    return result


def enforce_token_budget(model: str, input_tokens: int, max_output_tokens: int, safety_margin: int = 8192) -> dict[str, int]:
    p = profile_for(model)
    if isinstance(input_tokens, bool) or not isinstance(input_tokens, int) or input_tokens < 0:
        raise ValueError("A valid input token count is required; refuse submission when counting fails.")
    if not 1 <= max_output_tokens <= p["max_output_tokens"] or safety_margin < 0:
        raise ValueError("Invalid output token budget or safety margin.")
    total = input_tokens + max_output_tokens + safety_margin
    if total > p["context_window"]:
        raise ValueError(f"Token budget exceeded: input {input_tokens} + output/reasoning {max_output_tokens} + margin {safety_margin} > {p['context_window']}. No truncation or automatic fallback.")
    return {"input_tokens": input_tokens, "max_output_tokens": max_output_tokens,
            "safety_margin": safety_margin, "context_window": p["context_window"], "reserved_total": total}
