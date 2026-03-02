# Indexa

Auto-rename downloaded journal PDFs using a canonical filename format:

`FirstAuthor-ShortTitle-Year.pdf`

## What it does (MVP)

- Scans a folder for PDFs
- Extracts metadata from embedded PDF fields first
- Falls back to text extraction + DOI lookup via Crossref
- Renames files safely (collision-aware)
- Supports dry-run mode

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python -m indexa.cli scan ~/Downloads --dry-run
python -m indexa.cli scan ~/Downloads --apply
```

## Filename rule

Default template:

`{first_author_last}-{short_title}-{year}.pdf`

Sanitization removes filesystem-hostile characters and truncates long names.

## Status

Early prototype scaffold.
