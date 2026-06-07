"""
analysis/anomaly.py
===================
Cross-lens raw anomaly scan.

Разлика от другите analysis/ модули:
  - breadth.py    → агрегира per peer_group / lens
  - divergence.py → проверява conceptual pairs
  - non_consensus.py → филтрира по tags, прилага peer deviation
  - **anomaly.py**  → без теза, без tag predicate — чист scan за |z|>threshold
                      във целия каталог. "Кои серии точно сега са в краен отскок."

За briefing-а това е независим observation layer. Допълнителна сигурност:
ако серия е аномална тук, но НЕ се появи в non_consensus или divergence,
значи тя е "lone wolf" — заслужава специално разглеждане.

Изход:
  AnomalyReport
    ├── as_of: str (ISO)
    ├── threshold: z праг
    ├── lookback_years
    ├── total_flagged: брой серии с |z|>threshold (преди truncate)
    ├── top: [AnomalyReading, ...]          # sorted by |z| desc, truncated to top_n
    └── by_lens: {lens → [AnomalyReading, ...]}   # multi-lens серия се появява в двете

Dependencies:
  - catalog.series — за metadata enrichment (name_bg, peer_group, tags, narrative_hint)
  - core.primitives — z_score, new_extreme
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field, asdict
from typing import Optional

import numpy as np
import pandas as pd

from catalog.series import SERIES_CATALOG, ALLOWED_LENSES
from core.primitives import z_score, new_extreme


# ============================================================
# DEFAULTS
# ============================================================

Z_THRESHOLD_DEFAULT = 2.0
TOP_N_DEFAULT = 10
LOOKBACK_YEARS_DEFAULT = 5

# ── Staleness gate ──────────────────────────────────────────────────────────
# anomaly.py е "какво точно СЕГА е в краен отскок" (виж docstring горе). Стойност,
# чиято дата е твърде назад спрямо as_of за СОБСТВЕНАТА ѝ каденция, не е "сега" —
# затова не бива да влиза в Top Anomalies / total_flagged като текущ екстремум
# (иначе годишна 2024 стойност чете като "НОВ МИНИМУМ днес" на публичната страница).
# Прагът е ПО КАДЕНЦИЯ, защото единен праг не разделя чисто: годишна серия ~1.4
# периода зад (текуща, само ѝ липсва 2025) и месечна серия ~1.2 периода зад
# (текуща, зад daily as_of) се припокриват.
_PERIOD_DAYS = {
    "daily": 1.0,
    "weekly": 7.0,
    "monthly": 30.0,
    "quarterly": 91.0,
    "annually": 365.0,
    "annual": 365.0,
}
_MAX_PERIODS_BEHIND = {
    "daily": 21.0,       # ~3 седмици без отпечатък
    "weekly": 5.0,
    "monthly": 3.0,      # >3 месеца зад → застояла
    "quarterly": 2.0,
    "annually": 1.0,     # липсва цяла следваща година
    "annual": 1.0,
}
_DEFAULT_PERIOD_DAYS = 30.0
_DEFAULT_MAX_PERIODS = 3.0   # непозната каденция → третирай като месечна


# ============================================================
# DATA CLASSES
# ============================================================

@dataclass
class AnomalyReading:
    series_key: str
    series_name_bg: str
    lens: list[str]
    peer_group: str
    tags: list[str]
    last_value: float
    last_date: Optional[str]
    z_score: float
    direction: str                  # "up" | "down"
    is_new_extreme: bool            # нов max/min за lookback_years
    new_extreme_direction: Optional[str]   # "max" | "min" | None
    lookback_years: int
    narrative_hint: str
    stale: bool = False                     # дата твърде назад за каденцията си
    periods_behind: float = 0.0            # колко СОБСТВЕНИ периода зад as_of

    def to_dict(self) -> dict:
        d = asdict(self)
        for k in ("last_value", "z_score"):
            if isinstance(d[k], float) and np.isnan(d[k]):
                d[k] = None
        return d


@dataclass
class AnomalyReport:
    as_of: Optional[str]
    threshold: float
    lookback_years: int
    total_flagged: int
    top: list[AnomalyReading] = field(default_factory=list)
    by_lens: dict[str, list[AnomalyReading]] = field(default_factory=dict)
    stale_excluded: int = 0                          # брой застояли четения извън flagged
    stale_excluded_keys: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "as_of": self.as_of,
            "threshold": self.threshold,
            "lookback_years": self.lookback_years,
            "total_flagged": self.total_flagged,
            "stale_excluded": self.stale_excluded,
            "stale_excluded_keys": list(self.stale_excluded_keys),
            "top": [r.to_dict() for r in self.top],
            "by_lens": {
                lens: [r.to_dict() for r in readings]
                for lens, readings in self.by_lens.items()
            },
        }


# ============================================================
# PUBLIC API
# ============================================================

def compute_anomalies(
    snapshot: dict[str, pd.Series],
    z_threshold: float = Z_THRESHOLD_DEFAULT,
    top_n: int = TOP_N_DEFAULT,
    lookback_years: int = LOOKBACK_YEARS_DEFAULT,
) -> AnomalyReport:
    """Сканира snapshot-а за серии с |z|>threshold, връща top-N.

    Args:
        snapshot: {series_key → pd.Series} (каталожен ключ, не data-source ID).
        z_threshold: minimum |z| за да се флагне серия.
        top_n: колко top серии да върне в top list-а.
        lookback_years: window за new_extreme проверката.

    Returns:
        AnomalyReport с top (truncated), by_lens (всички flagged, multi-lens dedupe-ат се),
        total_flagged (pre-truncate брой на ТЕКУЩИ аномалии), и stale_excluded
        (брой четения изключени като застояли — за прозрачност, без тих cap).
    """
    as_of_ts = _max_date_ts(snapshot, list(snapshot.keys()))

    candidates: list[AnomalyReading] = []

    for key, series in snapshot.items():
        meta = SERIES_CATALOG.get(key)
        if meta is None:
            continue  # серия не е в каталога; skip за safety
        if series is None or series.dropna().empty:
            continue

        z_series = z_score(series)
        z_clean = z_series.dropna()
        if z_clean.empty:
            continue
        z_last = float(z_clean.iloc[-1])
        if np.isnan(z_last) or abs(z_last) <= z_threshold:
            continue

        clean = series.dropna()
        last_value = float(clean.iloc[-1])
        last_ts = (
            clean.index[-1] if isinstance(clean.index[-1], pd.Timestamp) else None
        )
        last_date = last_ts.strftime("%Y-%m-%d") if last_ts is not None else None

        sched = meta.get("release_schedule")
        periods_behind = _periods_behind(last_ts, as_of_ts, sched)
        stale = _is_stale(periods_behind, sched)

        ne = new_extreme(series, lookback_years=lookback_years)
        is_new_extreme = ne is not None
        new_extreme_dir = ne["direction"] if ne else None

        candidates.append(AnomalyReading(
            series_key=key,
            series_name_bg=meta.get("name_bg", key),
            lens=list(meta.get("lens", [])),
            peer_group=meta.get("peer_group", ""),
            tags=list(meta.get("tags", [])),
            last_value=round(last_value, 4),
            last_date=last_date,
            z_score=round(z_last, 3),
            direction="up" if z_last > 0 else "down",
            is_new_extreme=is_new_extreme,
            new_extreme_direction=new_extreme_dir,
            lookback_years=lookback_years,
            narrative_hint=meta.get("narrative_hint", ""),
            stale=stale,
            periods_behind=round(periods_behind, 2),
        ))

    # Staleness gate: застояло четене не е "сега" → вън от текущите аномалии.
    # Броим изключените (без тих cap) — годишна/тримесечна серия, чиято последна
    # точка е твърде назад за каденцията си, повече не чете като текущ екстремум.
    flagged = [r for r in candidates if not r.stale]
    dropped = [r for r in candidates if r.stale]

    # Сортиране по |z| desc
    flagged.sort(key=lambda r: abs(r.z_score), reverse=True)

    total = len(flagged)
    top = flagged[:top_n]

    # by_lens: всяка серия се появява във всички свои lens-ове
    by_lens: dict[str, list[AnomalyReading]] = defaultdict(list)
    for r in flagged:
        for lens in r.lens:
            if lens in ALLOWED_LENSES:
                by_lens[lens].append(r)

    as_of = as_of_ts.strftime("%Y-%m-%d") if as_of_ts is not None else None

    return AnomalyReport(
        as_of=as_of,
        threshold=z_threshold,
        lookback_years=lookback_years,
        total_flagged=total,
        top=top,
        by_lens=dict(by_lens),
        stale_excluded=len(dropped),
        stale_excluded_keys=[r.series_key for r in dropped],
    )


# ============================================================
# INTERNAL
# ============================================================

def _max_date_ts(
    snapshot: dict[str, pd.Series],
    keys: list[str],
) -> Optional[pd.Timestamp]:
    """Най-скорошната дата сред сериите (като Timestamp)."""
    dates: list[pd.Timestamp] = []
    for k in keys:
        s = snapshot.get(k)
        if s is None:
            continue
        s_clean = s.dropna()
        if s_clean.empty:
            continue
        last = s_clean.index[-1]
        if isinstance(last, pd.Timestamp):
            dates.append(last)
    return max(dates) if dates else None


def _compute_as_of(
    snapshot: dict[str, pd.Series],
    keys: list[str],
) -> Optional[str]:
    """Най-скорошна дата сред сериите (ISO стринг)."""
    ts = _max_date_ts(snapshot, keys)
    return ts.strftime("%Y-%m-%d") if ts is not None else None


def _periods_behind(
    last_ts: Optional[pd.Timestamp],
    as_of_ts: Optional[pd.Timestamp],
    release_schedule: Optional[str],
) -> float:
    """Колко СОБСТВЕНИ release-периода назад е last_ts спрямо as_of.

    Месечна серия 1 месец зад → ~1.0; годишна серия 1 година зад → ~1.0.
    Нормализира по каденция, за да е прагът сравним между честоти.
    """
    if last_ts is None or as_of_ts is None:
        return 0.0
    days = (as_of_ts - last_ts).days
    if days <= 0:
        return 0.0
    period = _PERIOD_DAYS.get((release_schedule or "").lower(), _DEFAULT_PERIOD_DAYS)
    return days / period


def _is_stale(periods_behind: float, release_schedule: Optional[str]) -> bool:
    """True ако четенето е твърде назад за каденцията си → не е 'сега'."""
    threshold = _MAX_PERIODS_BEHIND.get(
        (release_schedule or "").lower(), _DEFAULT_MAX_PERIODS
    )
    return periods_behind > threshold
