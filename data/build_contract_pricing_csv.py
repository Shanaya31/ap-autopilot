"""
Builds contract_pricing.csv from the same synthetic purchase-order data
used to generate the vendor contracts.

V003 and V007 receive a deliberate 12% contract-price increase, matching
the anomaly logic in generate_contracts.py.

Run from the project root:

    python .\\data\\build_contract_pricing_csv.py
"""

import csv
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path


# ---------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------

DATA_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = DATA_DIR / "output"

VENDORS_FILE = OUTPUT_DIR / "vendors.csv"
PURCHASE_ORDERS_FILE = OUTPUT_DIR / "purchase_orders.csv"
OUTPUT_FILE = OUTPUT_DIR / "contract_pricing.csv"


# Must match generate_contracts.py exactly.
MISMATCH_VENDORS = {"V003", "V007"}

PRICE_MULTIPLIER = Decimal("1.12")


def read_csv(path: Path) -> list[dict[str, str]]:
    """Read a CSV file and return its rows."""

    if not path.exists():
        raise FileNotFoundError(f"Required file not found:\n{path}")

    with path.open(
        mode="r",
        encoding="utf-8-sig",
        newline="",
    ) as csv_file:
        rows = list(csv.DictReader(csv_file))

    if not rows:
        raise ValueError(f"CSV file contains no data rows:\n{path}")

    return rows


def calculate_contract_price(
    vendor_id: str,
    purchase_order_price: str,
) -> Decimal:
    """Return the synthetic contract price for one PO line."""

    try:
        price = Decimal(purchase_order_price)
    except (InvalidOperation, TypeError) as error:
        raise ValueError(
            f"Invalid unit price '{purchase_order_price}' "
            f"for vendor {vendor_id}"
        ) from error

    if vendor_id in MISMATCH_VENDORS:
        price *= PRICE_MULTIPLIER

    return price.quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )


def main() -> None:
    vendors = read_csv(VENDORS_FILE)
    purchase_orders = read_csv(PURCHASE_ORDERS_FILE)

    valid_vendor_ids = {
        vendor.get("vendor_id", "").strip()
        for vendor in vendors
        if vendor.get("vendor_id", "").strip()
    }

    rows: list[dict[str, str]] = []

    for purchase_order in purchase_orders:
        vendor_id = purchase_order.get("vendor_id", "").strip()
        line_item = purchase_order.get("line_item", "").strip()
        unit_price = purchase_order.get("unit_price", "").strip()

        if not vendor_id:
            print("Skipping PO row with missing vendor_id.")
            continue

        if vendor_id not in valid_vendor_ids:
            print(
                f"Skipping {vendor_id}: vendor not found "
                "in vendors.csv."
            )
            continue

        if not line_item:
            print(
                f"Skipping PO row for {vendor_id}: "
                "line_item is missing."
            )
            continue

        contract_price = calculate_contract_price(
            vendor_id=vendor_id,
            purchase_order_price=unit_price,
        )

        rows.append(
            {
                "vendor_id": vendor_id,
                "line_item": line_item,
                "contract_unit_price": f"{contract_price:.2f}",
                "source_file": f"contract_{vendor_id}.pdf",
            }
        )

    if not rows:
        raise RuntimeError("No contract-pricing rows were produced.")

    with OUTPUT_FILE.open(
        mode="w",
        encoding="utf-8-sig",
        newline="",
    ) as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=[
                "vendor_id",
                "line_item",
                "contract_unit_price",
                "source_file",
            ],
            quoting=csv.QUOTE_ALL,
        )

        writer.writeheader()
        writer.writerows(rows)

    mismatch_rows = [
        row
        for row in rows
        if row["vendor_id"] in MISMATCH_VENDORS
    ]

    print("\nContract-pricing CSV created successfully.")
    print(f"Total pricing rows:    {len(rows)}")
    print(f"Seeded mismatch rows:  {len(mismatch_rows)}")
    print(f"Mismatch vendors:      {sorted(MISMATCH_VENDORS)}")
    print(f"Output:                {OUTPUT_FILE}")


if __name__ == "__main__":
    main()