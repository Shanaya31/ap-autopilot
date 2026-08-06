"""
Gemini reasoner.

This module converts a completed AP decision into a concise business memo.

It NEVER performs risk assessment.
It NEVER changes the decision.
It NEVER changes the severity.

Snowflake SQL is the primary source of truth.
The Python decision skill applies explicit safety overrides.
Gemini only explains the completed decision.
"""

import json
import os
import time
from typing import Any

from dotenv import load_dotenv
from google import genai


# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------

load_dotenv()

MODEL_NAME = os.getenv(
    "GEMINI_MODEL",
    "gemini-2.5-flash",
)

MAX_RETRIES = int(
    os.getenv(
        "GEMINI_MAX_RETRIES",
        "3",
    )
)

INITIAL_RETRY_DELAY_SECONDS = float(
    os.getenv(
        "GEMINI_RETRY_DELAY_SECONDS",
        "2",
    )
)

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise RuntimeError(
        "GEMINI_API_KEY was not found.\n"
        "Add it to the project-root .env file."
    )

client = genai.Client(api_key=api_key)


# ---------------------------------------------------------------------
# Error helpers
# ---------------------------------------------------------------------

def _is_temporary_service_error(error: Exception) -> bool:
    """
    Return True for temporary Gemini service failures worth retrying.

    Typical examples:
    - HTTP 503
    - UNAVAILABLE
    - temporarily overloaded
    - high demand
    """
    error_text = str(error).lower()

    temporary_markers = (
        "503",
        "unavailable",
        "high demand",
        "temporarily unavailable",
        "service unavailable",
        "internal server error",
        "500",
    )

    return any(
        marker in error_text
        for marker in temporary_markers
    )


def _is_quota_exhausted(error: Exception) -> bool:
    """
    Return True when retrying is unlikely to help.

    This includes daily or project-level free-tier quota exhaustion.
    """
    error_text = str(error).lower()

    quota_markers = (
        "generate_content_free_tier_requests",
        "requestsperday",
        "perday",
        "daily quota",
        "quota exceeded",
        "resource_exhausted",
    )

    return any(
        marker in error_text
        for marker in quota_markers
    )


def _fallback_memo(error: Exception) -> str:
    """
    Return a concise fallback without exposing raw API internals.
    """
    if _is_quota_exhausted(error):
        reason = (
            "the Gemini API quota has been reached"
        )

    elif _is_temporary_service_error(error):
        reason = (
            "the Gemini service is temporarily busy"
        )

    else:
        reason = (
            "the explanation service is currently unavailable"
        )

    return (
        f"AI explanation unavailable because {reason}. "
        "The deterministic AP decision remains valid and was still "
        "recorded using the Snowflake evidence and Python decision layer."
    )


# ---------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------

def _build_prompt(
    decision_result: dict[str, Any],
) -> str:
    """
    Build a grounded prompt from an already-completed decision.
    """
    decision_package = json.dumps(
        decision_result,
        indent=2,
        default=str,
    )

    return f"""
You are writing a short internal Accounts Payable review memo.

The financial decision has already been completed by a deterministic
Snowflake SQL rules engine and, where necessary, an explicit Python
fail-safe layer.

STRICT RULES

- Do not change the final decision.
- Do not recommend another action.
- Do not change the severity.
- Do not invent facts, dates, amounts, clauses, or percentages.
- Use only evidence contained in the supplied JSON.
- Do not mention Gemini, artificial intelligence, prompts, or JSON.
- Treat the final "decision" field as authoritative.
- The "sql_decision" field represents Snowflake's original result.
- The "decision_source" field identifies who produced the final decision.
- When SQL and the final decision differ, explain that a safety check
  escalated the invoice without criticising or second-guessing either layer.

DECISION PACKAGE

{decision_package}

Write a concise internal memo of 3 to 5 sentences.

Include, when available:

- the invoice ID and vendor;
- the final decision and the principal reason;
- specific price variance, amount, contract date, or contract status;
- whether an expired or missing contract triggered a fail-safe;
- whether the contract and purchase-order prices matched.

Do not use bullet points.
Do not add a heading or preamble.
Return only the memo text.
""".strip()


# ---------------------------------------------------------------------
# Gemini generation
# ---------------------------------------------------------------------

def explain_decision(
    decision_result: dict[str, Any],
) -> str:
    """
    Generate a business-friendly explanation for a completed AP decision.

    Temporary Gemini service failures are retried with exponential backoff.
    Quota exhaustion returns a concise fallback immediately.
    """
    if not isinstance(decision_result, dict):
        raise TypeError(
            "decision_result must be a dictionary."
        )

    required_fields = (
        "invoice_id",
        "vendor_id",
        "decision",
        "severity",
    )

    missing_fields = [
        field
        for field in required_fields
        if field not in decision_result
    ]

    if missing_fields:
        raise ValueError(
            "Decision result is missing required fields: "
            + ", ".join(missing_fields)
        )

    prompt = _build_prompt(decision_result)

    last_error: Exception | None = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt,
            )

            memo = getattr(
                response,
                "text",
                None,
            )

            if not memo or not memo.strip():
                raise ValueError(
                    "Gemini returned an empty explanation."
                )

            return memo.strip()

        except Exception as error:
            last_error = error

            # Daily or project quota exhaustion will not improve through
            # immediate retries.
            if _is_quota_exhausted(error):
                return _fallback_memo(error)

            should_retry = (
                _is_temporary_service_error(error)
                and attempt < MAX_RETRIES
            )

            if not should_retry:
                return _fallback_memo(error)

            delay_seconds = (
                INITIAL_RETRY_DELAY_SECONDS
                * (2 ** (attempt - 1))
            )

            print(
                f"Gemini is temporarily unavailable. "
                f"Retrying in {delay_seconds:.0f} seconds "
                f"({attempt}/{MAX_RETRIES})..."
            )

            time.sleep(delay_seconds)

    # Defensive fallback. The loop should normally return earlier.
    if last_error is not None:
        return _fallback_memo(last_error)

    return (
        "AI explanation is currently unavailable. "
        "The deterministic AP decision remains valid."
    )


# ---------------------------------------------------------------------
# Standalone smoke test
# ---------------------------------------------------------------------

def main() -> None:
    """
    Run a small standalone Gemini explanation test.
    """
    sample = {
        "invoice_id": "INV0007",
        "vendor_id": "V002",
        "sql_action": "MANUAL REVIEW",
        "sql_decision": "HOLD",
        "decision": "ESCALATE",
        "severity": "HIGH",
        "decision_source": "PYTHON_FAIL_SAFE",
        "reasoning_facts": {
            "contract_expired": True,
            "contract_end": "2026-05-08",
            "message": (
                "The vendor contract is expired and requires "
                "manual review."
            ),
        },
        "evidence": {
            "price_check": [
                {
                    "PO_ID": "PO0003",
                    "PO_PRICE": "141.38",
                    "CONTRACT_UNIT_PRICE": "141.38",
                    "DIFFERENCE_PERCENT": "0.00",
                    "PRICE_MISMATCH": False,
                }
            ]
        },
    }

    print(explain_decision(sample))


if __name__ == "__main__":
    main()