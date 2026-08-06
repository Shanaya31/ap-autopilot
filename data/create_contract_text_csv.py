import csv
import re
from pathlib import Path


DATA_DIR = Path(__file__).resolve().parent
CONTRACTS_DIR = DATA_DIR / "output" / "contracts"
OUTPUT_FILE = DATA_DIR / "output" / "contract_text.csv"


def extract_vendor_id(filename: str) -> str:
    match = re.search(r"V\d{3}", filename)

    if not match:
        raise ValueError(
            f"Could not extract vendor ID from filename: {filename}"
        )

    return match.group(0)


def main() -> None:
    txt_files = sorted(CONTRACTS_DIR.glob("contract_V*.txt"))

    if not txt_files:
        raise FileNotFoundError(
            f"No contract TXT files found in:\n{CONTRACTS_DIR}"
        )

    rows = []

    for txt_file in txt_files:
        contract_text = txt_file.read_text(
            encoding="utf-8"
        ).strip()

        if not contract_text:
            print(f"Skipping empty file: {txt_file.name}")
            continue

        vendor_id = extract_vendor_id(txt_file.name)
        pdf_filename = txt_file.with_suffix(".pdf").name

        rows.append(
            {
                "file_name": pdf_filename,
                "vendor_id": vendor_id,
                "raw_text": contract_text,
            }
        )

        print(f"Added {txt_file.name}")

    with OUTPUT_FILE.open(
        mode="w",
        encoding="utf-8-sig",
        newline="",
    ) as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=[
                "file_name",
                "vendor_id",
                "raw_text",
            ],
            quoting=csv.QUOTE_ALL,
        )

        writer.writeheader()
        writer.writerows(rows)

    print("\nContract CSV created successfully.")
    print(f"Rows written: {len(rows)}")
    print(f"Output: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()