#!/usr/bin/env python3
"""
PDF to Markdown Converter

Converts PDF documents to Markdown format with:
- Text extraction with layout preservation
- Table detection and conversion
- Basic heading detection
- Optional OCR for scanned PDFs

Usage:
    python pdf_to_markdown.py input.pdf [output.md]
    python pdf_to_markdown.py input.pdf -o output.md --ocr  # For scanned PDFs
"""

import argparse
import re
import sys
from pathlib import Path
from typing import Optional

import pdfplumber


def detect_headings(lines: list[str]) -> list[str]:
    """Detect potential headings based on line characteristics."""
    heading_lines = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # Skip short lines
        if len(stripped) < 3:
            continue

        # Check if line is all caps or title case (likely a heading)
        is_all_caps = stripped.isupper() and len(stripped) < 80
        is_title_case = (
            stripped.istitle() and len(stripped.split()) <= 8 and len(stripped) < 60
        )

        # Check for numbered sections like "1. Introduction"
        is_numbered_section = bool(re.match(r"^\d+\.\s+[A-Z]", stripped))

        if is_all_caps or is_title_case or is_numbered_section:
            heading_lines.append(stripped)

    return heading_lines


def lines_to_markdown(lines: list[str]) -> str:
    """Convert extracted lines to Markdown format."""
    md_lines = []
    in_code_block = False

    for line in lines:
        stripped = line.strip()

        # Skip empty lines at start
        if not stripped and not md_lines:
            continue

        # Detect code blocks
        if "```" in stripped:
            in_code_block = not in_code_block
            md_lines.append(stripped)
            continue

        if in_code_block:
            md_lines.append(stripped)
            continue

        # Skip very short lines that are likely noise
        if len(stripped) < 2:
            if md_lines and md_lines[-1].strip():
                md_lines.append("")
            continue

        # Detect potential headings
        is_all_caps = stripped.isupper() and len(stripped) < 80
        is_title_case = (
            stripped.istitle() and len(stripped.split()) <= 6 and len(stripped) < 60
        )
        is_numbered_section = bool(re.match(r"^\d+\.\s+", stripped))

        if is_all_caps or is_title_case:
            # Add blank line before headings
            if md_lines and md_lines[-1].strip():
                md_lines.append("")
            md_lines.append(f"## {stripped}")
            md_lines.append("")
        elif is_numbered_section:
            if md_lines and md_lines[-1].strip():
                md_lines.append("")
            md_lines.append(f"## {stripped}")
            md_lines.append("")
        else:
            md_lines.append(stripped)

    return "\n".join(md_lines)


def extract_tables(pdf_path: str) -> list[tuple[int, list[list[str]]]]:
    """Extract tables from PDF with page numbers."""
    tables = []

    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, 1):
            page_tables = page.extract_tables()
            if page_tables:
                for table in page_tables:
                    if table and any(row for row in table):
                        tables.append((page_num, table))

    return tables


def tables_to_markdown(tables: list[tuple[int, list[list[str]]]]) -> str:
    """Convert extracted tables to Markdown format."""
    if not tables:
        return ""

    md_sections = ["\n\n## Tables\n"]

    for page_num, table in tables:
        md_sections.append(f"### Page {page_num}\n")

        for row in table:
            # Clean cells
            cleaned_row = [cell.strip() if cell else "" for cell in row]
            md_sections.append("| " + " | ".join(cleaned_row) + " |")

        md_sections.append("")

    return "\n".join(md_sections)


def extract_text_with_layout(pdf_path: str) -> tuple[str, dict]:
    """Extract text while preserving basic layout."""
    full_text = ""
    metadata = {}

    with pdfplumber.open(pdf_path) as pdf:
        # Extract metadata
        if pdf.metadata:
            metadata = {
                "title": pdf.metadata.get("/Title", ""),
                "author": pdf.metadata.get("/Author", ""),
                "subject": pdf.metadata.get("/Subject", ""),
                "creator": pdf.metadata.get("/Creator", ""),
                "producer": pdf.metadata.get("/Producer", ""),
            }

        # Extract text from each page
        for page_num, page in enumerate(pdf.pages, 1):
            text = page.extract_text()
            if text:
                full_text += f"\n\n<!-- Page {page_num} -->\n\n"
                full_text += text

    return full_text, metadata


def extract_text_with_ocr(pdf_path: str) -> str:
    """Extract text using OCR (for scanned PDFs)."""
    try:
        from pdf2image import convert_from_path
        import pytesseract
    except ImportError:
        print("Error: OCR requires pdf2image and pytesseract", file=sys.stderr)
        print("Install with: pip install pdf2image pytesseract", file=sys.stderr)
        sys.exit(1)

    images = convert_from_path(pdf_path)
    text = ""

    for page_num, image in enumerate(images, 1):
        page_text = pytesseract.image_to_string(image)
        text += f"\n\n<!-- Page {page_num} -->\n\n"
        text += page_text

    return text


def main():
    parser = argparse.ArgumentParser(
        description="Convert PDF to Markdown",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("input", help="Input PDF file path")
    parser.add_argument(
        "-o", "--output", help="Output Markdown file path (default: input.md)"
    )
    parser.add_argument("--ocr", action="store_true", help="Use OCR for scanned PDFs")
    parser.add_argument(
        "--extract-tables", action="store_true", help="Extract and include tables"
    )
    parser.add_argument(
        "--no-metadata", action="store_true", help="Don't include metadata in output"
    )

    args = parser.parse_args()

    # Validate input
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: File not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    if not input_path.suffix.lower() == ".pdf":
        print("Error: Input file must be a PDF", file=sys.stderr)
        sys.exit(1)

    # Determine output path
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = input_path.with_suffix(".md")

    print(f"Converting: {input_path} -> {output_path}")

    # Extract text
    if args.ocr:
        print("Using OCR mode...")
        full_text = extract_text_with_ocr(str(input_path))
    else:
        full_text, metadata = extract_text_with_layout(str(input_path))

    if not full_text.strip():
        print(
            "Warning: No text extracted. Try --ocr for scanned PDFs.", file=sys.stderr
        )

    # Process to markdown
    lines = full_text.split("\n")
    md_content = lines_to_markdown(lines)

    # Extract tables if requested
    tables_md = ""
    if args.extract_tables:
        print("Extracting tables...")
        tables = extract_tables(str(input_path))
        tables_md = tables_to_markdown(tables)

    # Build final output
    output_parts = []

    # Add metadata
    if not args.no_metadata and not args.ocr and metadata:
        meta = metadata
        if any(meta.values()):
            output_parts.append("---")
            if meta.get("title"):
                output_parts.append(f'title: "{meta["title"]}"')
            if meta.get("author"):
                output_parts.append(f'author: "{meta["author"]}"')
            if meta.get("subject"):
                output_parts.append(f'subject: "{meta["subject"]}"')
            output_parts.append("---\n")

    output_parts.append(md_content)

    if tables_md:
        output_parts.append(tables_md)

    # Write output
    final_output = "\n".join(output_parts)
    output_path.write_text(final_output, encoding="utf-8")

    print(f"Done! Output saved to: {output_path}")
    print(f"Character count: {len(final_output):,}")


if __name__ == "__main__":
    main()
