# Indexa

Auto-rename downloaded journal PDFs using a canonical filename format:

`FirstAuthor-ShortTitle-Year.pdf`

## What it does

- Scans a folder for PDFs
- Extracts metadata from embedded PDF fields first
- Falls back to text extraction + DOI lookup via Crossref
- Renames files safely (collision-aware)
- Supports dry-run mode
- Writes an undo log for all applied renames
- Optional watch mode for continuously renaming new downloads

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## GUI (recommended)

Run:

```bash
python -m indexa.gui
```

GUI includes:
- folder picker
- preview/apply scan
- preview/apply undo
- start/stop watch mode
- system tray support (minimize to tray)
- Windows autostart toggle (Run key)
- simple filename style presets + advanced custom template
- title-word / interval / undo-log controls

### GUI screenshots

![Indexa GUI (latest)](assets/indexa-gui-latest.png)
![Indexa Watch Mode](assets/indexa-watch.png)

## Windows packaging / release

We currently ship a **Windows EXE** via GitHub Actions.

- Workflow: `.github/workflows/windows-release.yml`
- Trigger options:
  - manual: Actions → **Windows Release** → Run workflow
  - release tag: push `v*` tag (e.g. `v0.1.0`)

Tag release flow:

```bash
git tag v0.1.0
git push origin v0.1.0
```

After CI completes, download `Indexa-windows.zip` from the release assets.

## CLI

### Scan once

```bash
# preview
python -m indexa.cli scan ~/Downloads/indexa-test --dry-run

# apply
python -m indexa.cli scan ~/Downloads/indexa-test --apply
```

### Watch folder continuously

```bash
python -m indexa.cli watch <folder> --apply
```

Uses event-driven file watching (`watchdog`) + stable-file checks by default.
If watchdog is unavailable, it falls back to interval polling (`--interval`, default 3s).

Stop with `Ctrl+C`.

### Undo renames

```bash
# Preview undo for all logged renames
python -m indexa.cli undo <folder> --dry-run

# Undo last 5 renames
python -m indexa.cli undo <folder> --steps 5 --apply

# Undo all renames in the log
python -m indexa.cli undo <folder> --apply
```

## Filename rule

Default template:

`{first_author_last}-{short_title}-{year}.pdf`

Template tokens:
- `{first_author_last}`
- `{short_title}`
- `{year}`

The `--title-words` flag controls how many title words are kept (default: `8`).

Sanitization removes filesystem-hostile characters and truncates long tokens.
