"""
Generates synthetic vendor contract text as .txt files using the
Google Gemini API.

Project structure expected:

ap-autopilot/
├── .env
└── data/
    ├── generate_contracts.py
    └── output/
        ├── vendors.csv
        ├── purchase_orders.csv
        └── contracts/

Required .env entry:

    GOOGLE_API_KEY=your_actual_gemini_api_key

Install dependencies:

    python -m pip install google-genai python-dotenv

Run from the project root:

    python .\\data\\generate_contracts.py

The generated contracts deliberately vary in structure so the
contract-clause skill must parse realistic documents rather than
matching one fixed template.
"""

import csv
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from google import genai


# ---------------------------------------------------------------------
# File and folder paths
# ---------------------------------------------------------------------

# Folder containing this script:
# ap-autopilot/data/
DATA_DIR = Path(__file__).resolve().parent

# Project root:
# ap-autopilot/
PROJECT_DIR = DATA_DIR.parent

# Input and output paths
OUTPUT_DIR = DATA_DIR / "output"
VENDORS_FILE = OUTPUT_DIR / "vendors.csv"
PURCHASE_ORDERS_FILE = OUTPUT_DIR / "purchase_orders.csv"
CONTRACTS_DIR = OUTPUT_DIR / "contracts"

CONTRACTS_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------
# Load Gemini API key from .env
# ---------------------------------------------------------------------

ENV_FILE = PROJECT_DIR / ".env"

load_dotenv(dotenv_path=ENV_FILE)

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise RuntimeError(
        "Gemini API key not found.\n\n"
        f"Checked this file:\n{ENV_FILE}\n\n"
        "Make sure the file contains:\n"
        "GOOGLE_API_KEY=your_actual_gemini_api_key"
    )


# ---------------------------------------------------------------------
# Configure Gemini
# ---------------------------------------------------------------------

client = genai.Client(api_key=api_key)

# Uses Google's current Flash alias rather than a retired fixed model.
MODEL_NAME = "gemini-flash-latest"

# Free-tier limits may allow only a few requests per minute.
REQUEST_DELAY_SECONDS = 15

# Number of attempts for temporary API failures.
MAX_ATTEMPTS = 4

# Waiting period after a rate-limit response.
RATE_LIMIT_WAIT_SECONDS = 65


# ---------------------------------------------------------------------
# Validate required input files
# ---------------------------------------------------------------------

if not VENDORS_FILE.exists():
    raise FileNotFoundError(
        f"vendors.csv was not found:\n{VENDORS_FILE}\n\n"
        "Run generate_synthetic_data.py first."
    )

if not PURCHASE_ORDERS_FILE.exists():
    raise FileNotFoundError(
        f"purchase_orders.csv was not found:\n"
        f"{PURCHASE_ORDERS_FILE}\n\n"
        "Run generate_synthetic_data.py first."
    )


# ---------------------------------------------------------------------
# Read CSV files
# ---------------------------------------------------------------------

with VENDORS_FILE.open(
    mode="r",
    encoding="utf-8-sig",
    newline="",
) as file:
    vendors = list(csv.DictReader(file))

with PURCHASE_ORDERS_FILE.open(
    mode="r",
    encoding="utf-8-sig",
    newline="",
) as file:
    purchase_orders = list(csv.DictReader(file))


if not vendors:
    raise ValueError("vendors.csv does not contain any vendor records.")

if not purchase_orders:
    raise ValueError(
        "purchase_orders.csv does not contain any purchase-order records."
    )


# ---------------------------------------------------------------------
# Group purchase orders by vendor
# ---------------------------------------------------------------------

po_by_vendor: dict[str, list[dict[str, str]]] = {}

for purchase_order in purchase_orders:
    vendor_id = purchase_order.get("vendor_id", "").strip()

    if vendor_id:
        po_by_vendor.setdefault(vendor_id, []).append(purchase_order)


# ---------------------------------------------------------------------
# Synthetic anomaly configuration
# ---------------------------------------------------------------------

# These vendors receive contract prices that deliberately differ from
# their purchase-order prices.
MISMATCH_VENDORS = {"V003", "V007"}

STRUCTURE_VARIANTS = [
    (
        "a formal enterprise master services agreement with numbered "
        "sections and a pricing schedule as an appendix"
    ),
    (
        "a shorter services agreement with pricing embedded naturally "
        "inside prose paragraphs rather than a table"
    ),
    (
        "a vendor-drafted template with slightly inconsistent formatting "
        "and an awkwardly structured pricing table"
    ),
    (
        "a renewal amendment letter that references an original contract "
        "and states only the new commercial terms"
    ),
]


# ---------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------

def is_rate_limit_error(error: Exception) -> bool:
    """Return True when the API error appears to be a quota failure."""
    error_text = str(error).lower()

    return (
        "429" in error_text
        or "resource_exhausted" in error_text
        or "quota exceeded" in error_text
        or "rate limit" in error_text
    )


def is_model_error(error: Exception) -> bool:
    """Return True when the requested Gemini model is unavailable."""
    error_text = str(error).lower()

    return (
        "404" in error_text
        or "not_found" in error_text
        or "model" in error_text and "not available" in error_text
    )


def generate_contract_text(prompt: str, vendor_id: str) -> str | None:
    """
    Generate contract text with retry handling.

    Returns the generated contract string or None when generation fails.
    """

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt,
            )

            contract_text = response.text

            if not contract_text or not contract_text.strip():
                raise ValueError("Gemini returned an empty response.")

            return contract_text.strip()

        except Exception as error:
            print(
                f"Attempt {attempt}/{MAX_ATTEMPTS} failed "
                f"for {vendor_id}: {error}"
            )

            if is_rate_limit_error(error):
                if attempt < MAX_ATTEMPTS:
                    print(
                        f"Rate limit reached. Waiting "
                        f"{RATE_LIMIT_WAIT_SECONDS} seconds before retrying..."
                    )
                    time.sleep(RATE_LIMIT_WAIT_SECONDS)
                    continue

            if is_model_error(error):
                print(
                    "\nThe configured Gemini model is unavailable.\n"
                    f"Current model: {MODEL_NAME}\n"
                    "Check the available Gemini models for your API key."
                )

            break

    return None


# ---------------------------------------------------------------------
# Generate contracts
# ---------------------------------------------------------------------

generated_count = 0
existing_count = 0
failed_count = 0

for index, vendor in enumerate(vendors):
    vendor_id = vendor.get("vendor_id", "").strip()
    vendor_name = vendor.get("vendor_name", "").strip()

    if not vendor_id:
        print("Skipping a vendor row because vendor_id is missing.")
        failed_count += 1
        continue

    filename = CONTRACTS_DIR / f"contract_{vendor_id}.txt"

    # Resume safely after interrupted or partially successful runs.
    if filename.exists() and filename.stat().st_size > 100:
        print(
            f"\nSkipping {vendor_id}: "
            f"{filename.name} already exists."
        )
        existing_count += 1
        continue

    items = po_by_vendor.get(vendor_id, [])

    if not items:
        print(f"\nSkipping {vendor_id}: no purchase orders were found.")
        failed_count += 1
        continue

    pricing_lines = []

    for item in items:
        line_item = item.get(
            "line_item",
            "Unspecified item",
        ).strip()

        try:
            purchase_order_price = float(item["unit_price"])
        except (KeyError, TypeError, ValueError):
            print(
                f"Skipping invalid purchase-order row for "
                f"{vendor_id}: {item}"
            )
            continue

        contract_price = purchase_order_price

        if vendor_id in MISMATCH_VENDORS:
            # Deliberately make the contract price 12% higher than the
            # purchase-order price.
            contract_price = round(
                purchase_order_price * 1.12,
                2,
            )

        pricing_lines.append(
            f"- {line_item}: ${contract_price:.2f} per unit"
        )

    if not pricing_lines:
        print(
            f"\nSkipping {vendor_id}: "
            "no valid pricing lines were available."
        )
        failed_count += 1
        continue

    pricing_block = "\n".join(pricing_lines)
    structure = STRUCTURE_VARIANTS[
        index % len(STRUCTURE_VARIANTS)
    ]

    prompt = f"""
Write a realistic but concise vendor contract excerpt of approximately
400 to 600 words for a fictional business relationship.

This is entirely synthetic data created for a portfolio demonstration.
No real company, person, or vendor is involved.

Vendor information:
- Vendor name: {vendor_name}
- Vendor ID: {vendor_id}
- Contract ID: {vendor.get("contract_id", "")}
- Contract period: {vendor.get("contract_start", "")} to {vendor.get("contract_end", "")}
- Payment terms: {vendor.get("contracted_terms", "")}

Pricing terms that must appear in the document:

{pricing_block}

Also include:

- A renewal clause. Either automatically renew the agreement unless
  cancelled with 60 days' notice, or require explicit renegotiation.

- A late-payment penalty clause, such as a charge of 1.5 percent per
  month on overdue balances.

- A price-increase clause requiring written advance notice, such as
  30 days.

- Normal commercial language concerning invoices, delivery or service
  obligations, termination, and dispute handling.

Use the following document structure:

{structure}

Integrate the pricing terms naturally into the agreement. Preserve the
exact prices provided above.

Output only the contract text. Do not include a preamble, explanation,
markdown code fence, or commentary.
""".strip()

    print(f"\nGenerating contract for {vendor_id}: {vendor_name}")

    contract_text = generate_contract_text(
        prompt=prompt,
        vendor_id=vendor_id,
    )

    if not contract_text:
        print(f"Skipping {vendor_id}: generation failed.")
        failed_count += 1
        continue

    filename.write_text(
        contract_text,
        encoding="utf-8",
    )

    mismatch_status = (
        " [PRICE MISMATCH SEEDED]"
        if vendor_id in MISMATCH_VENDORS
        else ""
    )

    print(f"Wrote {filename}{mismatch_status}")

    generated_count += 1

    # Pause before the next vendor to remain beneath free-tier limits.
    time.sleep(REQUEST_DELAY_SECONDS)


# ---------------------------------------------------------------------
# Completion message
# ---------------------------------------------------------------------

print("\n" + "=" * 60)
print("Contract generation complete.")
print("=" * 60)
print(f"Newly generated: {generated_count}")
print(f"Already existed: {existing_count}")
print(f"Failed/skipped:   {failed_count}")
print(f"Total vendors:    {len(vendors)}")
print(f"Output folder:    {CONTRACTS_DIR}")

txt_files = list(CONTRACTS_DIR.glob("contract_*.txt"))

print(f"Contract files currently present: {len(txt_files)}")

if len(txt_files) == len(vendors):
    print(
        "\nAll contract files are ready.\n"
        "Next command:\n"
        "python .\\data\\convert_contracts_to_pdf.py"
    )
else:
    print(
        "\nSome contracts are still missing. You can rerun this script.\n"
        "Existing contracts will not be regenerated."
    )