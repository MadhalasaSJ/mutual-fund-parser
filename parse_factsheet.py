#!/usr/bin/env python3

import argparse
import json
import re
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional, Tuple


# -------------------------
# Lazy import helper
# -------------------------
def need(module: str, pipname: Optional[str] = None):
    try:
        return __import__(module)
    except Exception as e:
        raise SystemExit(f"Missing dependency: {module}. Install with: pip install {pipname or module}\n{e}")

fitz = None
pdfplumber = None
pd = None

@dataclass
class ContentItem:
    type: str
    section: Optional[str] = None
    sub_section: Optional[str] = None
    text: Optional[str] = None
    table: Optional[Dict[str, Any]] = None
    bbox: Optional[List[float]] = None
    meta: Optional[Dict[str, Any]] = None

@dataclass
class PageOut:
    page_number: int
    content: List[ContentItem]

# -------------------------
# Helpers
# -------------------------
def clean_text(t: str) -> str:
    
    if not t:
        return ""

    
    t = t.replace("\t", " ")
    t = re.sub(r"[\u00A0\u2007\u202F]", " ", t)  

    
    t = re.sub(r"(\w)-\s+(\w)", r"\1\2", t)

    
    t = re.sub(r"\s+", " ", t)

    
    t = re.sub(r"([a-z])([A-Z])", r"\1 \2", t)  # lower->Upper
    t = re.sub(r"([A-Za-z])(\d)", r"\1 \2", t)  # letter+digit
    t = re.sub(r"(\d)([A-Za-z])", r"\1 \2", t)  # digit+letter

    return t.strip()

def fix_glued_domain_terms(text: str) -> str:
    
    if not text:
        return text
    fixes = {
        r"\bopenended\b": "open ended",
        r"\bendedequity\b": "ended equity",
        r"\bequityscheme\b": "equity scheme",
        r"\bschemeinvesting\b": "scheme investing",
        r"\binvestingin\b": "investing in",
        r"\binmaximum\b": "in maximum",
        r"\bmulticapstocks\b": "multicap stocks",
        r"\bmutualfundinvestmentsaresubjecttomarketrisks\b": "Mutual Fund investments are subject to market risks",
        r"\breadallschemerelateddocumentscarefully\b": "read all scheme related documents carefully",
    }
    for pat, rep in fixes.items():
        text = re.sub(pat, rep, text, flags=re.IGNORECASE)
    return text

def is_noise(text: str) -> bool:
    
    if not text:
        return False
    compact = re.sub(r"[^A-Za-z]", "", text).lower()
    noise_compact = [
        "mutualfundinvestmentsaresubjecttomarketrisks",
        "readallschemerelateddocumentscarefully",
    ]
    if any(n in compact for n in noise_compact):
        return True
    if re.search(r"^\s*Page\s*\|?\s*\d+\s*$", text, re.IGNORECASE):
        return True
    if re.search(r"Page\s*\d+", text, re.IGNORECASE):
        return True
    return False

def open_doc(path: str):
    global fitz
    fitz = need("fitz", "PyMuPDF")
    return fitz.open(path)

def extract_blocks(doc) -> List[List[Dict[str, Any]]]:
    pages_blocks = []
    for page in doc:
        blocks = page.get_text("dict").get("blocks", [])
        text_blocks = [b for b in blocks if "lines" in b]
        pages_blocks.append(text_blocks)
    return pages_blocks

# -------------------------
# Heading detection
# -------------------------
def classify_spans_as_headings(block: Dict[str, Any], size_threshold: float = 11.0) -> List[Tuple[str, Dict[str, Any]]]:
    labeled = []
    for line in block.get("lines", []):
        for span in line.get("spans", []):
            text = clean_text(span.get("text") or "")
            if not text:
                continue
            size = span.get("size", 10.0)
            if size >= size_threshold or (text.isupper() and len(text.split()) <= 6):
                labeled.append(("heading", span))
            else:
                labeled.append(("body", span))
    return labeled

# -------------------------
# Group content per page
# -------------------------
def group_page_content(doc, blocks_per_page) -> List[PageOut]:
    out: List[PageOut] = []
    for i, page in enumerate(doc):
        blocks = blocks_per_page[i]
        blocks_sorted = sorted(blocks, key=lambda b: (b.get("bbox", [0,0,0,0])[1], b.get("bbox", [0,0,0,0])[0]))

        items: List[ContentItem] = []
        current_section = None
        current_sub = None

        def push_text(as_heading: bool, text: str, bbox):
            nonlocal current_section, current_sub, items
            if text is None:
                return
            txt = clean_text(text)
            txt = fix_glued_domain_terms(txt)
            if not txt or is_noise(txt):
                return
            if as_heading:
                if current_section is None:
                    current_section = txt
                    items.append(ContentItem(type="heading", section=current_section, text=txt, bbox=bbox))
                else:
                    current_sub = txt
                    items.append(ContentItem(type="heading", section=current_section, sub_section=current_sub, text=txt, bbox=bbox))
            else:
                # improved paragraph splitting
                if len(txt) > 600:
                    parts = re.split(r'(?<=[.!?])\s+(?=[A-Z])', txt)
                    for part in parts:
                        part = part.strip()
                        if part:
                            items.append(ContentItem(type="paragraph", section=current_section, sub_section=current_sub, text=part, bbox=bbox))
                else:
                    items.append(ContentItem(type="paragraph", section=current_section, sub_section=current_sub, text=txt, bbox=bbox))

        # add text blocks
        for b in blocks_sorted:
            labels = classify_spans_as_headings(b)
            buf_type = None
            buf_text: List[str] = []
            x0, y0, x1, y1 = b.get("bbox", [0, 0, 0, 0])
            for lab, span in labels:
                t = clean_text(span.get("text", ""))
                if not t:
                    continue
                typ = "heading" if lab == "heading" else "body"
                if buf_type is None:
                    buf_type = typ
                    buf_text = [t]
                elif typ != buf_type:
                    push_text(buf_type == "heading", " ".join(buf_text), [x0, y0, x1, y1])
                    buf_text = [t]
                    buf_type = typ
                else:
                    buf_text.append(t)
            if buf_text:
                push_text(buf_type == "heading", " ".join(buf_text), [x0, y0, x1, y1])

        # add chart placeholders
        try:
            for img in page.get_images(full=True):
                items.append(ContentItem(
                    type="chart",
                    section=current_section,
                    sub_section=current_sub,
                    text="Chart/graph detected",
                    bbox=[0, 0, 0, 0],
                    meta={"note": "placeholder for chart"}
                ))
        except Exception:
            pass

        out.append(PageOut(page_number=i + 1, content=items))
    return out

# -------------------------
# Table extraction + normalization
# -------------------------
def normalize_table(tbl: Dict[str, Any]) -> Dict[str, Any]:
    def clean_cell(c):
        if c is None:
            return ""
        s = str(c)
        s = clean_text(s)
        s = fix_glued_domain_terms(s)
        return s.strip()

    headers = [clean_cell(h) for h in tbl.get("headers", [])]

    def merge_fragments(row):
        merged = []
        i = 0
        while i < len(row):
            cur = row[i]
            if i + 1 < len(row):
                nxt = row[i + 1]
                cond_short = (len(cur) <= 4 and len(nxt) <= 6)
                cond_alpha_cont = (re.match(r".*[A-Za-z]$", cur) and re.match(r"^[a-z]{1,6}$", nxt))
                cond_percent_split = (cur.strip().endswith("%Yo") and nxt.strip().startswith("Y"))
                if cond_short or cond_alpha_cont or cond_percent_split:
                    row[i + 1] = (cur + " " + nxt).strip()
                    i += 1
                    continue
            merged.append(cur)
            i += 1
        return merged

    hdrs_merged = merge_fragments(headers)

    rows = []
    for raw_row in tbl.get("rows", []):
        cleaned = [clean_cell(c) for c in raw_row]
        cleaned = merge_fragments(cleaned)
        while cleaned and cleaned[-1] == "":
            cleaned.pop()
        rows.append(cleaned)

    return {"headers": hdrs_merged, "rows": rows}

def extract_tables(path: str) -> Dict[int, List[Dict[str, Any]]]:
    global pdfplumber, pd
    pdfplumber = need("pdfplumber")
    pd = need("pandas")
    tables_by_page: Dict[int, List[Dict[str, Any]]] = {}

    with pdfplumber.open(path) as pdf:
        for i, page in enumerate(pdf.pages):
            page_tables = []
            strategies = [
                {"vertical_strategy": "lines", "horizontal_strategy": "lines"},
                {"vertical_strategy": "text", "horizontal_strategy": "text"},
            ]
            seen_keys = set()
            for mode in strategies:
                try:
                    tables = page.extract_tables(table_settings=mode)
                except Exception:
                    tables = None
                for tbl in tables or []:
                    if not tbl or all((cell is None or str(cell).strip() == "" for row in tbl for cell in row)):
                        continue
                    header = [cell if cell is not None else "" for cell in tbl[0]]
                    rows = [[cell if cell is not None else "" for cell in row] for row in tbl[1:]]
                    norm = normalize_table({"headers": header, "rows": rows})
                    key = (tuple(norm["headers"]), len(norm["rows"]))
                    if key in seen_keys:
                        continue
                    seen_keys.add(key)
                    page_tables.append(norm)
            if page_tables:
                tables_by_page[i] = page_tables
    return tables_by_page

# -------------------------
# Merge tables
# -------------------------
def merge_tables_into_pages(pages: List[PageOut], tables_by_page: Dict[int, List[Dict[str, Any]]]):
    for i, page in enumerate(pages):
        if i in tables_by_page:
            for t in tables_by_page[i]:
                page.content.append(ContentItem(type="table", table=t, text=None, bbox=None))
        def sort_key(ci: ContentItem):
            y = 1e9
            if ci.bbox and isinstance(ci.bbox, (list, tuple)) and len(ci.bbox) >= 2:
                try:
                    y = float(ci.bbox[1])
                except Exception:
                    y = 1e9
            order = {"heading": 0, "paragraph": 1, "table": 2, "chart": 3}.get(ci.type, 4)
            return (order, y)
        page.content = sorted(page.content, key=sort_key)

# -------------------------
# Metadata extraction
# -------------------------
def extract_fund_metadata_from_content(pages: List[PageOut], cover_text: str) -> dict:
    meta = {
        "name": None,
        "category": None,
        "aum_crore": None,
        "monthly_avg_aum": None,
        "expense_ratio_regular": None,
        "expense_ratio_direct": None,
        "benchmark": None,
        "additional_benchmark": None,
        "date_of_allotment": None,
        "managers": [],
        "doc_date": None,
    }

    m = re.search(r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}", cover_text)
    if m:
        meta["doc_date"] = m.group(0)

    seen_managers = set()
    buffer = ""

    for p in pages:
        for c in p.content:
            if c.type not in ("paragraph", "heading") or not c.text:
                continue
            text = clean_text(c.text)
            text = fix_glued_domain_terms(text)

            if is_noise(text):
                continue

            if not meta["name"]:
                if "FUND" in text.upper() and len(text) < 120 and not text.upper().startswith("JUNE"):
                    n = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
                    meta["name"] = " ".join(n.split()).strip()
                    continue

            if meta.get("name") and not meta.get("category"):
                raw = text.strip()
                if raw.startswith("(") and raw.endswith(")"):
                    cat = clean_text(raw[1:-1].strip())
                    cat = fix_glued_domain_terms(cat)
                    meta["category"] = " ".join(cat.split()).strip()
                    continue

            if not meta.get("date_of_allotment"):
                m = re.search(r"Date of Allotment\s*[:\-]?\s*([A-Za-z]+\s+\d{1,2},\s+\d{4})", text)
                if m:
                    meta["date_of_allotment"] = m.group(1)

            if not meta.get("benchmark"):
                m = re.search(r"Benchmark(?: Index)?\s*[:\-]?\s*([A-Za-z0-9\s\-\&]+)", text)
                if m:
                    bench = re.sub(r"([a-z])([A-Z])", r"\1 \2", m.group(1))
                    meta["benchmark"] = " ".join(bench.split())

            if not meta.get("additional_benchmark"):
                m = re.search(r"Additional Benchmark(?: Index)?\s*[:\-]?\s*([A-Za-z0-9\s\-\&]+)", text)
                if m:
                    add_bench = re.sub(r"([a-z])([A-Z])", r"\1 \2", m.group(1))
                    meta["additional_benchmark"] = " ".join(add_bench.split())

            if not meta.get("aum_crore"):
                m = re.search(r"Net AUM\s*[:\-]?\s*[₹` ]*([\d,]+\.?\d*)\s*crore", text, re.IGNORECASE)
                if m:
                    try:
                        meta["aum_crore"] = float(m.group(1).replace(",", ""))
                    except Exception:
                        pass

            if not meta.get("monthly_avg_aum"):
                m = re.search(r"Monthly Average AUM\s*[:\-]?\s*[₹` ]*([\d,]+\.?\d*)\s*crore", text, re.IGNORECASE)
                if m:
                    try:
                        meta["monthly_avg_aum"] = float(m.group(1).replace(",", ""))
                    except Exception:
                        pass

            if not meta.get("expense_ratio_regular"):
                m = re.search(r"Regular Plan\s*[:\-]?\s*([\d\.]+)%", text, re.IGNORECASE)
                if m:
                    try:
                        meta["expense_ratio_regular"] = float(m.group(1))
                    except Exception:
                        pass

            if not meta.get("expense_ratio_direct"):
                m = re.search(r"Direct Plan\s*[:\-]?\s*([\d\.]+)%", text, re.IGNORECASE)
                if m:
                    try:
                        meta["expense_ratio_direct"] = float(m.group(1))
                    except Exception:
                        pass

            if re.search(r"Fund Manager", text, re.IGNORECASE):
                buffer += " " + text
                matches = re.findall(r"(?:Fund Manager|Co-? ?Fund Manager)\s*(?:[:\-]?)\s*(?:Mr\.|Ms\.|Mrs\.)?\s*([A-Z][A-Za-z\.\- ]{2,})", buffer)
                for mname in matches:
                    name = re.sub(r"\b(Equity|Debt|Hybrid|Fixed Income)\b", "", mname).strip()
                    name = re.sub(r"\([^)]*\)", "", name).strip()
                    name = " ".join(name.split())
                    name = re.sub(r"^(Mr\.|Ms\.|Mrs\.)\s*", "", name)
                    if name and name not in seen_managers:
                        seen_managers.add(name)
                        meta["managers"].append(name)
                buffer = ""
                continue

            if buffer and text.startswith("Mr."):
                buffer += " " + text
                matches = re.findall(r"Mr\.?\s*([A-Z][A-Za-z\.\- ]{2,})", buffer)
                for mname in matches:
                    name = re.sub(r"\b(Equity|Debt|Hybrid|Fixed Income)\b", "", mname).strip()
                    name = re.sub(r"\([^)]*\)", "", name).strip()
                    name = " ".join(name.split())
                    name = re.sub(r"^(Mr\.|Ms\.|Mrs\.)\s*", "", name)
                    if name and name not in seen_managers:
                        seen_managers.add(name)
                        meta["managers"].append(name)
                buffer = ""

    return meta

# -------------------------
# Main parse flow
# -------------------------
def parse(pdf_path: str) -> Dict[str, Any]:
    doc = open_doc(pdf_path)
    cover_text = ""
    if len(doc) > 0:
        try:
            cover_text = doc[0].get_text("text")
        except Exception:
            cover_text = ""

    blocks_per_page = extract_blocks(doc)
    pages = group_page_content(doc, blocks_per_page)
    tables = extract_tables(pdf_path)
    merge_tables_into_pages(pages, tables)
    fund_meta = extract_fund_metadata_from_content(pages, cover_text)

    return {
        "file_name": pdf_path.split("/")[-1],
        "doc_date": fund_meta.pop("doc_date", None),
        "fund": fund_meta,
        "pages": [
            {"page_number": p.page_number, "content": [asdict(c) for c in p.content]} for p in pages
        ],
    }

# -------------------------
# CLI
# -------------------------
def main():
    ap = argparse.ArgumentParser(description="Parse factsheet PDF into structured JSON")
    ap.add_argument("--pdf", required=True, help="Path to factsheet PDF")
    ap.add_argument("--out", required=True, help="Path to output JSON")
    args = ap.parse_args()

    data = parse(args.pdf)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Wrote {args.out}")

if __name__ == "__main__":
    main()
