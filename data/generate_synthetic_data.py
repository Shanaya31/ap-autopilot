"""
Generates synthetic VENDORS / PURCHASE_ORDERS / INVOICES / PAYMENT_HISTORY
CSVs for AP Autopilot, with deliberately seeded anomalies so you can verify
your skills catch them.

Usage:
    pip install faker --break-system-packages
    python generate_synthetic_data.py

Output: ./output/vendors.csv, purchase_orders.csv, invoices.csv, payment_history.csv
Load these into Snowflake via PUT + COPY INTO (see sql/01_schema.sql for table defs).
"""

import csv
import random
import os
from datetime import date, timedelta

random.seed(42)  # reproducible seed set
OUT_DIR = "output"
os.makedirs(OUT_DIR, exist_ok=True)

VENDOR_NAMES = [
    "Meridian Logistics", "Northbridge Supplies", "Cascade Packaging",
    "Vertex IT Services", "Solaris Facilities Mgmt", "Anchor Freight Co",
    "Prairie Office Solutions", "Ironclad Security Systems", "Blue Harbor Consulting",
    "Redwood Maintenance Group",
]

LINE_ITEMS = [
    "Cardboard Cartons (per unit)", "Pallet Wrap (per roll)", "IT Support Hours",
    "Security Patrol (per shift)", "Freight - Regional Route", "Office Cleaning (monthly)",
    "Consulting Hours - Sr", "Facilities Repair Call-out",
]

today = date(2026, 7, 21)

vendors = []
for i, name in enumerate(VENDOR_NAMES, start=1):
    vendor_id = f"V{i:03d}"
    contract_start = today - timedelta(days=random.randint(200, 700))
    # seed 2 vendors (V009, V010) with EXPIRED contracts on purpose
    if vendor_id in ("V009", "V010"):
        contract_end = today - timedelta(days=random.randint(10, 60))
    else:
        contract_end = contract_start + timedelta(days=random.randint(365, 730))
    vendors.append({
        "vendor_id": vendor_id,
        "vendor_name": name,
        "contract_id": f"C{i:03d}",
        "contract_start": contract_start.isoformat(),
        "contract_end": contract_end.isoformat(),
        "contracted_terms": random.choice(["NET_30", "NET_45", "NET_60"]),
        "contact_email": f"ap@{name.lower().replace(' ', '')}.example.com",
    })

with open(f"{OUT_DIR}/vendors.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=vendors[0].keys())
    w.writeheader()
    w.writerows(vendors)

# Purchase orders: one baseline unit_price per vendor/line_item pair
purchase_orders = []
po_counter = 1
po_price_map = {}  # (vendor_id, line_item) -> contracted unit_price
for v in vendors:
    n_items = random.randint(1, 2)
    items = random.sample(LINE_ITEMS, n_items)
    for item in items:
        unit_price = round(random.uniform(8, 400), 2)
        po_id = f"PO{po_counter:04d}"
        po_counter += 1
        purchase_orders.append({
            "po_id": po_id,
            "vendor_id": v["vendor_id"],
            "line_item": item,
            "unit_price": unit_price,
            "quantity": random.randint(10, 500),
            "po_date": v["contract_start"],
        })
        po_price_map[(v["vendor_id"], item)] = (po_id, unit_price)

with open(f"{OUT_DIR}/purchase_orders.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=purchase_orders[0].keys())
    w.writeheader()
    w.writerows(purchase_orders)

# Invoices: mostly clean, with seeded anomalies
invoices = []
inv_counter = 1
price_creep_targets = random.sample(list(po_price_map.keys()), 4)  # 4 price-creep cases

for v in vendors:
    vendor_items = [k for k in po_price_map if k[0] == v["vendor_id"]]
    n_invoices = random.randint(4, 7)
    for _ in range(n_invoices):
        item_key = random.choice(vendor_items)
        po_id, base_price = po_price_map[item_key]
        invoice_date = today - timedelta(days=random.randint(1, 180))

        invoiced_price = base_price
        if item_key in price_creep_targets and invoice_date > today - timedelta(days=90):
            # 8-20% above contracted price -- the anomaly to catch
            invoiced_price = round(base_price * random.uniform(1.08, 1.20), 2)

        qty = random.randint(10, 500)
        invoices.append({
            "invoice_id": f"INV{inv_counter:04d}",
            "vendor_id": v["vendor_id"],
            "po_id": po_id,
            "line_item": item_key[1],
            "invoiced_unit_price": invoiced_price,
            "invoiced_quantity": qty,
            "invoice_amount": round(invoiced_price * qty, 2),
            "invoice_date": invoice_date.isoformat(),
            "payment_terms_stated": v["contracted_terms"],
        })
        inv_counter += 1

# Seed 3 duplicate invoices: clone an existing invoice with a new ID, same amount, +1-2 days
originals = random.sample(invoices, 3)
for orig in originals:
    dup_date = date.fromisoformat(orig["invoice_date"]) + timedelta(days=random.randint(1, 2))
    invoices.append({
        **orig,
        "invoice_id": f"INV{inv_counter:04d}",
        "invoice_date": dup_date.isoformat(),
    })
    inv_counter += 1

with open(f"{OUT_DIR}/invoices.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=invoices[0].keys())
    w.writeheader()
    w.writerows(invoices)

# Payment history: pay ~90% of invoices, on time-ish
payments = []
pay_counter = 1
for inv in invoices:
    if random.random() < 0.9:
        pay_date = date.fromisoformat(inv["invoice_date"]) + timedelta(days=random.randint(20, 50))
        payments.append({
            "payment_id": f"PMT{pay_counter:04d}",
            "invoice_id": inv["invoice_id"],
            "amount_paid": inv["invoice_amount"],
            "payment_date": pay_date.isoformat(),
        })
        pay_counter += 1

with open(f"{OUT_DIR}/payment_history.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=payments[0].keys())
    w.writeheader()
    w.writerows(payments)

print(f"Generated {len(vendors)} vendors, {len(purchase_orders)} POs, "
      f"{len(invoices)} invoices ({len(originals)} seeded duplicates, "
      f"{len(price_creep_targets)} seeded price-creep pairs), {len(payments)} payments.")
print(f"Seeded expired-contract vendors: V009, V010")
print(f"Output written to ./{OUT_DIR}/")
