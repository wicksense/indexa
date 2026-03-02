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

    title = getattr(meta, "title", None) or meta.get("/Title") if hasattr(meta, "get") else None
    author = getattr(meta, "author", None) or meta.get("/Author") if hasattr(meta, "get") else None

    year = None
    subj = meta.get("/CreationDate") if hasattr(meta, "get") else None
    if subj and len(subj) >= 6:
        m = re.search(r"(19|20)\d{2}", subj)
        if m:
            year = m.group(0)

    return author, title, year


def _extract_doi_from_first_page(pdf_path: Path) -> Optional[str]:
    try:
        reader = PdfReader(str(pdf_path))
        if not reader.pages:
            return None
        text = (reader.pages[0].extract_text() or "")[:5000]
        m = re.search(r"10\.\d{4,9}/[-._;()/:A-Za-z0-9]+", text)
        return m.group(0).rstrip(".,;) ") if m else None
    except Exception:
        return None


def _crossref_lookup(doi: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
    try:
        url = f"https://api.crossref.org/works/{doi}"
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        msg = r.json().get("message", {})

        title = (msg.get("title") or [None])[0]
        authors = msg.get("author") or []
        author = None
        if authors:
            first = authors[0]
            author = first.get("family") or first.get("name")
        year = None
        issued = msg.get("issued", {}).get("date-parts", [])
        if issued and issued[0]:
            year = str(issued[0][0])
        return author, title, year
    except Exception:
        return None, None, None


def _short_title(title: str, max_words: int = 8) -> str:
    words = re.findall(r"[A-Za-z0-9]+", title)
    return "".join(words[:max_words]) or "Untitled"


def _build_filename(author: Optional[str], title: Optional[str], year: Optional[str]) -> str:
    author_last = (author or "Unknown").split()[-1]
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

        if not (author and title and year):
            doi = _extract_doi_from_first_page(pdf)
            if doi:
                a2, t2, y2 = _crossref_lookup(doi)
                author = author or a2
                title = title or t2
                year = year or y2

        new_name = _build_filename(author, title, year)
        target = _dedupe_path(pdf.with_name(new_name))

        if target.name == pdf.name:
            print(f"SKIP  {pdf.name}")
            continue

        print(f"{'PLAN' if dry_run else 'MOVE'}  {pdf.name} -> {target.name}")
        if not dry_run:
            pdf.rename(target)
