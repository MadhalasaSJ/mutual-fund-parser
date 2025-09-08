# Mutual Fund Parser

A Python tool to extract structured JSON data (text, tables, charts, and fund metadata) from mutual fund factsheet PDFs.
Built using PyMuPDF, pdfplumber, pandas, and regex, this parser converts unstructured PDFs into machine-readable JSON for further analysis or integration.

## Features

⮕ Extracts fund metadata (name, category, benchmarks, expense ratios, managers, etc.)

⮕ Captures headings, sub-sections, and paragraphs

⮕ Splits long paragraphs into clean sentences

⮕ Normalizes tables (removes empty trailing cells, fixes broken words)

⮕ Adds chart placeholders for easy downstream processing

⮕ Cleans glued words like endedequity → ended equity

## Requirements

- Python 3.8+

Dependencies:
```bash
    pip install -r requirements.txt
```


requirements.txt contains:

- PyMuPDF
- pdfplumber
- pandas

## Usage

Run the parser on any factsheet PDF:
```bash
    python parse_factsheet.py --pdf input.pdf --out output.json
```

--pdf → Path to the input PDF file

--out → Path to save the extracted JSON

## Example
```bash
    python parse_factsheet.py --pdf sample.pdf --out sample_output.json
```

Produces sample_output.json:
```bash
    {
    "file_name": "sample.pdf",
    "doc_date": "May 2025",
    "fund": {
        "name": "360 ONE FOCUSED EQUITY FUND",
        "category": "An open ended equity scheme investing in maximum 30 multicap stocks",
        "benchmark": "Nifty 500 TRI",
        "managers": ["Mayur Patel", "Ashish Ongari"]
    },
    "pages": [
        {
        "page_number": 1,
        "content": [
            {"type": "heading", "text": "Equity Market Update"},
            {"type": "paragraph", "text": "Markets continued to remain volatile during May 2025..."}
        ]
        }
    ]
    }
```

## Use Cases

- Automating financial factsheet parsing

- Building data pipelines for fund analysis

- Preprocessing PDFs for ML/NLP models

## Roadmap (Future Enhancements)

- OCR support for scanned PDFs

- Improved table merging across multi-line headers

- Export to CSV/SQL for analytics platforms
