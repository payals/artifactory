# md2pdf - Markdown to PDF Converter

Convert markdown files to beautifully formatted PDFs using Pandoc.

## Installation

### Prerequisites

```bash
# Install Pandoc
brew install pandoc

# Install XeLaTeX (for PDF generation)
brew install --cask basictex
```

### Usage

```bash
# Basic conversion
python scripts/md2pdf.py input.md

# With output filename
python scripts/md2pdf.py input.md -o output.pdf

# With table of contents
python scripts/md2pdf.py input.md --toc

# With syntax highlighting theme
python scripts/md2pdf.py input.md --theme=monokai

# Custom page size
python scripts/md2pdf.py input.md --page-size=letter

# Custom margins
python scripts/md2pdf.py input.md --margin=2in
```

## Options

| Flag | Description | Default |
|------|-------------|---------|
| `-o, --output` | Output PDF file | `<input>.pdf` |
| `--toc` | Generate table of contents | false |
| `--theme` | Syntax highlighting theme | pygments |
| `--page-size` | Page size (a4, letter, legal, a5, b5) | a4 |
| `--margin` | Page margins | 1in |
| `--template` | Custom pandoc template | none |

## Syntax Highlighting Themes

Available themes: `pygments`, `tango`, `espresso`, `zenburn`, `kate`, `monochrome`, `breezeDark`, `android`

## Supported Markdown Features

- Code blocks with syntax highlighting (150+ languages)
- LaTeX math rendering (`$inline$` and `$$block$$`)
- Tables with proper formatting
- Image embedding
- Headers, lists, blockquotes
- Links and references

## Notes

- The script automatically detects Pandoc and XeLaTeX installations
- If XeLaTeX is not in PATH, ensure it's installed via basictex
- Some box-drawing characters may not render correctly with basictex; consider installing full MacTeX for complete Unicode support
- If you get errors about missing LaTeX packages (like `framed.sty`), install the full MacTeX: `brew install --cask mactex`
