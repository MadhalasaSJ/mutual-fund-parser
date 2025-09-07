# PDF to JSON Parser (Starter)

## 1) Setup
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## 2) Run
```bash
python parse_factsheet.py --pdf "/path/to/360ONE-MF-May 2025.pdf.pdf" --out out.json
```

## 3) Customize Heuristics
- Tweak `size_threshold` in `classify_spans_as_headings`.
- Improve table extraction strategies in `extract_tables`.
- Add regex rules to populate `fund` fields from Page 1.