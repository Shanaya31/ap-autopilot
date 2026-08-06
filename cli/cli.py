"""
cli.py -- AP Autopilot orchestration layer.

Commands:
    python cli.py review-invoice INV0007
    python cli.py scan-open-invoices
    python cli.py inspect-contract V003

Each command:

1. Retrieves deterministic evidence from Snowflake.
2. Uses decision_skill.py to assemble the final decision.
3. Uses Gemini only to explain the completed decision.
4. Writes the decision and evidence to AUDIT_LOG.
5. Prints a readable console report.
"""

import json
import sys
import uuid
from datetime import datetime, timezone
from typing import Any

from contract_clause_skill import (
    get_contract_analysis,
    get_contract_status,
    get_price_check,
)
from decision_skill import decide
from gemini_reasoner import explain_decision
from invoice_anomaly_skill import get_all_open_invoices
from snowflake_client import execute, query


# ---------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------

def normalise_identifier(value: str, label: str) -> str:
    """
    Validate and normalise an invoice or vendor identifier.
    """
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} cannot be empty.")

    return value.strip().upper()


# ---------------------------------------------------------------------
# Snowflake lookup helpers
# ---------------------------------------------------------------------

def get_vendor_id_for_invoice(invoice_id: str) -> str:
    """
    Return the vendor ID associated with an invoice.
    """
    normalised_invoice_id = normalise_identifier(
        invoice_id,
        "Invoice ID",
    )

    rows = query(
        """
        SELECT VENDOR_ID
        FROM INVOICES
        WHERE INVOICE_ID = %(invoice_id)s
        """,
        {
            "invoice_id": normalised_invoice_id,
        },
    )

    if not rows:
        raise ValueError(
            f"No invoice found with ID {normalised_invoice_id}."
        )

    return str(rows[0]["VENDOR_ID"]).strip().upper()


# ---------------------------------------------------------------------
# Decision helpers
# ---------------------------------------------------------------------

def _normalise_decision_bucket(decision: str) -> str:
    """
    Convert different decision labels into stable batch-summary buckets.

    Snowflake may return business-friendly values such as:

    - AUTO APPROVE
    - MANUAL REVIEW
    - ESCALATE

    Older code may still return:

    - APPROVE
    - HOLD
    - ESCALATE
    """
    value = str(decision or "").strip().upper().replace("_", " ")

    if value in {
        "APPROVE",
        "AUTO APPROVE",
        "AUTO-APPROVE",
    }:
        return "AUTO_APPROVE"

    if value in {
        "HOLD",
        "MANUAL REVIEW",
        "REVIEW",
    }:
        return "MANUAL_REVIEW"

    if value in {
        "ESCALATE",
        "ESCALATED",
    }:
        return "ESCALATE"

    return "OTHER"


def _get_explanation(decision_result: dict[str, Any]) -> str:
    """
    Generate the memo while protecting the CLI from unexpected failures.

    gemini_reasoner.py already handles quota exhaustion and temporary
    service errors. This is only a final defensive boundary.
    """
    try:
        return explain_decision(decision_result)

    except Exception:
        return (
            "AI explanation is currently unavailable. "
            "The deterministic AP decision remains valid and was still "
            "recorded using Snowflake evidence and the Python decision layer."
        )


# ---------------------------------------------------------------------
# Audit logging
# ---------------------------------------------------------------------

def write_audit_log(
    decision_result: dict[str, Any],
    memo: str,
) -> None:
    """
    Write the completed AP decision and its supporting evidence to AUDIT_LOG.
    """
    sql = """
        INSERT INTO AUDIT_LOG
        (
            LOG_ID,
            INVOICE_ID,
            VENDOR_ID,
            DECISION,
            DECISION_SOURCE,
            ANOMALY_EVIDENCE,
            CONTRACT_EVIDENCE,
            REASONING,
            DECIDED_AT
        )
        SELECT
            %(log_id)s,
            %(invoice_id)s,
            %(vendor_id)s,
            %(decision)s,
            %(decision_source)s,
            PARSE_JSON(%(anomaly_evidence)s),
            PARSE_JSON(%(contract_evidence)s),
            %(reasoning)s,
            %(decided_at)s
    """

    evidence = decision_result.get("evidence", {})

    anomaly_evidence = {
        "review_entry": evidence.get("review_entry"),
        "invoice_anomalies": evidence.get("invoice_anomalies"),
        "sql_action": decision_result.get("sql_action"),
        "sql_decision": decision_result.get("sql_decision"),
        "final_decision": decision_result.get("decision"),
        "decision_source": decision_result.get("decision_source"),
    }

    contract_evidence = {
        "contract_analysis": evidence.get("contract_analysis"),
        "contract_status": evidence.get("contract_status"),
        "price_check": evidence.get("price_check"),
    }

    execute(
        sql,
        {
            "log_id": str(uuid.uuid4()),
            "invoice_id": decision_result["invoice_id"],
            "vendor_id": decision_result["vendor_id"],
            "decision": decision_result["decision"],
            "decision_source": decision_result.get(
                "decision_source",
                "UNKNOWN",
            ),
            "anomaly_evidence": json.dumps(
                anomaly_evidence,
                default=str,
            ),
            "contract_evidence": json.dumps(
                contract_evidence,
                default=str,
            ),
            "reasoning": memo,
            "decided_at": datetime.now(
                timezone.utc
            ).isoformat(),
        },
    )


# ---------------------------------------------------------------------
# Console reporting
# ---------------------------------------------------------------------

def print_report(
    decision_result: dict[str, Any],
    memo: str,
    audit_written: bool = False,
) -> None:
    """
    Print a readable AP review report.

    When Python overrides Snowflake for safety, the report displays both
    Snowflake's original decision and the final decision.
    """
    final_decision = str(
        decision_result.get("decision", "UNKNOWN")
    ).strip().upper()

    sql_action = decision_result.get("sql_action")
    sql_decision = decision_result.get("sql_decision")

    if sql_action is not None:
        sql_action = str(sql_action).strip().upper()

    if sql_decision is not None:
        sql_decision = str(sql_decision).strip().upper()

    decision_source = str(
        decision_result.get(
            "decision_source",
            "UNKNOWN",
        )
    ).strip().upper()

    override_occurred = (
        sql_decision is not None
        and sql_decision != final_decision
    )

    print("=" * 60)
    print("AP AUTOPILOT")
    print("=" * 60)

    print(f"Invoice:        {decision_result['invoice_id']}")
    print(f"Vendor:         {decision_result['vendor_id']}")
    print(f"Severity:       {decision_result['severity']}")

    if override_occurred:
        if sql_action:
            print(f"SQL Action:     {sql_action}")

        print(f"SQL Decision:   {sql_decision}")
        print(f"Final Decision: {final_decision}  (overridden)")
        print(f"Decided by:     {decision_source}")

    else:
        if sql_action and sql_action != final_decision:
            print(f"SQL Action:     {sql_action}")

        print(f"Decision:       {final_decision}")
        print(f"Decided by:     {decision_source}")

    print("\nAI Summary")
    print("-" * 60)
    print(memo)

    if audit_written:
        print("\n✓ Audit log written successfully.")

    print("=" * 60)


# ---------------------------------------------------------------------
# Single-invoice workflow
# ---------------------------------------------------------------------

def review_invoice(invoice_id: str) -> dict[str, Any]:
    """
    Review one invoice, explain the decision, write the audit log,
    and print the report.
    """
    normalised_invoice_id = normalise_identifier(
        invoice_id,
        "Invoice ID",
    )

    vendor_id = get_vendor_id_for_invoice(
        normalised_invoice_id
    )

    decision_result = decide(
        normalised_invoice_id,
        vendor_id,
    )

    memo = _get_explanation(decision_result)

    # Write first. Only claim success after Snowflake accepts the row.
    write_audit_log(
        decision_result,
        memo,
    )

    print_report(
        decision_result,
        memo,
        audit_written=True,
    )

    return decision_result


# ---------------------------------------------------------------------
# Batch workflow
# ---------------------------------------------------------------------

def scan_open_invoices() -> None:
    """
    Process every invoice currently present in AP_REVIEW_QUEUE.
    """
    invoices = get_all_open_invoices()

    if not invoices:
        print("No invoices found in AP_REVIEW_QUEUE.")
        return

    print(
        f"Scanning {len(invoices)} "
        "review-queue invoices...\n"
    )

    summary = {
        "AUTO_APPROVE": 0,
        "MANUAL_REVIEW": 0,
        "ESCALATE": 0,
        "OTHER": 0,
        "ERROR": 0,
    }

    for row in invoices:
        invoice_id = row["INVOICE_ID"]

        try:
            vendor_id = get_vendor_id_for_invoice(
                invoice_id
            )

            decision_result = decide(
                invoice_id,
                vendor_id,
            )

            memo = _get_explanation(
                decision_result
            )

            write_audit_log(
                decision_result,
                memo,
            )

            decision_bucket = _normalise_decision_bucket(
                decision_result["decision"]
            )

            summary[decision_bucket] += 1

            # Keep successful auto-approvals quiet during batch processing.
            if decision_bucket != "AUTO_APPROVE":
                print_report(
                    decision_result,
                    memo,
                    audit_written=True,
                )
                print()

        except Exception as exc:
            summary["ERROR"] += 1
            print(
                f"[ERROR] {invoice_id}: {exc}"
            )

    successful = (
        summary["AUTO_APPROVE"]
        + summary["MANUAL_REVIEW"]
        + summary["ESCALATE"]
        + summary["OTHER"]
    )

    total = successful + summary["ERROR"]

    print("\n" + "=" * 60)
    print("BATCH SUMMARY")
    print("=" * 60)

    print(
        f"Auto approved:  "
        f"{summary['AUTO_APPROVE']}"
    )
    print(
        f"Manual review:  "
        f"{summary['MANUAL_REVIEW']}"
    )
    print(
        f"Escalated:      "
        f"{summary['ESCALATE']}"
    )
    print(
        f"Other:          "
        f"{summary['OTHER']}"
    )
    print(
        f"Errors:         "
        f"{summary['ERROR']}"
    )

    if total:
        success_rate = (
            successful / total
        ) * 100

        print()
        print(
            f"Processed successfully: "
            f"{successful}/{total}"
        )
        print(
            f"Success rate:           "
            f"{success_rate:.2f}%"
        )

    print("=" * 60)


# ---------------------------------------------------------------------
# Contract inspection
# ---------------------------------------------------------------------

def inspect_contract(vendor_id: str) -> None:
    """
    Print contract status, clause analysis, and price evidence for one vendor.
    """
    normalised_vendor_id = normalise_identifier(
        vendor_id,
        "Vendor ID",
    )

    status = get_contract_status(
        normalised_vendor_id
    )

    analysis = get_contract_analysis(
        normalised_vendor_id
    )

    price_check = get_price_check(
        normalised_vendor_id
    )

    print("=" * 60)
    print(
        f"CONTRACT INSPECTION: "
        f"{normalised_vendor_id}"
    )
    print("=" * 60)

    print(
        "\nStatus:\n"
        f"{json.dumps(status, indent=2, default=str)}"
    )

    print(
        "\nClause analysis:\n"
        f"{json.dumps(analysis, indent=2, default=str)}"
    )

    print(
        "\nPrice check:\n"
        f"{json.dumps(price_check, indent=2, default=str)}"
    )

    print("=" * 60)


# ---------------------------------------------------------------------
# CLI parsing
# ---------------------------------------------------------------------

def print_usage() -> None:
    """
    Print available CLI commands.
    """
    print(
        "Available commands:\n\n"
        "  python cli.py review-invoice <INVOICE_ID>\n"
        "  python cli.py scan-open-invoices\n"
        "  python cli.py inspect-contract <VENDOR_ID>\n\n"
        "Examples:\n"
        "  python cli.py review-invoice INV0007\n"
        "  python cli.py scan-open-invoices\n"
        "  python cli.py inspect-contract V003"
    )


def main() -> None:
    """
    Parse and execute the requested CLI command.
    """
    if len(sys.argv) < 2:
        print_usage()
        raise SystemExit(1)

    command = sys.argv[1].strip().lower()

    try:
        if command == "review-invoice":
            if len(sys.argv) != 3:
                print(
                    "Usage: python cli.py "
                    "review-invoice <INVOICE_ID>"
                )
                raise SystemExit(1)

            review_invoice(sys.argv[2])

        elif command == "scan-open-invoices":
            if len(sys.argv) != 2:
                print(
                    "Usage: python cli.py "
                    "scan-open-invoices"
                )
                raise SystemExit(1)

            scan_open_invoices()

        elif command == "inspect-contract":
            if len(sys.argv) != 3:
                print(
                    "Usage: python cli.py "
                    "inspect-contract <VENDOR_ID>"
                )
                raise SystemExit(1)

            inspect_contract(sys.argv[2])

        else:
            print(
                f"Unknown command: {command}\n"
            )
            print_usage()
            raise SystemExit(1)

    except ValueError as exc:
        print(f"Input error: {exc}")
        raise SystemExit(1)

    except Exception as exc:
        print("AP Autopilot command failed.")
        print(exc)
        raise SystemExit(1)


if __name__ == "__main__":
    main()