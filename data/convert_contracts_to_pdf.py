from pathlib import Path
import re

from fpdf import FPDF


BASE_DIR = Path(__file__).resolve().parent
CONTRACTS_DIR = BASE_DIR / "output" / "contracts"


def normalize_text(text: str) -> str:
    """
    Replace punctuation that the built-in PDF font may not support.
    This keeps the conversion reliable without requiring a custom font.
    """
    replacements = {
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2013": "-",
        "\u2014": "-",
        "\u2022": "-",
        "\u00a0": " ",
    }

    for original, replacement in replacements.items():
        text = text.replace(original, replacement)

    # Remove remaining characters unsupported by Latin-1 Helvetica.
    return text.encode("latin-1", errors="replace").decode("latin-1")


def extract_title(text: str, fallback: str) -> str:
    """Use the first non-empty line as the PDF title."""
    for line in text.splitlines():
        cleaned_line = line.strip()

        if cleaned_line:
            return cleaned_line[:100]

    return fallback


def convert_contract(txt_path: Path) -> Path:
    raw_text = txt_path.read_text(encoding="utf-8")
    clean_text = normalize_text(raw_text)

    pdf_path = txt_path.with_suffix(".pdf")

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_title(extract_title(clean_text, txt_path.stem))
    pdf.set_author("AP Autopilot Synthetic Data Generator")
    pdf.add_page()

    pdf.set_font("Helvetica", style="B", size=15)
    pdf.cell(
        w=0,
        h=10,
        text="Vendor Contract",
        new_x="LMARGIN",
        new_y="NEXT",
        align="C",
    )

    pdf.ln(4)
    pdf.set_font("Helvetica", size=11)

    for line in clean_text.splitlines():
        line = line.strip()

        if not line:
            pdf.ln(4)
            continue

        # Make probable headings slightly more prominent.
        is_heading = (
            len(line) <= 80
            and (
                line.isupper()
                or re.match(r"^\d+\.\s+", line)
                or line.endswith(":")
            )
        )

        if is_heading:
            pdf.set_font("Helvetica", style="B", size=11)
        else:
            pdf.set_font("Helvetica", size=11)

        pdf.multi_cell(w=0, h=6, text=line)
        pdf.ln(1)

    pdf.output(str(pdf_path))
    return pdf_path


def main() -> None:
    if not CONTRACTS_DIR.exists():
        raise FileNotFoundError(
            f"Contract directory does not exist: {CONTRACTS_DIR}"
        )

    txt_files = sorted(CONTRACTS_DIR.glob("*.txt"))

    if not txt_files:
        raise FileNotFoundError(
            f"No .txt contract files found in: {CONTRACTS_DIR}"
        )

    print(f"Found {len(txt_files)} contract text files.\n")

    converted_files = []

    for txt_path in txt_files:
        pdf_path = convert_contract(txt_path)
        converted_files.append(pdf_path)
        print(f"Converted: {txt_path.name} -> {pdf_path.name}")

    print(
        f"\nSuccessfully created {len(converted_files)} PDF contracts "
        f"in:\n{CONTRACTS_DIR}"
    )


if __name__ == "__main__":
    main()