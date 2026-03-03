from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
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


def _extract_arxiv_id_from_text(text: str) -> Optional[str]:
    # modern form: 2410.08406 or 2410.08406v1
    m = re.search(r"\b(\d{4}\.\d{4,5}(?:v\d+)?)\b", text)
    if m:
        return m.group(1)
    # explicit arXiv: prefix
    m = re.search(r"arXiv\s*:\s*(\d{4}\.\d{4,5}(?:v\d+)?)", text, re.I)
    if m:
        return m.group(1)
    return None


def _extract_filename_hints(pdf_path: Path) -> tuple[Optional[str], Optional[str]]:
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

    # Avoid treating raw ids as titles (e.g., 2410.08406v1)
    if re.fullmatch(r"\d{4}\.\d{4,5}(?:v\d+)?", stem.strip()):
        return year, None

    return year, stem.strip() or None


def _extract_title_from_text(text: str) -> Optional[str]:
    for raw in text.splitlines()[:40]:
        line = re.sub(r"\s+", " ", raw).strip()
        if not line:
            continue
        if len(line) < 20:
            continue
        if re.search(r"\b(doi|abstract|keywords|introduction)\b", line, re.I):
            continue
        if re.fullmatch(r"[A-Z\s]{8,}", line):
            continue
        return line
    return None


def _author_needs_upgrade(author: Optional[str]) -> bool:
    if not author:
        return True
    a = str(author).strip()
    if not a:
        return True
    if len(a.split()) == 1 and len(a) >= 14:
        return True
    return False


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


def _arxiv_lookup(arxiv_id: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
    try:
        url = f"https://export.arxiv.org/api/query?id_list={arxiv_id}"
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        xml = r.text

        title_m = re.search(r"<title>\s*(.*?)\s*</title>", xml, re.S)
        # first <title> is feed title; second is paper title
        titles = re.findall(r"<title>\s*(.*?)\s*</title>", xml, re.S)
        title = None
        if len(titles) >= 2:
            title = re.sub(r"\s+", " ", titles[1]).strip()

        authors = re.findall(r"<name>\s*(.*?)\s*</name>", xml, re.S)
        author = re.sub(r"\s+", " ", authors[0]).strip() if authors else None

        published = re.search(r"<published>(\d{4})-", xml)
        year = published.group(1) if published else None
        return author, title, year
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


def _name_token_last(s: str) -> str:
    parts = s.split()
    if len(parts) > 1:
        return parts[-1]
    camel_parts = re.findall(r"[A-Z][a-z]+", s)
    if len(camel_parts) >= 2:
        return camel_parts[-1]
    return parts[0] if parts else "Unknown"


def _first_author_last(author: Optional[str]) -> str:
    if not author:
        return "Unknown"

    a = re.sub(r"\s+", " ", str(author)).strip()

    if " and " in a:
        a = a.split(" and ", 1)[0].strip()
    if ";" in a:
        a = a.split(";", 1)[0].strip()

    if "," in a:
        left, right = [x.strip() for x in a.split(",", 1)]
        if left:
            return _name_token_last(left)

    return _name_token_last(a)


def _build_filename(
    author: Optional[str],
    title: Optional[str],
    year: Optional[str],
    title_words: int = 8,
    template: str = "{first_author_last}-{short_title}-{year}",
) -> str:
    values = {
        "first_author_last": _sanitize(_first_author_last(author)),
        "short_title": _sanitize(_short_title(title or "Untitled", max_words=title_words)),
        "year": _sanitize(year or "n.d"),
    }

    out = template
    for k, v in values.items():
        out = out.replace(f"{{{k}}}", v)

    # If user passes unknown tokens, keep app stable with fallback
    if "{" in out or "}" in out:
        out = f"{values['first_author_last']}-{values['short_title']}-{values['year']}"

    out = _sanitize(out, max_len=180)
    return f"{out}.pdf"


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


def _resolve_undo_log(base: Path, undo_log_path: str) -> Path:
    p = Path(undo_log_path).expanduser()
    if not p.is_absolute():
        p = base / p
    return p


def _write_undo_log(log_path: Path, src: Path, dst: Path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "from": str(src),
        "to": str(dst),
    }
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def process_file(
    pdf: Path,
    dry_run: bool = True,
    title_words: int = 8,
    undo_log_path: str = ".indexa-renames.jsonl",
    template: str = "{first_author_last}-{short_title}-{year}",
) -> bool:
    base = pdf.parent
    log_path = _resolve_undo_log(base, undo_log_path)

    author, title, year = _extract_pdf_metadata(pdf)
    fname_year, fname_title = _extract_filename_hints(pdf)
    first_page_text = _extract_first_page_text(pdf)

    year = fname_year or year

    if not title or title.strip().lower() in {"untitled", "untitled document"}:
        title = fname_title or _extract_title_from_text(first_page_text)

    doi = _extract_doi_from_text(first_page_text)
    if doi:
        a2, t2, y2 = _crossref_lookup_doi(doi)
        if _author_needs_upgrade(author):
            author = a2 or author
        else:
            author = author or a2
        title = title or t2
        year = year or y2

    # arXiv fallback (from filename or first page text)
    arxiv_id = _extract_arxiv_id_from_text(pdf.stem) or _extract_arxiv_id_from_text(first_page_text)
    if arxiv_id and (not title or _author_needs_upgrade(author) or not year):
        a4, t4, y4 = _arxiv_lookup(arxiv_id)
        if _author_needs_upgrade(author):
            author = a4 or author
        title = title or t4
        year = year or y4

    if (_author_needs_upgrade(author)) and title:
        a3, t3, y3 = _crossref_lookup_title(title)
        author = a3 or author
        if title.lower() in {"untitled", "unknown"}:
            title = t3 or title
        year = year or y3

    new_name = _build_filename(author, title, year, title_words=title_words, template=template)
    target = _dedupe_path(pdf.with_name(new_name))

    if target.name == pdf.name:
        print(f"SKIP  {pdf.name}")
        return False

    print(f"{'PLAN' if dry_run else 'MOVE'}  {pdf.name} -> {target.name}")
    if not dry_run:
        src = pdf.resolve()
        pdf.rename(target)
        _write_undo_log(log_path, src, target.resolve())
    return True


def scan_and_rename(
    folder: str,
    dry_run: bool = True,
    title_words: int = 8,
    undo_log_path: str = ".indexa-renames.jsonl",
    template: str = "{first_author_last}-{short_title}-{year}",
) -> None:
    base = Path(folder).expanduser().resolve()
    pdfs = sorted(base.glob("*.pdf"))

    if not pdfs:
        print(f"No PDFs found in {base}")
        return

    for pdf in pdfs:
        process_file(
            pdf,
            dry_run=dry_run,
            title_words=title_words,
            undo_log_path=undo_log_path,
            template=template,
        )


def undo_renames(
    folder: str,
    undo_log_path: str = ".indexa-renames.jsonl",
    steps: int = 0,
    dry_run: bool = True,
) -> None:
    base = Path(folder).expanduser().resolve()
    log_path = _resolve_undo_log(base, undo_log_path)

    if not log_path.exists():
        print(f"No undo log found at {log_path}")
        return

    lines = [ln for ln in log_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    if not lines:
        print("Undo log is empty.")
        return

    entries = [json.loads(ln) for ln in lines]
    to_undo = entries[-steps:] if steps and steps > 0 else entries

    undone = 0
    for row in reversed(to_undo):
        src = Path(row["to"])  # current location
        dst = Path(row["from"])  # original location
        if not src.exists():
            print(f"MISS  {src} (already moved/missing)")
            continue
        if dst.exists():
            dst = _dedupe_path(dst)
        print(f"{'PLAN' if dry_run else 'UNDO'}  {src.name} -> {dst.name}")
        if not dry_run:
            src.rename(dst)
            undone += 1

    if not dry_run and undone:
        keep = entries[: len(entries) - len(to_undo)] if steps and steps > 0 else []
        with log_path.open("w", encoding="utf-8") as f:
            for row in keep:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _wait_until_stable(path: Path, checks: int = 3, delay: float = 0.7) -> bool:
    """Return True once file size is stable across N checks."""
    last_size = -1
    stable = 0
    for _ in range(max(1, checks) * 6):
        if not path.exists():
            return False
        try:
            size = path.stat().st_size
        except OSError:
            return False
        if size > 0 and size == last_size:
            stable += 1
            if stable >= checks:
                return True
        else:
            stable = 0
            last_size = size
        time.sleep(max(0.2, delay))
    return False


def watch_and_rename(
    folder: str,
    dry_run: bool = True,
    title_words: int = 8,
    undo_log_path: str = ".indexa-renames.jsonl",
    interval: float = 3.0,
    template: str = "{first_author_last}-{short_title}-{year}",
) -> None:
    base = Path(folder).expanduser().resolve()
    print(f"Watching {base} for PDFs... (dry_run={dry_run})")

    try:
        from watchdog.events import FileSystemEventHandler
        from watchdog.observers import Observer
    except Exception:
        # Fallback polling mode
        seen: set[str] = set()
        print(f"watchdog not installed; using polling fallback (interval={interval}s)")
        try:
            while True:
                for pdf in sorted(base.glob("*.pdf")):
                    key = str(pdf.resolve())
                    if key in seen:
                        continue
                    seen.add(key)
                    if _wait_until_stable(pdf):
                        process_file(
                            pdf,
                            dry_run=dry_run,
                            title_words=title_words,
                            undo_log_path=undo_log_path,
                            template=template,
                        )
                time.sleep(interval)
        except KeyboardInterrupt:
            print("Stopped watch mode.")
        return

    class _PdfHandler(FileSystemEventHandler):
        def __init__(self) -> None:
            self.last_processed: dict[str, float] = {}

        def on_created(self, event):  # type: ignore[override]
            self._handle(event)

        def on_modified(self, event):  # type: ignore[override]
            self._handle(event)

        def _handle(self, event) -> None:
            if event.is_directory:
                return
            p = Path(event.src_path)
            if p.suffix.lower() != ".pdf":
                return
            key = str(p.resolve())
            now = time.time()
            # debounce bursts from download/write notifications
            if now - self.last_processed.get(key, 0) < 1.0:
                return
            self.last_processed[key] = now

            if not _wait_until_stable(p):
                return

            process_file(
                p,
                dry_run=dry_run,
                title_words=title_words,
                undo_log_path=undo_log_path,
                template=template,
            )

    observer = Observer()
    handler = _PdfHandler()
    observer.schedule(handler, str(base), recursive=False)
    observer.start()
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        observer.stop()
        observer.join(timeout=5)
        print("Stopped watch mode.")
