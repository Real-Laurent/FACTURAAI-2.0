"""
Expense category mapping for AEAT tax classification.
Supplier name keywords are matched case-insensitively.
"""
from __future__ import annotations

CATEGORY_LABELS: dict[str, str] = {
    "alimentacion":        "Alimentación y bebidas",
    "suministros":         "Suministros (luz/gas/agua)",
    "telecomunicaciones":  "Telecomunicaciones",
    "seguros":             "Seguros",
    "publicidad":          "Publicidad y marketing",
    "compras_mercancias":  "Compras de mercancías",
    "servicios_bancarios": "Servicios bancarios y similares",
    "otros_gastos":        "Otros gastos de explotación",
    "sin_clasificar":      "Sin clasificar",
}

# (keyword, category_code) — first match wins
_MAP: list[tuple[str, str]] = [
    ("mercadona",   "alimentacion"),
    ("makro",       "alimentacion"),
    ("naturgy",     "suministros"),
    ("digi",        "telecomunicaciones"),
    ("qualianza",   "seguros"),
    ("sinages",     "publicidad"),
    ("disbere",     "compras_mercancias"),
    ("voldis",      "compras_mercancias"),
    ("ehosa",       "compras_mercancias"),
    ("luji",        "compras_mercancias"),
    ("recreativos", "otros_gastos"),
    ("caixabank",   "servicios_bancarios"),
]


def auto_category(supplier: str | None) -> str:
    if not supplier:
        return "sin_clasificar"
    low = supplier.lower()
    for keyword, code in _MAP:
        if keyword in low:
            return code
    return "sin_clasificar"


def label(code: str | None) -> str:
    return CATEGORY_LABELS.get(code or "", "Sin clasificar")
