"""
Controlled test for the missing-contract fail-safe.

This test does not modify Snowflake data. It temporarily replaces the
decision skill's data-retrieval functions with predictable test values.
"""

from unittest.mock import patch

from decision_skill import decide


def test_missing_contract_analysis() -> None:
    fake_review_entry = {
        "INVOICE_ID": "INV_TEST",
        "VENDOR_ID": "V_TEST",
        "SEVERITY": "LOW",
        "RECOMMENDED_ACTION": "AUTO APPROVE",
    }

    with (
        patch(
            "decision_skill.get_invoice_anomalies",
            return_value=[],
        ),
        patch(
            "decision_skill.get_review_queue_entry",
            return_value=fake_review_entry,
        ),
        patch(
            "decision_skill.get_contract_analysis",
            return_value=None,
        ),
        patch(
            "decision_skill.get_contract_status",
            return_value=None,
        ),
        patch(
            "decision_skill.get_price_check",
            return_value=[],
        ),
    ):
        result = decide("INV_TEST", "V_TEST")

    assert result["decision"] == "ESCALATE"
    assert result["severity"] == "HIGH"
    assert result["decision_source"] == "PYTHON_FAIL_SAFE"
    assert (
        result["reasoning_facts"]["no_contract_analysis_on_file"]
        is True
    )

    print("Missing-contract fail-safe test passed.")
    print(f"Decision: {result['decision']}")
    print(f"Severity: {result['severity']}")
    print(f"Source:   {result['decision_source']}")


if __name__ == "__main__":
    test_missing_contract_analysis()