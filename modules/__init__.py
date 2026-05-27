"""modules — Аналитични lens-ове за China macro dashboard."""
from modules.growth import run as run_growth
from modules.inflation import run as run_inflation
from modules.labor import run as run_labor
from modules.credit import run as run_credit
from modules.property import run as run_property

__all__ = [
    "run_growth",
    "run_inflation",
    "run_labor",
    "run_credit",
    "run_property",
]
