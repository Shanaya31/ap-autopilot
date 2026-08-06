"""
Invoice anomaly skill.

This module is intentionally a thin read-only wrapper.

All anomaly detection and decision rules are implemented in Snowflake SQL,
primarily in:

- INVOICE_ANOMALY_RESULTS
- AP_REVIEW_QUEUE

This Python module only retrieves the precomputed results. It does not
recalculate duplicate detection, price drift, quantity mismatches, severity,
or recommended actions.
"""

import json
import sys
from typing import Any

from snowflake_client import query


def _normalise_invoice_id(invoice_id: str) -> str:
    """
    Validate and normalise an invoice ID.
    """
    if not isinstance(invoice_id, str) or not invoice_id.strip():
        raise ValueError("Invoice ID cannot be empty.")

    return invoice_id.strip().upper()


def get_invoice_anomalies(invoice_id: str) -> list[dict[str, Any]]:
    """
    Return all anomaly records for one invoice.

    An empty list means that no anomaly record was found.
    """
    normalised_id = _normalise_invoice_id(invoice_id)

    sql = """
        SELECT *
        FROM INVOICE_ANOMALY_RESULTS
        WHERE INVOICE_ID = %(invoice_id)s
    """

    return query(sql, {"invoice_id": normalised_id})


def get_review_queue_entry(invoice_id: str) -> dict[str, Any] | None:
    """
    Return the AP review-queue entry for one invoice.

    Returns None when the invoice is not currently present in
    AP_REVIEW_QUEUE.
    """
    normalised_id = _normalise_invoice_id(invoice_id)

    sql = """
        SELECT *
        FROM AP_REVIEW_QUEUE
        WHERE INVOICE_ID = %(invoice_id)s
    """

    rows = query(sql, {"invoice_id": normalised_id})
    return rows[0] if rows else None


def get_all_review_queue_entries() -> list[dict[str, Any]]:
    """
    Return every invoice currently present in AP_REVIEW_QUEUE.
    """
    sql = """
        SELECT *
        FROM AP_REVIEW_QUEUE
        ORDER BY INVOICE_ID
    """

    return query(sql)


def get_all_open_invoices() -> list[dict[str, Any]]:
    """
    Backward-compatible alias used by cli.py.

    This currently returns invoices from AP_REVIEW_QUEUE.
    """
    return get_all_review_queue_entries()


def main() -> None:
    """
    Run a small command-line test for a single invoice.
    """
    if len(sys.argv) != 2:
        print(
            "Usage:\n"
            "  python invoice_anomaly_skill.py <INVOICE_ID>\n\n"
            "Example:\n"
            "  python invoice_anomaly_skill.py INV0001"
        )
        raise SystemExit(1)

    invoice_id = sys.argv[1]

    try:
        anomaly_rows = get_invoice_anomalies(invoice_id)
        review_entry = get_review_queue_entry(invoice_id)

        output = {
            "invoice_id": invoice_id.strip().upper(),
            "anomalies": anomaly_rows,
            "review_queue_entry": review_entry,
        }

        print(json.dumps(output, indent=2, default=str))

    except ValueError as exc:
        print(f"Input error: {exc}")
        raise SystemExit(1)

    except Exception as exc:
        print("Failed to retrieve invoice anomaly data.")
        print(exc)
        raise SystemExit(1)


if __name__ == "__main__":
    main()