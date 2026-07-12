# FacturaAI 2.0

Invoice automation for a Spanish bar business — watches a folder + Gmail for
PDF invoices, classifies and extracts them automatically (no manual
per-supplier setup), archives them locally and/or to OneDrive, maintains a
SQLite ledger, and generates Modelo 303/390/130/100 tax report drafts
through a Flask dashboard.

## What's new vs. FacturaAI 1.0

v1 required you to drop a sample invoice into a Claude Code session and ask
it to hand-write a parser every time a new supplier showed up. 2.0 automates
that:

- **Factura detection** — every incoming PDF is classified as a known
  supplier, a new-supplier invoice, or not an invoice at all (receipts,
  contracts, etc. get moved to `rejected/`, never mixed into the ledger).
- **Automatic extractor generation** — new-supplier invoices get a
  Claude-written parser, self-tested in an isolated subprocess, and
  promoted into the live pipeline automatically. The first invoice from
  that supplier still goes to `manual_review/` for a one-time confirmation
  (configurable).
- **AI plausibility review** — every extraction is sanity-checked against
  the raw invoice text (catches things like OCR decimal-shift errors that
  the deterministic VAT/spike checks alone wouldn't).
- **OneDrive archiving**, alongside or instead of local folders.
- **Modelo 130 and 100** report drafts, in addition to v1's 303 and 390.

---

## Requirements

- Windows 10+ or macOS 11.7+
- Python 3.10+
- An Anthropic API key ([console.anthropic.com](https://console.anthropic.com))
- Tesseract + Ghostscript (for OCR on scanned invoices) — `scripts/install.py` checks for these and tells you how to get them if missing

---

## 1 — Install

```bash
git clone <this repo>   # or copy the folder
cd "FacturaAI 2.0"
python scripts/install.py
```

This creates a `.venv`, installs Python dependencies (skipping anything
already satisfied), checks for Tesseract/Ghostscript, copies
`config/config.example.yaml` → `config/config.yaml` if you don't already
have one, and creates the working directory tree. Safe to re-run — every
step checks whether it's already done before doing it.

Add `--service` to also register a background service (launchd on macOS,
Task Scheduler on Windows) so FacturaAI starts automatically. Without it,
start manually with `python main.py` whenever you want it running — for a
low-volume mailbox this is often enough; see "Manual vs. scheduled" below.

## 2 — Anthropic API key

```bash
export ANTHROPIC_API_KEY=sk-ant-...        # macOS/Linux
setx ANTHROPIC_API_KEY "sk-ant-..."        # Windows (new shells pick this up)
```

Never put this in `config.yaml` — it's read from the environment only.

## 3 — Config

Edit `config/config.yaml`:

- `ai.enabled` — set `false` to disable classification/codegen/plausibility
  entirely and fall back to v1's old behaviour (unmatched invoices just go
  to `manual_review/` at zero confidence, no factura/non-factura judgement).
- `ai.auto_trust_new_extractors` — leave `false` until you trust the
  pipeline; `true` skips the manual-review checkpoint for newly generated
  extractors.
- `processing.output_destination` — `local` (default), `onedrive`, or `both`.
- `processing.ocr_tesseract_dir` — Windows only, point this at your
  Tesseract install folder if it's not on PATH.
- `gmail.enabled` / `onedrive.enabled` — see setup steps below.

## 4 — Gmail API access (optional — only if you want Gmail polling)

1. [Google Cloud Console](https://console.cloud.google.com/) → new project → enable the **Gmail API**.
2. Set up an OAuth consent screen (internal if it's a Workspace account, external if personal Gmail).
3. Create OAuth 2.0 credentials, type **Desktop app** → download the JSON as `config/gmail_credentials.json`.
4. Scopes: `gmail.readonly` is enough to search and download attachments; the code currently requests `gmail.modify` as well so it can mark messages as read after processing — drop that scope in `gmail_poller.py` if you'd rather it not touch your mailbox at all.
5. Set `gmail.enabled: true` in `config.yaml`.
6. First run pops one browser consent screen; after that a refresh token is cached in `config/gmail_token.json` and it won't ask again.

## 5 — OneDrive / Microsoft Graph access (optional — only if `processing.output_destination` includes `onedrive`)

1. [Azure Portal](https://portal.azure.com/) → Azure Active Directory → App registrations → new registration. Note the **Application (client) ID** and **Directory (tenant) ID**.
2. Under **Authentication** → Advanced settings, set "Allow public client flows" to **Yes** (this lets the script sign in via a browser without needing a client secret).
3. Under **API permissions** → Microsoft Graph → delegated `Files.ReadWrite` (or `Files.ReadWrite.All` to write outside the app's own OneDrive folder). Grant admin consent if it's a work/school account; personal Microsoft accounts skip that step.
4. Fill in `onedrive.client_id` and `onedrive.tenant_id` in `config.yaml`, and set `onedrive.enabled: true`.
5. First upload pops one browser consent screen; after that a token is cached at `onedrive.token_cache_file` and it won't ask again.

(`onedrive.client_secret_file` in the config is only needed if you set up a confidential/web-app registration instead of a public client — most setups won't need it.)

## 6 — One-time historical import (optional)

If you have invoices already sitting in the mailbox from before FacturaAI:

```bash
python scripts/backfill_gmail.py                  # everything
python scripts/backfill_gmail.py --since 2024-01-01
python scripts/backfill_gmail.py --since 2024-01-01 --until 2024-03-01
```

Pulls every PDF attachment in the mailbox (not just "unprocessed" mail),
classifies each one, and runs it through the same pipeline as live mail.
Not every PDF attachment will turn out to be an invoice — the classifier
sorts that out, and the `rejected/` folder ending up non-empty afterward is
expected, not a bug. Safe to interrupt and re-run; already-archived
invoices are skipped automatically.

Same thing without a terminal: on the dashboard's **Status** page there's a
"Check Gmail" button with From/To date fields — runs the same backfill in
the background and shows live progress. Only one check can run at a time
(dashboard or terminal); starting a second while one is in flight is
rejected rather than queued.

## 7 — Manual run / dashboard

```bash
python main.py
```

Dashboard: [http://127.0.0.1:5000](http://127.0.0.1:5000)

## 8 — Health check

```bash
python scripts/health_check.py
```

## 9 — Updating

```bash
python scripts/update.py
```

Pulls the latest code (if this is a git checkout), re-checks dependencies,
restarts whichever service is registered (or reminds you to restart
`main.py` manually if none is).

---

## Manual vs. scheduled running

The Gmail mailbox this was built for is low-volume — an always-on watcher
isn't necessary. Options, roughly in order of effort:

1. Run `python main.py` by hand whenever you want a pass.
2. A daily scheduled task (cron / Task Scheduler) that runs `python main.py
   --once`-style — not currently a flag `main.py` supports, so for now use
   `--service` at install time for a persistent background service instead,
   or run it manually.
3. `--service` at install time (launchd/Task Scheduler), matching v1's
   always-on behaviour.

The local-folder watcher (`inbox/scan/` — drop a PDF in, it gets picked up
within seconds) works the same regardless of which mode you pick.

---

## Folder layout

```
FacturaAI 2.0/
├── inbox/
│   ├── scan/          ← drop PDFs here manually
│   └── gmail/          ← filled by Gmail poller / backfill script
├── output/YYYY/MM/     ← archived invoices (local)
├── manual_review/      ← low-confidence, flagged, or newly-generated-extractor invoices
├── rejected/            ← PDFs that weren't invoices at all
├── extractors/
│   ├── suppliers/       ← one file per known supplier (hand-written + AI-generated)
│   └── pending_suppliers/  ← generated extractors that failed self-test, awaiting a look
├── logs/
└── data/
    ├── facturas.db
    ├── facturas.csv
    └── facturas.xlsx
```

---

## Sanity checks

| Check | Rule |
|-------|------|
| VAT rate | Extracted VAT must be ≈ 4%, 10%, or 21% of net (±2%) |
| Spike | Total > 3× rolling monthly average → flagged |
| AI plausibility | Claude checks the extracted fields against the raw invoice text — catches things the numeric checks above can miss (e.g. a decimal-shift OCR error that still divides cleanly by a valid VAT rate) |

Flagged invoices go to `manual_review/` and are editable in the dashboard at `/review`.

To retry files in `manual_review/` after a bug fix (rather than hand-editing
each one, or re-running the whole Gmail backfill and reprocessing files
that already succeeded), use:

```bash
python scripts/reprocess_manual_review.py                       # every file in manual_review/
python scripts/reprocess_manual_review.py --file "some name.pdf" # just one
```

Runs the same extraction → classification → filing pipeline as new mail,
purely on files already downloaded — no Gmail connection is touched.
Successes move to `output/` normally; files that still need review stay in
`manual_review/` with `retry_count`/`last_retried_at` updated so it's clear
they were retried, not just untouched. Also available from the dashboard's
**Review** page (`/review`) — a "Reprocess All" button, and a per-item
"Reprocess" button for retrying just one file.

## Tax reports

`/reports/303` and `/reports/390` (quarterly/annual IVA) work exactly as in
v1. `/reports/130` (quarterly IRPF payment) and `/reports/100` (annual
business-income summary) are new — both compute correctly against expenses,
but income is currently a stub returning €0.00 (`db.get_income_for_period`)
since FacturaAI has never tracked sales/income. Wire a real source into
that one function (e.g. POS sales data, or a manual entry screen) when
you're ready; every report that needs income already calls it.
