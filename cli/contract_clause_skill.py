"""
Contract clause skill.

This module is intentionally a thin read-only wrapper.

All contract extraction, clause scoring, status classification, and price
comparison logic already exists in Snowflake SQL, primarily in:

- CONTRACT_CLAUSE_ANALYSIS
- CONTRACT_STATUS
- CONTRACT_PRICE_CHECK

This Python module only retrieves those precomputed results.
"""

import json
import sys
from typing import Any

from snowflake_client import query


def _normalise_vendor_id(vendor_id: str) -> str:
    """
    Validate and normalise a vendor ID.

    Raises:
        ValueError: If the vendor ID is missing or blank.
    """
    if not isinstance(vendor_id, str) or not vendor_id.strip():
        raise ValueError("Vendor ID cannot be empty.")

    return vendor_id.strip().upper()


def get_contract_analysis(vendor_id: str) -> dict[str, Any] | None:
    """
    Return the clause analysis for one vendor.

    Returns None when no contract analysis exists. Downstream code must treat
    this explicitly as a missing-contract or missing-analysis case rather
    than assuming the contract is clean.
    """
    normalised_vendor_id = _normalise_vendor_id(vendor_id)

    sql = """
        SELECT *
        FROM CONTRACT_CLAUSE_ANALYSIS
        WHERE VENDOR_ID = %(vendor_id)s
    """

    rows = query(sql, {"vendor_id": normalised_vendor_id})
    return rows[0] if rows else None


def get_contract_status(vendor_id: str) -> dict[str, Any] | None:
    """
    Return the contract status record for one vendor.

    Expected statuses may include ACTIVE, EXPIRING_SOON, and EXPIRED,
    depending on the SQL view definition.
    """
    normalised_vendor_id = _normalise_vendor_id(vendor_id)

    sql = """
        SELECT *
        FROM CONTRACT_STATUS
        WHERE VENDOR_ID = %(vendor_id)s
    """

    rows = query(sql, {"vendor_id": normalised_vendor_id})
    return rows[0] if rows else None


def get_price_check(
    vendor_id: str,
    line_item: str | None = None,
) -> list[dict[str, Any]]:
    """
    Return contract-versus-PO price comparison rows for one vendor.

    A specific line item may be supplied to narrow the results.
    """
    normalised_vendor_id = _normalise_vendor_id(vendor_id)

    if line_item is not None:
        if not isinstance(line_item, str) or not line_item.strip():
            raise ValueError("Line item cannot be blank.")

        normalised_line_item = line_item.strip()

        sql = """
            SELECT *
            FROM CONTRACT_PRICE_CHECK
            WHERE VENDOR_ID = %(vendor_id)s
              AND LINE_ITEM = %(line_item)s
            ORDER BY LINE_ITEM
        """

        return query(
            sql,
            {
                "vendor_id": normalised_vendor_id,
                "line_item": normalised_line_item,
            },
        )

    sql = """
        SELECT *
        FROM CONTRACT_PRICE_CHECK
        WHERE VENDOR_ID = %(vendor_id)s
        ORDER BY LINE_ITEM
    """

    return query(sql, {"vendor_id": normalised_vendor_id})


def get_contract_evidence(vendor_id: str) -> dict[str, Any]:
    """
    Return all contract evidence for one vendor in a single structure.
    """
    normalised_vendor_id = _normalise_vendor_id(vendor_id)

    return {
        "vendor_id": normalised_vendor_id,
        "contract_status": get_contract_status(normalised_vendor_id),
        "clause_analysis": get_contract_analysis(normalised_vendor_id),
        "price_check": get_price_check(normalised_vendor_id),
    }


def main() -> None:
    """
    Run a small command-line test for one vendor.
    """
    if len(sys.argv) != 2:
        print(
            "Usage:\n"
            "  python contract_clause_skill.py <VENDOR_ID>\n\n"
            "Example:\n"
            "  python contract_clause_skill.py V003"
        )
        raise SystemExit(1)

    vendor_id = sys.argv[1]

    try:
        result = get_contract_evidence(vendor_id)
        print(json.dumps(result, indent=2, default=str))

    except ValueError as exc:
        print(f"Input error: {exc}")
        raise SystemExit(1)

    except Exception as exc:
        print("Failed to retrieve contract evidence.")
        print(exc)
        raise SystemExit(1)


if __name__ == "__main__":
    main()