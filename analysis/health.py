"""Лещов health_z за Китай (PROLETR4).

Огледало на eu-macro-dashboard/analysis/health.py::lens_health: per-серия health_z
(вече изчислен от core/scorer.score_series, робастен z спрямо 10г норма, с полярност)
-> средно по peer_group -> претеглено средно по peer_group_weight -> health_z на лещата.

Разлики спрямо EU:
- здравето по серия се ВЗИМА от scorer-а (не се смята наново);
- серии със застоял отпечатък (същото правило като series_data.json: _periods_behind
  + _is_stale от analysis.anomaly) се ИЗКЛЮЧВАТ — иначе замразена серия води лещата;
- празен резултат (core.scorer._empty_score, health_z=0.0, current_value=None)
  НЕ е z=0, а липсващ.
Тежестите: каталогът на Китай няма PEER_GROUP_WEIGHT; използваме EU дефолта
(1.0 за всяка peer група; EU има само monetary_aggregates=0.5, а такава група у нас няма).
"""
from __future__ import annotations

import math
from typing import Any, Optional

import pandas as pd

from analysis.anomaly import _periods_behind, _is_stale

PEER_GROUP_WEIGHT: dict[str, float] = {}   # празно = 1.0 за всички (EU дефолт)

ALL_STALE_NOTE = "всички серии в лещата са стари"


def peer_group_weight(pg: str) -> float:
    return PEER_GROUP_WEIGHT.get(pg, 1.0)


def _usable_z(ind: Optional[dict]) -> Optional[float]:
    """health_z на серията или None ако липсва/е празен резултат (_empty_score)."""
    if not ind:
        return None
    if ind.get("current_value") is None:      # _empty_score: current_value=None, z=0.0
        return None
    z = ind.get("health_z")
    if z is None or (isinstance(z, float) and math.isnan(z)):
        return None
    return float(z)


def series_is_stale(last_date: Any, today: Any, release_schedule: Optional[str]) -> bool:
    """Същото правило като build_series_data (latest.stale)."""
    if last_date is None:
        return True
    pb = _periods_behind(pd.Timestamp(last_date), pd.Timestamp(today), release_schedule)
    return _is_stale(pb, release_schedule)


def lens_health(series_ids, indicators: dict, peer_groups: dict, last_dates: dict,
                schedules: dict, today: Any) -> dict:
    """Връща {health_z, n_series, excluded_stale, all_stale}.

    series_ids: серии, членове на лещата (SERIES на модула)
    indicators: {sid: score_series dict}; peer_groups/last_dates/schedules: {sid: ...}
    """
    excluded_stale: list[str] = []
    by_pg: dict[str, list[float]] = {}
    n_fresh_candidates = 0
    for sid in series_ids:
        if series_is_stale(last_dates.get(sid), today, schedules.get(sid)):
            excluded_stale.append(sid)
            continue
        n_fresh_candidates += 1
        z = _usable_z(indicators.get(sid))
        if z is None:
            continue
        pg = peer_groups.get(sid) or "_none"
        by_pg.setdefault(pg, []).append(z)

    pg_zs = [(sum(v) / len(v), peer_group_weight(pg)) for pg, v in by_pg.items()]
    n_used = sum(len(v) for v in by_pg.values())
    out = {"health_z": None, "n_series": n_used,
           "excluded_stale": sorted(excluded_stale),
           "all_stale": n_fresh_candidates == 0 and bool(excluded_stale)}
    if pg_zs:
        wsum = sum(w for _, w in pg_zs)
        if wsum:
            out["health_z"] = sum(z * w for z, w in pg_zs) / wsum
    return out
