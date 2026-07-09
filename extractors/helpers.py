"""
Shared parsing utilities for all supplier extractors.
"""

import re
from typing import Optional

SPANISH_MONTHS = {
    'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4,
    'mayo': 5, 'junio': 6, 'julio': 7, 'agosto': 8,
    'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12,
}


def parse_amount(s: str) -> Optional[float]:
    """
    Parse a Spanish-locale number string to float.
    Handles: "1.234,56" → 1234.56, "466,07" → 466.07, "466.07" → 466.07
    """
    if not s:
        return None
    s = s.strip().replace(' ', '').replace('\xa0', '')
    # "1.234,56" pattern — thousands dot, decimal comma
    if re.match(r'^\d{1,3}(\.\d{3})+(,\d+)?$', s):
        s = s.replace('.', '').replace(',', '.')
    else:
        s = s.replace(',', '.')
    try:
        return float(s)
    except ValueError:
        return None


def parse_date(s: str) -> Optional[str]:
    """
    Try all date formats seen in Spanish invoices. Returns 'YYYY-MM-DD' or None.
    Formats handled:
      DD/MM/YYYY   31/05/2026
      DD/MM/YY     31/05/26
      DD-MM-YY     29-05-26
      DD.MM.YYYY   08.06.2026
      D mes YYYY   19 mayo 2026  (Spanish month names)
    """
    if not s:
        return None
    s = s.strip()

    # DD/MM/YYYY
    m = re.fullmatch(r'(\d{2})/(\d{2})/(\d{4})', s)
    if m:
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"

    # DD/MM/YY
    m = re.fullmatch(r'(\d{2})/(\d{2})/(\d{2})', s)
    if m:
        y = int(m.group(3))
        y = 2000 + y if y < 50 else 1900 + y
        return f"{y:04d}-{m.group(2)}-{m.group(1)}"

    # DD-MM-YY
    m = re.fullmatch(r'(\d{2})-(\d{2})-(\d{2})', s)
    if m:
        y = int(m.group(3))
        y = 2000 + y if y < 50 else 1900 + y
        return f"{y:04d}-{m.group(2)}-{m.group(1)}"

    # DD.MM.YYYY
    m = re.fullmatch(r'(\d{2})\.(\d{2})\.(\d{4})', s)
    if m:
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"

    # D/DD mes YYYY  (Spanish month name)
    m = re.fullmatch(r'(\d{1,2})\s+(\w+)\s+(\d{4})', s, re.IGNORECASE)
    if m:
        month = SPANISH_MONTHS.get(m.group(2).lower())
        if month:
            return f"{m.group(3)}-{month:02d}-{int(m.group(1)):02d}"

    return None


def first_match(pattern: str, text: str, flags: int = 0) -> Optional[re.Match]:
    return re.search(pattern, text, flags)


def find_amount(pattern: str, text: str, flags: int = 0) -> Optional[float]:
    m = re.search(pattern, text, flags)
    if m:
        return parse_amount(m.group(1))
    return None


def find_date(pattern: str, text: str, flags: int = 0) -> Optional[str]:
    m = re.search(pattern, text, flags)
    if m:
        return parse_date(m.group(1))
    return None


def collapse_spaced_chars(text: str) -> str:
    """
    Collapse pdfplumber output where each character is individually space-separated
    (common with certain PDF generators). Multi-char tokens act as run boundaries.
    Example: 'M a k r o' → 'Makro', '3 2 , 4 3' → '32,43'
    """
    out = []
    for line in text.split('\n'):
        tokens = line.split(' ')
        new_toks: list[str] = []
        run: list[str] = []
        for tok in tokens:
            if len(tok) <= 1:
                run.append(tok)
            else:
                if run:
                    new_toks.append(''.join(run))
                    run = []
                new_toks.append(tok)
        if run:
            new_toks.append(''.join(run))
        out.append(' '.join(new_toks))
    return '\n'.join(out)
