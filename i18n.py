"""
UI translations for FacturaAI — Spanish / English / Simplified Chinese.
Usage: from i18n import get_translations, LANGUAGES
"""
from __future__ import annotations

LANGUAGES: dict[str, str] = {
    "es": "ES",
    "en": "EN",
    "zh": "中文",
}

_T: dict[str, dict[str, str]] = {

    # ── Nav ──────────────────────────────────────────────────────────────────
    "nav_invoices":      {"es": "Facturas",      "en": "Invoices",      "zh": "发票"},
    "nav_monthly":       {"es": "Mensual",        "en": "Monthly",       "zh": "月度"},
    "nav_categories":    {"es": "Categorías",     "en": "Categories",    "zh": "费用分类"},
    "nav_303":           {"es": "IVA 303",        "en": "VAT 303",       "zh": "增值税303"},
    "nav_390":           {"es": "IVA 390",        "en": "VAT 390",       "zh": "增值税390"},
    "nav_130":           {"es": "IRPF 130",       "en": "IRPF 130",      "zh": "个税130"},
    "nav_100":           {"es": "Renta 100",      "en": "Income Tax 100", "zh": "个税100"},
    "nav_pnl":           {"es": "Pérdidas y Ganancias", "en": "P&L",     "zh": "损益表"},
    "nav_bank":          {"es": "Banco",          "en": "Bank",          "zh": "银行对账"},
    "nav_review":        {"es": "Revisión",       "en": "Review",        "zh": "待审核"},
    "nav_rejected":      {"es": "Rechazadas",     "en": "Rejected",      "zh": "已拒绝"},
    "nav_health":        {"es": "Estado",         "en": "Status",        "zh": "系统状态"},

    # ── Common controls ───────────────────────────────────────────────────────
    "year":              {"es": "Año",            "en": "Year",          "zh": "年份"},
    "all_years":         {"es": "Todos los años", "en": "All years",     "zh": "全部年份"},
    "quarter":           {"es": "Trimestre",      "en": "Quarter",       "zh": "季度"},
    "annual_option":     {"es": "Anual",          "en": "Annual",        "zh": "年度"},
    "view":              {"es": "Ver",            "en": "View",          "zh": "查看"},
    "filter":            {"es": "Filtrar",        "en": "Filter",        "zh": "筛选"},
    "clear":             {"es": "Limpiar",        "en": "Clear",         "zh": "清除"},
    "clear_all_btn":     {"es": "Borrar todo",    "en": "Clear All",     "zh": "清空数据"},
    "clear_all_confirm": {"es": "¿Borrar TODAS las facturas, transacciones bancarias y archivos de salida? Esta acción no se puede deshacer.",
                          "en": "Delete ALL invoices, bank transactions, and output files? This cannot be undone.",
                          "zh": "删除所有发票、银行交易和输出文件？此操作无法撤销。"},
    "clear_all_done":    {"es": "Todo borrado",   "en": "All cleared",   "zh": "已清空"},
    "export_csv":        {"es": "↓ CSV",          "en": "↓ CSV",         "zh": "↓ CSV"},
    "import_btn":        {"es": "Importar",       "en": "Import",        "zh": "导入"},

    # ── Units / counters ──────────────────────────────────────────────────────
    "inv_singular":      {"es": "factura",        "en": "invoice",       "zh": "张发票"},
    "inv_plural":        {"es": "facturas",       "en": "invoices",      "zh": "张发票"},
    "results":           {"es": "resultados",     "en": "results",       "zh": "条记录"},

    # ── Shared table headers ──────────────────────────────────────────────────
    "col_date":          {"es": "Fecha",          "en": "Date",          "zh": "日期"},
    "col_supplier":      {"es": "Proveedor",      "en": "Supplier",      "zh": "供应商"},
    "col_inv_no":        {"es": "Nº Factura",     "en": "Invoice No.",   "zh": "发票号"},
    "col_net":           {"es": "Base",           "en": "Net",           "zh": "税基"},
    "col_vat":           {"es": "IVA",            "en": "VAT",           "zh": "增值税"},
    "col_total":         {"es": "Total",          "en": "Total",         "zh": "合计"},
    "col_currency":      {"es": "Moneda",         "en": "Currency",      "zh": "货币"},
    "col_source":        {"es": "Fuente",         "en": "Source",        "zh": "来源"},
    "col_confidence":    {"es": "Confianza",      "en": "Confidence",    "zh": "置信度"},
    "col_status":        {"es": "Estado",         "en": "Status",        "zh": "状态"},
    "col_month":         {"es": "Mes",            "en": "Month",         "zh": "月份"},
    "col_count":         {"es": "Facturas",       "en": "Invoices",      "zh": "发票数"},
    "col_taxable":       {"es": "Base Imponible", "en": "Taxable Base",  "zh": "税基"},
    "col_category":      {"es": "Categoría",      "en": "Category",      "zh": "分类"},
    "col_rate":          {"es": "Tipo",           "en": "Rate",          "zh": "税率"},
    "col_box":           {"es": "Casilla",        "en": "Box",           "zh": "栏目"},
    "col_description":   {"es": "Descripción",    "en": "Description",   "zh": "描述"},
    "col_vat_amount":    {"es": "Cuota IVA",      "en": "VAT Amount",    "zh": "税额"},
    "col_concept":       {"es": "Concepto",       "en": "Description",   "zh": "摘要"},
    "col_amount":        {"es": "Importe",        "en": "Amount",        "zh": "金额"},
    "col_balance":       {"es": "Saldo",          "en": "Balance",       "zh": "余额"},
    "col_matched_inv":   {"es": "Factura conciliada", "en": "Matched invoice", "zh": "匹配发票"},

    # ── Badges / status labels ────────────────────────────────────────────────
    "badge_review":      {"es": "Revisar",        "en": "Review",        "zh": "待审核"},
    "badge_ok":          {"es": "OK",             "en": "OK",            "zh": "正常"},
    "no_results":        {"es": "Sin resultados", "en": "No results",    "zh": "无结果"},
    "no_data":           {"es": "Sin datos",      "en": "No data",       "zh": "无数据"},
    "total_row":         {"es": "TOTAL",          "en": "TOTAL",         "zh": "合计"},
    "prev_page":         {"es": "‹ Anterior",     "en": "‹ Previous",    "zh": "‹ 上一页"},
    "next_page":         {"es": "Siguiente ›",    "en": "Next ›",        "zh": "下一页 ›"},

    # ── Index / invoice list ──────────────────────────────────────────────────
    "page_invoices":     {"es": "Facturas",       "en": "Invoices",      "zh": "发票列表"},
    "filter_supplier":   {"es": "Proveedor",      "en": "Supplier",      "zh": "供应商"},
    "filter_from":       {"es": "Desde",          "en": "From",          "zh": "开始日期"},
    "filter_to":         {"es": "Hasta",          "en": "To",            "zh": "结束日期"},
    "filter_min":        {"es": "Importe mín.",   "en": "Min amount",    "zh": "最小金额"},
    "filter_max":        {"es": "Importe máx.",   "en": "Max amount",    "zh": "最大金额"},
    "filter_review_only":{"es": "Solo revisión",  "en": "Review only",   "zh": "仅待审核"},
    "supplier_eg":       {"es": "Ej. Makro",      "en": "e.g. Makro",    "zh": "如 Makro"},

    # ── Monthly ───────────────────────────────────────────────────────────────
    "page_monthly":      {"es": "Resumen Mensual","en": "Monthly Summary","zh": "月度汇总"},

    # ── Review ────────────────────────────────────────────────────────────────
    "page_review":       {"es": "Cola de Revisión Manual", "en": "Manual Review Queue", "zh": "人工审核队列"},
    "review_none":       {"es": "Sin facturas pendientes de revisión.",
                          "en": "No invoices pending review.",
                          "zh": "无待审核发票。"},
    "badge_vat_err":     {"es": "IVA incorrecto", "en": "VAT error",     "zh": "增值税错误"},
    "badge_spike":       {"es": "Importe anómalo","en": "Unusual amount", "zh": "金额异常"},
    "badge_ai_flag":     {"es": "Revisión IA",    "en": "AI flagged",    "zh": "AI标记"},
    "badge_new_extractor": {"es": "Nuevo proveedor — confirmar", "en": "New supplier — confirm", "zh": "新供应商 — 待确认"},
    "col_reason":        {"es": "Motivo",         "en": "Reason",        "zh": "原因"},
    "col_vat_rate":      {"es": "Tipo IVA",       "en": "VAT Rate",      "zh": "增值税率"},
    "save_reviewed":     {"es": "Guardar y marcar revisado",
                          "en": "Save and mark reviewed",
                          "zh": "保存并标记为已审核"},

    # ── Health / status ───────────────────────────────────────────────────────
    "page_health":       {"es": "Estado del Sistema", "en": "System Status", "zh": "系统状态"},
    "last_heartbeat":    {"es": "Último heartbeat",   "en": "Last heartbeat","zh": "最近心跳"},
    "files_found":       {"es": "Archivos encontrados","en": "Files found",  "zh": "发现文件"},
    "files_processed":   {"es": "Procesados",         "en": "Processed",    "zh": "已处理"},
    "files_failed":      {"es": "Fallidos",           "en": "Failed",       "zh": "失败"},
    "files_skipped":     {"es": "Omitidos",           "en": "Skipped",      "zh": "已跳过"},
    "cycle_duration":    {"es": "Duración ciclo",     "en": "Cycle duration","zh": "周期时长"},
    "pending_review":    {"es": "Pendientes revisión","en": "Pending review","zh": "待审核"},
    "cycle_label":       {"es": "Ciclo",              "en": "Cycle",        "zh": "周期"},

    # ── Categories ────────────────────────────────────────────────────────────
    "page_categories":   {"es": "Gastos por Categoría","en": "Expenses by Category","zh": "按分类费用"},

    # ── Modelo 303 ────────────────────────────────────────────────────────────
    "page_303":          {"es": "Modelo 303 — Declaración Trimestral IVA",
                          "en": "Model 303 — Quarterly VAT Return",
                          "zh": "303表格 — 季度增值税申报"},
    "period":            {"es": "Período",        "en": "Period",        "zh": "期间"},
    "sec1_title":        {"es": "Sección I — IVA Devengado (Repercutido)",
                          "en": "Section I — Output VAT (Sales)",
                          "zh": "第一节 — 销项税"},
    "sec1_pending":      {"es": ("Pendiente — las facturas de ingresos aún no están disponibles. "
                                 "Cuando se añadan, aparecerán aquí y el resultado se calculará automáticamente."),
                          "en": ("Pending — income invoices are not yet available. "
                                 "Once added they will appear here and the result will be calculated automatically."),
                          "zh": "待定 — 收入发票尚未可用，添加后将自动显示并计算结果。"},
    "sec2_title":        {"es": "Sección II — IVA Deducible (Soportado en gastos)",
                          "en": "Section II — Input VAT (Purchases)",
                          "zh": "第二节 — 进项税（采购）"},
    "sec3_title":        {"es": "Sección III — Resultado",
                          "en": "Section III — Result",
                          "zh": "第三节 — 结果"},
    "purchases_type":    {"es": "Adquisiciones corrientes — tipo",
                          "en": "Current purchases — rate",
                          "zh": "当期采购 — 税率"},
    "total_input_vat":   {"es": "TOTAL IVA DEDUCIBLE", "en": "TOTAL INPUT VAT", "zh": "可抵扣增值税合计"},
    "output_vat_row":    {"es": "Total IVA devengado (repercutido)",
                          "en": "Total output VAT (sales)",
                          "zh": "销项税合计"},
    "input_vat_row":     {"es": "Total IVA deducible (soportado)",
                          "en": "Total deductible VAT (purchases)",
                          "zh": "进项税合计"},
    "result_label":      {"es": "RESULTADO",      "en": "RESULT",        "zh": "结果"},
    "to_offset":         {"es": "A compensar",    "en": "To offset",     "zh": "可抵扣"},
    "to_pay":            {"es": "A ingresar",     "en": "To pay",        "zh": "应缴"},
    "zero":              {"es": "Cero",           "en": "Zero",          "zh": "零"},
    "no_data_period":    {"es": "Sin datos para este período",
                          "en": "No data for this period",
                          "zh": "本期无数据"},
    "draft_notice":      {"es": "Borrador generado automáticamente. Verificar con el gestor antes de presentar.",
                          "en": "Auto-generated draft. Verify with your accountant before filing.",
                          "zh": "自动生成的草稿，提交前请与会计核实。"},

    # ── Modelo 390 ────────────────────────────────────────────────────────────
    "page_390":          {"es": "Modelo 390 — Resumen Anual IVA",
                          "en": "Model 390 — Annual VAT Summary",
                          "zh": "390表格 — 年度增值税汇总"},
    "fiscal_year":       {"es": "Ejercicio",      "en": "Fiscal Year",   "zh": "财年"},
    "vat_output_title":  {"es": "IVA Devengado (Repercutido)",
                          "en": "Output VAT (Sales)",
                          "zh": "销项税"},
    "vat_input_title":   {"es": "IVA Deducible (Soportado en gastos)",
                          "en": "Input VAT (Purchases)",
                          "zh": "进项税（采购）"},
    "annual_result_hdr": {"es": "Resultado del Ejercicio", "en": "Annual Result", "zh": "年度结果"},
    "total_output_row":  {"es": "Total IVA devengado",  "en": "Total output VAT", "zh": "销项税合计"},
    "total_input_row":   {"es": "Total IVA deducible",  "en": "Total input VAT",  "zh": "进项税合计"},
    "annual_result_lbl": {"es": "RESULTADO ANUAL",      "en": "ANNUAL RESULT",    "zh": "年度结果"},
    "no_data_year":      {"es": "Sin datos para este año",
                          "en": "No data for this year",
                          "zh": "本年无数据"},

    # ── Modelo 130 / 100 (income seam — see db.get_income_for_period) ──────────
    "page_130":          {"es": "Modelo 130 — Pago Fraccionado IRPF",
                          "en": "Model 130 — Quarterly IRPF Payment",
                          "zh": "130表格 — 季度个税预缴"},
    "page_100":          {"es": "Modelo 100 — Resumen Anual Actividad Económica",
                          "en": "Model 100 — Annual Business Income Summary",
                          "zh": "100表格 — 年度经营所得汇总"},
    "income_stub_notice": {"es": "Ingresos = 0,00 € — la fuente de ingresos aún no está configurada. Este borrador solo refleja gastos.",
                          "en": "Income = €0.00 — no income source is configured yet. This draft reflects expenses only.",
                          "zh": "收入 = 0.00 € — 尚未配置收入来源，此草稿仅反映支出。"},
    "casilla_ingresos":  {"es": "Ingresos",              "en": "Income",                "zh": "收入"},
    "casilla_gastos":    {"es": "Gastos deducibles",     "en": "Deductible expenses",   "zh": "可抵扣支出"},
    "casilla_neto":      {"es": "Rendimiento neto",      "en": "Net income",            "zh": "净收益"},
    "casilla_pago":      {"es": "20% s/ rendimiento neto","en": "20% of net income",     "zh": "净收益的20%"},
    "casilla_prior":     {"es": "Pagos fraccionados anteriores", "en": "Prior quarterly payments", "zh": "前几季度已预缴"},

    # ── P&L statement + manual cash income ───────────────────────────────────
    "page_pnl":          {"es": "Cuenta de Pérdidas y Ganancias",
                          "en": "Profit & Loss Statement",
                          "zh": "损益表"},
    "pnl_income_section": {"es": "Ingresos",       "en": "Income",        "zh": "收入"},
    "pnl_bank_income":   {"es": "Ingresos bancarios (abonos)",
                          "en": "Bank income (credits)",
                          "zh": "银行收入（贷记）"},
    "pnl_cash_income":   {"es": "Ingresos en efectivo (manual)",
                          "en": "Cash income (manual)",
                          "zh": "现金收入（手动）"},
    "pnl_total_income":  {"es": "TOTAL INGRESOS",  "en": "TOTAL INCOME",  "zh": "总收入"},
    "pnl_expense_section": {"es": "Gastos por categoría", "en": "Expenses by category", "zh": "按分类支出"},
    "pnl_total_expenses": {"es": "TOTAL GASTOS",   "en": "TOTAL EXPENSES", "zh": "总支出"},
    "pnl_net_result":    {"es": "RESULTADO NETO",  "en": "NET RESULT",    "zh": "净利润"},
    "cash_income_title": {"es": "Ingresos en efectivo",
                          "en": "Cash income",
                          "zh": "现金收入"},
    "cash_income_hint":  {"es": "Para ventas en efectivo que no aparecen en el extracto bancario.",
                          "en": "For cash sales that won't show up on the bank statement.",
                          "zh": "用于不会出现在银行对账单中的现金销售。"},
    "cash_income_add":   {"es": "Añadir",          "en": "Add",           "zh": "添加"},
    "cash_income_none":  {"es": "Sin ingresos en efectivo registrados para este período.",
                          "en": "No cash income recorded for this period.",
                          "zh": "本期无现金收入记录。"},
    "col_action":        {"es": "Acción",          "en": "Action",        "zh": "操作"},
    "delete_btn":        {"es": "Eliminar",        "en": "Delete",        "zh": "删除"},

    # ── Rejected documents ───────────────────────────────────────────────────
    "page_rejected":     {"es": "Documentos Rechazados", "en": "Rejected Documents", "zh": "已拒绝文档"},
    "rejected_none":     {"es": "No hay documentos rechazados.",
                          "en": "No rejected documents.",
                          "zh": "没有被拒绝的文档。"},

    # ── Bank ──────────────────────────────────────────────────────────────────
    "page_bank":         {"es": "Extracto Bancario",     "en": "Bank Statement",  "zh": "银行对账单"},
    "bank_import_title": {"es": "Importar extracto (CSV)","en": "Import statement (CSV)","zh": "导入对账单（CSV）"},
    "bank_compat":       {"es": ("CSV o Excel (.xlsx). Compatible con Santander, CaixaBank, BBVA y Sabadell. "
                                 "Cada archivo sólo se importa una vez. Los abonos (importe positivo) se "
                                 "cuentan como ingresos — ver la Cuenta de Pérdidas y Ganancias."),
                          "en": ("CSV or Excel (.xlsx). Compatible with Santander, CaixaBank, BBVA and Sabadell. "
                                 "Each file can only be imported once. Credits (positive amounts) count as "
                                 "income — see the P&L statement."),
                          "zh": "CSV或Excel（.xlsx）。兼容Santander、CaixaBank、BBVA和Sabadell。每个文件只能导入一次。贷记（正数金额）计为收入——参见损益表。"},
    "bank_transactions": {"es": "Movimientos",    "en": "Transactions",  "zh": "交易记录"},
    "bank_matched":      {"es": "Conciliados",    "en": "Matched",       "zh": "已匹配"},
    "bank_unmatched":    {"es": "Sin conciliar",  "en": "Unmatched",     "zh": "未匹配"},
    "bank_rematch":      {"es": "↻ Re-conciliar automáticamente",
                          "en": "↻ Auto-rematch",
                          "zh": "↻ 自动重新匹配"},
    "bank_no_data":      {"es": "No hay movimientos. Importa un extracto CSV para empezar.",
                          "en": "No transactions. Import a bank CSV to get started.",
                          "zh": "暂无交易记录，请导入CSV银行对账单。"},
    "processing":        {"es": "Procesando…",    "en": "Processing…",   "zh": "处理中…"},

    # ── Bank import result ────────────────────────────────────────────────────
    "bank_import_done":  {"es": "Importación completada",  "en": "Import complete",   "zh": "导入完成"},
    "bank_import_hdr":   {"es": "Importación de extracto", "en": "Statement import",  "zh": "对账单导入"},
    "file_label":        {"es": "Archivo",         "en": "File",          "zh": "文件"},
    "already_imported":  {"es": ("Este archivo ya fue importado anteriormente. "
                                 "No se han añadido duplicados."),
                          "en": "This file was already imported. No duplicates were added.",
                          "zh": "该文件已导入过，不会添加重复记录。"},
    "no_valid_rows":     {"es": ("No se encontraron movimientos válidos. "
                                 "Comprueba que el formato sea CSV con columnas de fecha, concepto e importe."),
                          "en": ("No valid transactions found. "
                                 "Check the CSV has date, description and amount columns."),
                          "zh": "未找到有效交易记录。请确认CSV包含日期、摘要和金额列。"},
    "bank_imported":     {"es": "Importados",      "en": "Imported",      "zh": "已导入"},
    "view_statement":    {"es": "Ver extracto",    "en": "View statement","zh": "查看对账单"},
}


def get_translations(lang: str) -> dict[str, str]:
    lang = lang if lang in LANGUAGES else "es"
    return {k: v.get(lang, v.get("es", "")) for k, v in _T.items()}
