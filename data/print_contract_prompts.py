"""
Alternative to generate_contracts.py that needs NO API key at all.

Instead of calling an LLM API, this script reads your vendors.csv and
purchase_orders.csv and PRINTS OUT one ready-to-paste prompt per vendor.
Paste each prompt into Claude.ai, ChatGPT, Gemini's chat UI, or any chat tool
you already use, then save the response as output/contracts/contract_<vendor_id>.txt.

This is the simplest path if you don't want to set up a new API key just to
generate ~10 short documents.

Usage:
    python print_contract_prompts.py > contract_prompts.txt
    (then open contract_prompts.txt, copy each prompt one at a time into your
    chat tool of choice, and save each response manually)
"""

import csv

with open("output/vendors.csv") as f:
    vendors = list(csv.DictReader(f))

with open("output/purchase_orders.csv") as f:
    pos = list(csv.DictReader(f))

po_by_vendor = {}
for po in pos:
    po_by_vendor.setdefault(po["vendor_id"], []).append(po)

# Same two vendors deliberately get a mismatched contract price --
# tests whether contract-clause-skill catches a contract that says one
# thing while the PO/invoice system reflects another.
MISMATCH_VENDORS = {"V003", "V007"}

STRUCTURE_VARIANTS = [
    "a formal enterprise MSA with numbered sections and a pricing schedule as an appendix",
    "a shorter services agreement with pricing embedded in prose paragraphs, not a table",
    "a vendor-drafted template with inconsistent formatting and a pricing table with merged cells described awkwardly",
    "a renewal amendment letter that references an original contract and only states the NEW terms",
]

for i, v in enumerate(vendors):
    items = po_by_vendor.get(v["vendor_id"], [])
    if not items:
        continue

    lines = []
    for item in items:
        price = float(item["unit_price"])
        if v["vendor_id"] in MISMATCH_VENDORS:
            price = round(price * 1.12, 2)
        lines.append(f"- {item['line_item']}: ${price:.2f} per unit")

    pricing_block = "\n".join(lines)
    structure = STRUCTURE_VARIANTS[i % len(STRUCTURE_VARIANTS)]

    prompt = f"""Write a realistic but concise (400-600 word) vendor contract excerpt for a fictional
business relationship. This is entirely synthetic/fictional data for a hackathon demo -- no real
company or vendor is involved.

Vendor: {v['vendor_name']}
Contract ID: {v['contract_id']}
Contract period: {v['contract_start']} to {v['contract_end']}
Payment terms: {v['contracted_terms']}

Pricing terms to include (word them naturally into the document, don't just list them):
{pricing_block}

Also include:
- A renewal clause (auto-renews unless cancelled with 60 days notice, OR requires explicit renegotiation -- pick one)
- A late payment penalty clause (e.g. 1.5% per month on overdue balances)
- One clause about price increases requiring written notice period (e.g. 30 days)

Format this as: {structure}

Output ONLY the contract text, no preamble or explanation."""

    print("=" * 80)
    print(f"PROMPT FOR: contract_{v['vendor_id']}.txt" +
          (" [PRICE MISMATCH SEEDED]" if v["vendor_id"] in MISMATCH_VENDORS else ""))
    print("=" * 80)
    print(prompt)
    print()
