from __future__ import annotations

import contextlib
import io
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from indexa.rename import process_file

ROOT = Path(__file__).resolve().parent
PDF_DIR = ROOT / "pdfs"
MANIFEST = ROOT / "manifest.json"

FORBIDDEN_TITLE_SNIPPETS = [
    "Contentslistsavailable",
    "ScienceDirect",
    "Journalhomepage",
    "Publishedasaconferencepaper",
    "Providedproperattribution",
    "Googleherebygrants",
    "MachineLearningwithApplications4",
]


def run_one(pdf: Path, **kwargs) -> tuple[bool, str]:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        changed = process_file(pdf, dry_run=True, **kwargs)
    return changed, buf.getvalue().strip()


def parse_target(line: str) -> str | None:
    m = re.search(r"->\s*(.+)$", line)
    return m.group(1).strip() if m else None


def evaluate(mode_name: str, **kwargs) -> dict:
    rows = []
    for pdf in sorted(PDF_DIR.glob("*.pdf")):
        changed, out = run_one(pdf, **kwargs)
        rows.append({"file": pdf.name, "changed": changed, "out": out, "target": parse_target(out)})

    renamed = [r for r in rows if r["changed"] and r["target"]]
    skipped = [r for r in rows if not r["changed"]]

    bad_unknown = [r for r in renamed if "Unknown-" in r["target"]]
    bad_untitled = [r for r in renamed if "Untitled" in r["target"]]
    bad_nd = [r for r in renamed if "-n.d" in r["target"]]
    bad_forbidden = [
        r
        for r in renamed
        if any(s.lower() in r["target"].replace(" ", "").lower() for s in FORBIDDEN_TITLE_SNIPPETS)
    ]

    legacy = next((r for r in rows if "legacy_ecology_sample" in r["file"]), None)
    legacy_ok = bool(legacy and legacy.get("target") and "-1993" in legacy["target"])

    blank = next((r for r in rows if "blank_synthetic" in r["file"] or r["file"] == "sdfsdfsd.pdf"), None)
    blank_ok = bool(blank and "low-confidence metadata" in blank.get("out", ""))

    return {
        "mode": mode_name,
        "total": len(rows),
        "renamed": len(renamed),
        "skipped": len(skipped),
        "bad_unknown": len(bad_unknown),
        "bad_untitled": len(bad_untitled),
        "bad_nd": len(bad_nd),
        "bad_forbidden": len(bad_forbidden),
        "legacy_1993": legacy_ok,
        "blank_low_conf_skip": blank_ok,
        "rows": rows,
    }


def main() -> None:
    _ = json.loads(MANIFEST.read_text())

    reports = [
        evaluate("default", title_words=8, template="{first_author_last}-{short_title}-{year}"),
        evaluate(
            "spaces_sentence",
            title_words=8,
            template="{first_author_last}-{short_title}-{year}",
            title_spacing="spaces",
            title_case="sentence",
        ),
    ]

    out_path = ROOT / "report.json"
    out_path.write_text(json.dumps(reports, indent=2))

    for rep in reports:
        print(f"== {rep['mode']} ==")
        print(
            f"total={rep['total']} renamed={rep['renamed']} skipped={rep['skipped']} "
            f"unknown={rep['bad_unknown']} untitled={rep['bad_untitled']} nd={rep['bad_nd']} forbidden={rep['bad_forbidden']}"
        )
        print(f"legacy_1993={rep['legacy_1993']} blank_low_conf_skip={rep['blank_low_conf_skip']}")


if __name__ == "__main__":
    main()
