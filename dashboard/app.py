import io
import logging
import os
from datetime import datetime, timezone

from flask import Flask, jsonify, make_response, redirect, render_template, request, url_for

import bank as bank_mod
import db
from categories import CATEGORY_LABELS, label as cat_label
from config.loader import get_config
from i18n import get_translations, LANGUAGES
from reports import modelo100, modelo130, modelo303, modelo390

log = logging.getLogger(__name__)
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10 MB upload limit


# ---------------------------------------------------------------------------
# i18n
# ---------------------------------------------------------------------------

@app.context_processor
def inject_i18n():
    lang = request.cookies.get("lang", "es")
    if lang not in LANGUAGES:
        lang = "es"
    return {"t": get_translations(lang), "lang": lang, "LANGUAGES": LANGUAGES}


@app.route("/lang/<code>")
def set_lang(code):
    if code not in LANGUAGES:
        code = "es"
    resp = make_response(redirect(request.referrer or "/"))
    resp.set_cookie("lang", code, max_age=60 * 60 * 24 * 365)
    return resp


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _heartbeat_age(last_seen: str) -> str:
    if not last_seen:
        return "never"
    try:
        ts = datetime.strptime(last_seen, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - ts
        mins = int(delta.total_seconds() // 60)
        return f"{mins}m ago"
    except ValueError:
        return last_seen


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    cfg = get_config()
    page = int(request.args.get("page", 1))
    page_size = cfg.get("dashboard", {}).get("page_size", 50)
    filters = {
        "supplier": request.args.get("supplier") or None,
        "date_from": request.args.get("date_from") or None,
        "date_to": request.args.get("date_to") or None,
        "amount_min": float(request.args["amount_min"]) if request.args.get("amount_min") else None,
        "amount_max": float(request.args["amount_max"]) if request.args.get("amount_max") else None,
        "needs_review": True if request.args.get("needs_review") == "1" else None,
    }
    invoices, total = db.get_all_invoices(filters, page=page, page_size=page_size)
    total_pages = max(1, (total + page_size - 1) // page_size)

    return render_template(
        "index.html",
        invoices=invoices,
        page=page,
        total_pages=total_pages,
        total_count=total,
        filters={k: v for k, v in filters.items() if v is not None},
        args=request.args,
    )


@app.route("/monthly")
def monthly():
    totals = db.get_monthly_totals()
    return render_template("monthly.html", totals=totals)


@app.route("/review")
def review():
    queue = db.get_review_queue()
    return render_template("review.html", queue=queue)


@app.route("/review/<int:invoice_id>", methods=["POST"])
def update_review(invoice_id):
    fields = {}
    for key in ("date", "supplier", "invoice_number", "net_amount",
                "vat_amount", "vat_rate", "total_amount", "currency"):
        val = request.form.get(key)
        if val is not None and val != "":
            try:
                if key in ("net_amount", "vat_amount", "vat_rate", "total_amount"):
                    fields[key] = float(val)
                else:
                    fields[key] = val
            except ValueError:
                pass
    fields["needs_review"] = 0
    db.update_invoice(invoice_id, fields)
    return redirect(url_for("review"))


@app.route("/rejected")
def rejected():
    page = int(request.args.get("page", 1))
    cfg = get_config()
    page_size = cfg.get("dashboard", {}).get("page_size", 50)
    rows, total = db.get_rejected_invoices(page=page, page_size=page_size)
    total_pages = max(1, (total + page_size - 1) // page_size)
    return render_template(
        "rejected.html", rejected=rows, page=page,
        total_pages=total_pages, total_count=total,
    )


@app.route("/health")
def health():
    last_seen = db.get_heartbeat()
    last_cycle = db.get_last_cycle()
    review_count = len(db.get_review_queue())
    return render_template(
        "health.html",
        last_seen=last_seen,
        age=_heartbeat_age(last_seen),
        last_cycle=last_cycle,
        review_count=review_count,
    )


@app.route("/api/health")
def api_health():
    last_seen = db.get_heartbeat()
    last_cycle = db.get_last_cycle()
    return jsonify({
        "last_seen": last_seen,
        "age": _heartbeat_age(last_seen),
        "last_cycle": dict(last_cycle),
        "review_count": len(db.get_review_queue()),
    })


@app.route("/clear-all", methods=["POST"])
def clear_all():
    import shutil
    cfg = get_config()
    counts = db.clear_all_data()
    # Remove processed files from output, manual_review, and rejected
    for key in ("output", "manual_review", "rejected"):
        folder = cfg["paths"].get(key)
        if folder and os.path.isdir(folder):
            shutil.rmtree(folder)
            os.makedirs(folder, exist_ok=True)
    log.warning("Dashboard clear-all: %s", counts)
    return jsonify({"ok": True, **counts})


# ---------------------------------------------------------------------------
# Reports — Modelo 303 (quarterly)
# ---------------------------------------------------------------------------

@app.route("/reports/303")
def reports_303():
    years = db.get_available_years()
    default_year, default_quarter = _default_year_quarter(years)
    year    = int(request.args.get("year",    default_year))
    quarter = int(request.args.get("quarter", default_quarter))
    report  = modelo303.generate(year, quarter)
    return render_template("reports303.html",
                           report=report, years=years,
                           selected_year=year, selected_quarter=quarter)


@app.route("/reports/303/export")
def export_303():
    year    = int(request.args.get("year",    datetime.now().year))
    quarter = int(request.args.get("quarter", _current_quarter()))
    report  = modelo303.generate(year, quarter)
    csv_text = modelo303.as_csv(report)
    resp = make_response(csv_text)
    resp.headers["Content-Type"] = "text/csv; charset=utf-8"
    resp.headers["Content-Disposition"] = (
        f'attachment; filename="modelo303_{year}_T{quarter}.csv"'
    )
    return resp


# ---------------------------------------------------------------------------
# Reports — Modelo 390 (annual)
# ---------------------------------------------------------------------------

@app.route("/reports/390")
def reports_390():
    years  = db.get_available_years()
    year   = int(request.args.get("year", years[0] if years else datetime.now().year))
    report = modelo390.generate(year)
    return render_template("reports390.html",
                           report=report, years=years, selected_year=year)


@app.route("/reports/390/export")
def export_390():
    year   = int(request.args.get("year", datetime.now().year))
    report = modelo390.generate(year)
    csv_text = modelo390.as_csv(report)
    resp = make_response(csv_text)
    resp.headers["Content-Type"] = "text/csv; charset=utf-8"
    resp.headers["Content-Disposition"] = (
        f'attachment; filename="modelo390_{year}.csv"'
    )
    return resp


# ---------------------------------------------------------------------------
# Reports — Modelo 130 (quarterly IRPF pago fraccionado)
# ---------------------------------------------------------------------------

@app.route("/reports/130")
def reports_130():
    years = db.get_available_years()
    default_year, default_quarter = _default_year_quarter(years)
    year    = int(request.args.get("year",    default_year))
    quarter = int(request.args.get("quarter", default_quarter))
    report  = modelo130.generate(year, quarter)
    return render_template("reports130.html",
                           report=report, years=years,
                           selected_year=year, selected_quarter=quarter)


@app.route("/reports/130/export")
def export_130():
    year    = int(request.args.get("year",    datetime.now().year))
    quarter = int(request.args.get("quarter", _current_quarter()))
    report  = modelo130.generate(year, quarter)
    csv_text = modelo130.as_csv(report)
    resp = make_response(csv_text)
    resp.headers["Content-Type"] = "text/csv; charset=utf-8"
    resp.headers["Content-Disposition"] = (
        f'attachment; filename="modelo130_{year}_T{quarter}.csv"'
    )
    return resp


# ---------------------------------------------------------------------------
# Reports — Modelo 100 (annual business-activity net income summary)
# ---------------------------------------------------------------------------

@app.route("/reports/100")
def reports_100():
    years  = db.get_available_years()
    year   = int(request.args.get("year", years[0] if years else datetime.now().year))
    report = modelo100.generate(year)
    return render_template("reports100.html",
                           report=report, years=years, selected_year=year)


@app.route("/reports/100/export")
def export_100():
    year   = int(request.args.get("year", datetime.now().year))
    report = modelo100.generate(year)
    csv_text = modelo100.as_csv(report)
    resp = make_response(csv_text)
    resp.headers["Content-Type"] = "text/csv; charset=utf-8"
    resp.headers["Content-Disposition"] = (
        f'attachment; filename="modelo100_{year}.csv"'
    )
    return resp


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------

@app.route("/categories")
def categories():
    years = db.get_available_years()
    year  = request.args.get("year")
    year_int = int(year) if year and year.isdigit() else None
    totals = db.get_category_totals(year=year_int)
    # Attach human-readable label
    for row in totals:
        row["label"] = cat_label(row.get("category"))
    return render_template("categories.html",
                           totals=totals, years=years,
                           selected_year=year_int)


# ---------------------------------------------------------------------------
# Bank reconciliation
# ---------------------------------------------------------------------------

@app.route("/bank")
def bank():
    page = int(request.args.get("page", 1))
    transactions, total = db.get_bank_transactions(page=page, page_size=100)
    total_pages = max(1, (total + 99) // 100)
    stats = db.get_bank_stats()
    return render_template("bank.html",
                           transactions=transactions,
                           page=page, total_pages=total_pages,
                           stats=stats)


@app.route("/bank/import", methods=["POST"])
def bank_import():
    f = request.files.get("csv_file")
    if not f or not f.filename:
        return redirect(url_for("bank"))
    try:
        raw = f.read()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = raw.decode("latin-1")
        result = bank_mod.import_csv_text(text, f.filename)
    except Exception as e:
        log.error("Bank import error: %s", e)
        result = {"imported": 0, "matched": 0, "skipped": 0, "already_imported": False}
    return render_template("bank_import_result.html", result=result, filename=f.filename)


@app.route("/bank/rematch", methods=["POST"])
def bank_rematch():
    matched = bank_mod.rematch_all()
    return jsonify({"newly_matched": matched})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _current_quarter() -> int:
    return (datetime.now().month - 1) // 3 + 1


def _default_year_quarter(years: list) -> tuple[int, int]:
    """Return the year/quarter of the most recent invoice, falling back to current period."""
    try:
        last_date = db.get_connection().execute(
            "SELECT MAX(date) FROM invoices WHERE date IS NOT NULL"
        ).fetchone()[0]
        if last_date:
            dt = datetime.strptime(last_date[:10], "%Y-%m-%d")
            return dt.year, (dt.month - 1) // 3 + 1
    except Exception:
        pass
    return (years[0] if years else datetime.now().year), _current_quarter()


def run_dashboard():
    cfg = get_config().get("dashboard", {})
    app.run(
        host=cfg.get("host", "127.0.0.1"),
        port=cfg.get("port", 5000),
        debug=cfg.get("debug", False),
    )
