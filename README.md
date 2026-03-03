# Indexa

Auto-rename downloaded academic PDFs using a canonical filename format:

`FirstAuthor-ShortTitle-Year.pdf`

## Why we built this

This came from a very real pain point [@Tharusha-W](https://github.com/Tharusha-W) kept running into while downloading and organizing academic papers for research:

> “Why do I have to type this out every single time? There has to be a more efficient way.”

Short filenames like `FirstAuthor et al. (Year)` are fast in the moment, but later you end up reopening files just to find the exact title when you want to share them.

Adding full titles helps, but then every download turns into another tiny manual task.  
And yeah… ain’t nobody got time for that.

That constant friction is exactly why Indexa exists:  
**download PDF → auto-name it cleanly → move on.**

---

## Download (Windows)

Get the latest release here:

**https://github.com/wicksense/indexa/releases**

Download one of these:

- **Indexa-Setup.exe** → installable app (recommended for most users)
- **Indexa-windows-portable.zip** → portable version (no install)

## Quick usage (GUI)

1. Open **Indexa**
2. Pick your folder
3. Click **Preview Scan**
4. If good, click **Apply Scan**
5. (Optional) click **Start Watch** to auto-handle incoming PDFs

GUI includes:
- folder picker
- preview/apply scan
- preview/apply undo
- start/stop watch mode
- system tray support (minimize to tray)
- Launch on startup toggle (Windows)
- simple filename style presets + advanced custom template

### GUI screenshots

![Indexa GUI (latest)](assets/indexa-gui-latest.png)
![Indexa Watch Mode](assets/indexa-watch.png)

---

## What it does

- Scans a folder for PDFs
- Extracts metadata from PDF content (not from original filename)
- DOI/Crossref + arXiv lookup support
- Renames files safely (collision-aware)
- Supports dry-run mode
- Writes an undo log for applied renames

## Filename rule

Default template:

`{first_author_last}-{short_title}-{year}.pdf`

Template tokens:
- `{first_author_last}`
- `{short_title}`
- `{year}`

---

## CLI (advanced)

### Scan once

```bash
python -m indexa.cli scan <folder> --dry-run
python -m indexa.cli scan <folder> --apply
```

### Watch folder continuously

```bash
python -m indexa.cli watch <folder> --apply
```

Uses event-driven file watching (`watchdog`) when available, with fallback polling.

### Undo renames

```bash
python -m indexa.cli undo <folder> --dry-run
python -m indexa.cli undo <folder> --steps 5 --apply
python -m indexa.cli undo <folder> --apply
```

---

## Developer setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m indexa.gui
```
