from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

import requests
from pypdf import PdfReader


def _sanitize(s: str, max_len: int = 80) -> str:
    s = re.sub(r"[^A-Za-z0-9 _.-]", "", s)
    s = re.sub(r"\s+", " ", s).strip().replace(" ", "")
    return s[:max_len] if s else "Untitled"


def _extract_pdf_metadata(pdf_path: Path) -> tuple[Optional[str], Optional[str], Optional[str]]:
    reader = PdfReader(str(pdf_path))
    meta = reader.metadata or {}

    title = (getattr(meta, "title", None) or (meta.get("/Title") if hasattr(meta, "get") else None) or None)
    author = (getattr(meta, "author", None) or (meta.get("/Author") if hasattr(meta, "get") else None) or None)

    year = None
    created = meta.get("/CreationDate") if hasattr(meta, "get") else None
    if created:
        m = re.search(r"(19|20)\d{2}", str(created))
        if m:
            year = m.group(0)

    return author, title, year


def _extract_first_page_text(pdf_path: Path, max_chars: int = 12000) -> str:
    try:
        reader = PdfReader(str(pdf_path))
        if not reader.pages:
            return ""
        text = reader.pages[0].extract_text() or ""
        return text[:max_chars]
    except Exception:
        return ""


def _extract_doi_from_text(text: str) -> Optional[str]:
    m = re.search(r"10\.\d{4,9}/[-._;()/:A-Za-z0-9]+", text)
    return m.group(0).rstrip(".,;) ") if m else None


def _extract_filename_hints(pdf_path: Path) -> tuple[Optional[str], Optional[str]]:
    """Try to recover year/title from raw filename like:
    2021-Recent trends in crowd analysis A review.pdf
    """
    stem = pdf_path.stem.replace("_", " ")

    year = None
    ym = re.match(r"^\s*((19|20)\d{2})\s*[- ]\s*(.+)$", stem)
    if ym:
        year = ym.group(1)
        title = ym.group(3).strip()
        return year, title or None

    m = re.search(r"(19|20)\d{2}", stem)
    if m:
        year = m.group(0)

    return year, stem.strip() or None


def _extract_title_from_text(text: str) -> Optional[str]:
    # Heuristic: first substantial non-junk line in the first page
    for raw in text.splitlines()[:40]:
        line = re.sub(r"\s+", " ", raw).strip()
        if not line:
            continue
        if len(line) < 20:
            continue
        if re.search(r"\b(doi|abstract|keywords|introduction)\b", line, re.I):
            continue
        if re.fullmatch(r"[A-Z\s]{8,}", line):
            # all-caps headers are often venue metadata
            continue
        return line
    return None


def _crossref_lookup_doi(doi: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
    try:
        url = f"https://api.crossref.org/works/{doi}"
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        return _parse_crossref_message(r.json().get("message", {}))
    except Exception:
        return None, None, None


def _crossref_lookup_title(title: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
    try:
        params = {"query.title": title, "rows": 1}
        r = requests.get("https://api.crossref.org/works", params=params, timeout=15)
        r.raise_for_status()
        items = r.json().get("message", {}).get("items", [])
        if not items:
            return None, None, None
        return _parse_crossref_message(items[0])
    except Exception:
        return None, None, None


def _parse_crossref_message(msg: dict) -> tuple[Optional[str], Optional[str], Optional[str]]:
    title = (msg.get("title") or [None])[0]
    authors = msg.get("author") or []
    author = None
    if authors:
        first = authors[0]
        author = first.get("family") or first.get("name")

    year = None
    for field in ("issued", "published-print", "published-online", "created"):
        date_parts = (msg.get(field, {}) or {}).get("date-parts", [])
        if date_parts and date_parts[0]:
            year = str(date_parts[0][0])
            break

    return author, title, year


def _short_title(title: str, max_words: int = 8) -> str:
    words = re.findall(r"[A-Za-z0-9]+", title)
    return "".join(words[:max_words]) or "Untitled"


def _first_author_last(author: Optional[str]) -> str:
    if not author:
        return "Unknown"

    a = re.sub(r"\s+", " ", str(author)).strip()

    # Common multi-author separators in PDF metadata
    if " and " in a:
        a = a.split(" and ", 1)[0].strip()
    if ";" in a:
        a = a.split(";", 1)[0].strip()

    # If metadata is like "Last, First", keep Last
    if "," in a:
        left, right = [x.strip() for x in a.split(",", 1)]
        if left and right:
            return left

    parts = a.split()
    if len(parts) > 1:
        return parts[-1]

    # Handle squashed CamelCase names like "MohammadAsifulHossain"
    camel_parts = re.findall(r"[A-Z][a-z]+", a)
    if len(camel_parts) >= 2:
        return camel_parts[-1]

    return parts[0] if parts else "Unknown"


def _build_filename(author: Optional[str], title: Optional[str], year: Optional[str]) -> str:
    author_last = _first_author_last(author)
    title_short = _short_title(title or "Untitled")
    year_part = year or "n.d"
    return f"{_sanitize(author_last)}-{_sanitize(title_short)}-{_sanitize(year_part)}.pdf"


def _dedupe_path(target: Path) -> Path:
    if not target.exists():
        return target
    stem = target.stem
    suffix = target.suffix
    i = 2
    while True:
        candidate = target.with_name(f"{stem}-{i}{suffix}")
        if not candidate.exists():
            return candidate
        i += 1


def scan_and_rename(folder: str, dry_run: bool = True) -> None:
    base = Path(folder).expanduser().resolve()
    pdfs = sorted(base.glob("*.pdf"))

    if not pdfs:
        print(f"No PDFs found in {base}")
        return

    for pdf in pdfs:
        author, title, year = _extract_pdf_metadata(pdf)
        fname_year, fname_title = _extract_filename_hints(pdf)
        first_page_text = _extract_first_page_text(pdf)

        # Year: prefer filename year over PDF creation year (often wrong for downloaded copies)
        year = fname_year or year

        if not title or title.strip().lower() in {"untitled", "untitled document"}:
            title = fname_title or _extract_title_from_text(first_page_text)

        # DOI lookup (best quality metadata)
        doi = _extract_doi_from_text(first_page_text)
        if doi:
            a2, t2, y2 = _crossref_lookup_doi(doi)
            author = author or a2
            title = title or t2
            year = year or y2

        # Title-only lookup as fallback when author still missing
        if (not author or author.strip().lower() == "unknown") and title:
            a3, t3, y3 = _crossref_lookup_title(title)
            author = author or a3
            # keep local title unless it's weak
            if title.lower() in {"untitled", "unknown"}:
                title = t3 or title
            year = year or y3

        new_name = _build_filename(author, title, year)
        target = _dedupe_path(pdf.with_name(new_name))

        if target.name == pdf.name:
            print(f"SKIP  {pdf.name}")
            continue

        print(f"{'PLAN' if dry_run else 'MOVE'}  {pdf.name} -> {target.name}")
        if not dry_run:
            pdf.rename(target)
