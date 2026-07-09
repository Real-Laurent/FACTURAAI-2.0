"""
Sanity checks applied after extraction.
Returns flags; never raises.
"""

import json
import logging
from config.loader import get_config

log = logging.getLogger(__name__)


def check_vat(net: float, vat: float, vat_breakdown_json: str = None) -> bool:
    """
    Return True if VAT is consistent with Spanish rates.

    - If vat_breakdown_json is provided (mixed-rate invoice): validate each
      line independently. All lines must pass.
    - Otherwise: the blended rate (vat/net) must be within tolerance of one
      of the known Spanish VAT rates.
    """
    cfg = get_config().get("sanity", {})
    rates = cfg.get("vat_rates", [0.04, 0.10, 0.21])
    tol   = cfg.get("vat_tolerance", 0.02)

    if vat_breakdown_json:
        try:
            lines = json.loads(vat_breakdown_json)
            for line in lines:
                line_base = line.get("base", 0)
                line_amt  = line.get("amount", 0)
                line_rate = line.get("rate", 0)
                if line_base <= 0:
                    continue
                actual = line_amt / line_base
                if not any(abs(actual - r) <= tol for r in rates):
                    log.warning(
                        "VAT sanity fail on breakdown line: base=%.2f vat=%.2f rate=%.4f",
                        line_base, line_amt, actual,
                    )
                    return False
            return True
        except (ValueError, KeyError, TypeError) as e:
            log.warning("Could not parse vat_breakdown for sanity check: %s", e)
            # fall through to blended-rate check

    if not net or not vat or net <= 0:
        return False

    actual_rate = vat / net
    if any(abs(actual_rate - r) <= tol for r in rates):
        return True

    log.warning(
        "VAT sanity fail: net=%.2f vat=%.2f implied_rate=%.4f", net, vat, actual_rate
    )
    return False


def check_spike(total: float, year: int, month: int) -> bool:
    """Return True if the total is suspiciously large vs. rolling monthly average."""
    if not total or total <= 0:
        return False
    from db import get_monthly_average
    cfg = get_config().get("sanity", {})
    multiplier = cfg.get("monthly_spike_multiplier", 3.0)
    avg = get_monthly_average(year, month)
    if avg <= 0:
        return False
    if total > avg * multiplier:
        log.warning("Spike flag: total=%.2f vs avg=%.2f (x%.1f)", total, avg, multiplier)
        return True
    return False
