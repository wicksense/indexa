from __future__ import annotations

import json
import shutil
from pathlib import Path

import requests
from pypdf import PdfWriter

ROOT = Path(__file__).resolve().parent
PDF_DIR = ROOT / "pdfs"
PDF_DIR.mkdir(parents=True, exist_ok=True)

SOURCES = [
    # CS baseline
    ("case01_arxiv_1706", "https://arxiv.org/pdf/1706.03762.pdf"),
    ("case02_arxiv_1810", "https://arxiv.org/pdf/1810.04805.pdf"),
    ("case03_arxiv_1512", "https://arxiv.org/pdf/1512.03385.pdf"),
    ("case04_arxiv_2006", "https://arxiv.org/pdf/2006.11239.pdf"),
    # Biology/ecology journals (PLOS)
    ("case05_plos_pone_0001248", "https://journals.plos.org/plosone/article/file?id=10.1371/journal.pone.0001248&type=printable"),
    ("case06_plos_pone_0260976", "https://journals.plos.org/plosone/article/file?id=10.1371/journal.pone.0260976&type=printable"),
    ("case07_plos_pbio_3000002", "https://journals.plos.org/plosbiology/article/file?id=10.1371/journal.pbio.3000002&type=printable"),
    ("case08_plos_pbio_3001755", "https://journals.plos.org/plosbiology/article/file?id=10.1371/journal.pbio.3001755&type=printable"),
    ("case09_plos_pone_0283902", "https://journals.plos.org/plosone/article/file?id=10.1371/journal.pone.0283902&type=printable"),
    ("case10_plos_pone_0291803", "https://journals.plos.org/plosone/article/file?id=10.1371/journal.pone.0291803&type=printable"),
]


def main() -> None:
    for f in PDF_DIR.glob("*.pdf"):
        f.unlink()

    manifest = []
    for stem, url in SOURCES:
        out = PDF_DIR / f"{stem}.pdf"
        r = requests.get(url, timeout=45)
        if r.status_code == 200 and r.content[:4] == b"%PDF":
            out.write_bytes(r.content)
            manifest.append({"file": out.name, "url": url})
            print(f"saved {out.name}")
        else:
            print(f"skip {stem}: {r.status_code}")

    # include local legacy ecology sample if available
    legacy = Path("/home/r/.openclaw/media/inbound/474a669f-74b1-4f1e-8a57-06612307a33d.pdf")
    if legacy.exists():
        dst = PDF_DIR / "case11_legacy_ecology_sample.pdf"
        shutil.copy2(legacy, dst)
        manifest.append({"file": dst.name, "url": "local media sample"})
        print(f"saved {dst.name}")

    # blank low-confidence synthetic file
    blank = PDF_DIR / "case12_blank_synthetic.pdf"
    w = PdfWriter()
    w.add_blank_page(width=300, height=300)
    with blank.open("wb") as f:
        w.write(f)
    manifest.append({"file": blank.name, "url": "synthetic"})

    (ROOT / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"wrote manifest.json ({len(manifest)} files)")


if __name__ == "__main__":
    main()
