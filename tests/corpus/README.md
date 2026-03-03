# Corpus-based Inference Evaluation

This folder provides a repeatable smoke/regression test for Indexa filename inference.

## 1) Build corpus

```bash
cd ~/.openclaw/workspace/indexa
source .venv/bin/activate
python tests/corpus/download_corpus.py
```

This downloads a mixed set of PDFs:
- arXiv (CS baseline)
- PLOS journals (biology/ecology)
- one legacy ecology sample (if local media file exists)
- one blank synthetic PDF (low-confidence guard)

## 2) Run evaluation

```bash
python tests/corpus/evaluate.py
```

Outputs summary metrics and writes:
- `tests/corpus/report.json`

Key checks:
- no `Unknown` / `Untitled` / `n.d` in renamed outputs
- no obvious journal-header contamination in titles
- blank synthetic file is skipped as low-confidence
- legacy ecology sample resolves to 1993
