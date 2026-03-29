#!/usr/bin/env python3
"""Markdown to PDF converter using Pandoc.

Usage:
    python md2pdf.py input.md [options]

Examples:
    python md2pdf.py README.md
    python md2pdf.py input.md --output output.pdf
    python md2pdf.py input.md --toc --theme=monokai --page-size=letter
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


TEXLIVE_PATH = "/usr/local/texlive/2026basic/bin/universal-darwin"

PANDOC_HIGHLIGHT_STYLES = [
    "pygments",
    "tango",
    "espresso",
    "zenburn",
    "kate",
    "monochrome",
    "breezeDark",
    "android",
    "arrnir",
]

PAGE_SIZES = ["a4", "letter", "legal", "a5", "b5"]


def check_dependencies():
    errors = []

    pandoc_path = shutil.which("pandoc")
    if not pandoc_path:
        if Path("/opt/homebrew/bin/pandoc").exists():
            pandoc_path = "/opt/homebrew/bin/pandoc"
        elif Path("/usr/local/bin/pandoc").exists():
            pandoc_path = "/usr/local/bin/pandoc"

    if not pandoc_path:
        errors.append("pandoc not found. Install: brew install pandoc")

    xelatex_path = shutil.which("xelatex")
    if not xelatex_path:
        xelatex_path_candidate = Path(TEXLIVE_PATH) / "xelatex"
        if xelatex_path_candidate.exists():
            xelatex_path = str(xelatex_path_candidate)

    if not xelatex_path:
        errors.append("xelatex not found. Install: brew install --cask basictex")

    return errors


def build_pandoc_command(input_path, output_path, args):
    cmd = [
        "pandoc",
        str(input_path),
        "-o",
        str(output_path),
        "--pdf-engine=xelatex",
    ]

    if args.theme:
        cmd.extend(["--highlight-style", args.theme])

    if args.toc:
        cmd.append("--toc")

    if args.page_size and args.page_size != "a4":
        cmd.extend(["--pdf-engine-opt=-V", f"papersize={args.page_size}"])

    if args.margin and args.margin != "1in":
        cmd.extend(["--pdf-engine-opt=-V", f"geometry=margin={args.margin}"])

    if args.template:
        cmd.extend(["--template", str(args.template)])

    return cmd


def main():
    parser = argparse.ArgumentParser(
        description="Convert markdown files to PDF using Pandoc.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument("input", type=Path, help="Input markdown file")

    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output PDF file (default: same as input with .pdf extension)",
    )

    parser.add_argument("--toc", action="store_true", help="Generate table of contents")

    parser.add_argument(
        "--theme",
        choices=PANDOC_HIGHLIGHT_STYLES,
        default="pygments",
        help="Code highlighting theme (default: pygments)",
    )

    parser.add_argument(
        "--page-size", choices=PAGE_SIZES, default="a4", help="Page size (default: a4)"
    )

    parser.add_argument("--margin", default="1in", help="Page margins (default: 1in)")

    parser.add_argument("--template", type=Path, help="Custom pandoc template")

    args = parser.parse_args()

    if not args.input.exists():
        print(f"Error: Input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    if args.input.suffix.lower() != ".md":
        print(f"Warning: Input file doesn't have .md extension", file=sys.stderr)

    errors = check_dependencies()
    if errors:
        print("Error: Missing dependencies:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        sys.exit(1)

    if args.output:
        output_path = args.output
    else:
        output_path = args.input.with_suffix(".pdf")

    cmd = build_pandoc_command(args.input, output_path, args)

    env = os.environ.copy()
    if TEXLIVE_PATH not in env.get("PATH", ""):
        env["PATH"] = f"{TEXLIVE_PATH}:{env.get('PATH', '')}"

    try:
        subprocess.run(cmd, check=True, env=env)
        print(f"Successfully created: {output_path}")

    except subprocess.CalledProcessError as e:
        print(f"Error running pandoc:", file=sys.stderr)
        print(e.stderr, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
