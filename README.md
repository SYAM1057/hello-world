# CSV to SQLite Reconciliation

This repository contains a Python implementation that compares a source CSV file against a target SQLite table, identifies missing rows, extra rows, and value mismatches, and writes a reconciliation report.

## Files

- `sqlite_reconciliation.py` - CLI script to compare CSV vs SQLite table and generate a report.
- `app.py` - Gradio web app for interactive reconciliation.
- `requirements.txt` - Dependencies for local execution and Hugging Face Spaces deployment.

## Local usage

### CLI

```bash
python sqlite_reconciliation.py \
  --source-file source.csv \
  --sqlite-db target.db \
  --table target_table \
  --key-columns id \
  --compare-columns amount,date \
  --report-file reconciliation_report.csv
```

If `--compare-columns` is omitted, the script compares all non-key columns from the source CSV.

### Web UI

```bash
python app.py
```

Then open `http://127.0.0.1:7860` in your browser.

## Hugging Face Spaces deployment

1. Push this repository to GitHub (or directly to a Hugging Face repo).
2. Create a new Hugging Face Space using the `Gradio` SDK.
3. Connect the Space to this repository, or upload the repository files.
4. Ensure `requirements.txt` is present so Hugging Face installs `gradio`.
5. The Space will launch `app.py` automatically.

The Gradio app accepts a source CSV file and a SQLite database file, then compares the selected table and returns a reconciliation summary and report contents.
