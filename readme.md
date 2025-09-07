360ONE Factsheet Parser
-----------------------

This project contains a Python script to extract structured JSON data from 360ONE
mutual fund factsheet PDF files.

Requirements
------------
- Python 3.8 or higher
- Install dependencies by running:

    pip install PyMuPDF pdfplumber pandas

How to Run
----------
1. Place the PDF factsheet in the same folder as the script (or note its path).
2. Run the script from the command line:

    python parse_factsheet.py --pdf input.pdf --out output.json

   where:
   - input.pdf  = path to the PDF factsheet file
   - output.json = path where the JSON output will be saved

Output
------
The script produces a JSON file with:
- Fund metadata (name, category, AUM, expense ratios, benchmarks, managers, etc.)
- Page-level structured content:
  * Headings
  * Paragraphs (long text is split into sentences)
  * Tables (rows and columns normalized, extra empty cells removed)
  * Chart placeholders (detected but not extracted)

Example
-------
    python parse_factsheet.py --pdf "[Fund Factsheet - May]360ONE-MF-May 2025.pdf.pdf" --out out.json

This will create "out.json" containing the structured representation of the PDF.
