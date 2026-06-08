"""
core/scorer.py
==============
Преобразува сурови pd.Series стойности в нормализирани scores (0–100).

Data-source agnostic — работи с pd.Series независимо дали идва от ECB,
Eurostat или другаде.

Методология:
• percentile_rank(value, history) → 0–100 спрямо историческото разпределение
• invert=True → обръща логиката (висок unemployment = нисък score)
• z_score → колко стандартни отклонения от средната за периода

Всеки индикатор излиза с:
  - score (0–100)
  - percentile (0–100)
  - z_score
  - current_value
  - last_date
  - yoy_change (%)
"""
from __future__ import annotations
from typing import Optional

import numpy as np
import pandas as pd


def percentile_rank(current: float, history: pd.Series) -> float:
    """% от историческите стойности по-ниски от текущата (0..100)."""
    if len(history) == 0:
        return 50.0
    return float(np.sum(history < current) / len(history) * 100)


def z_score(current: float, history: pd.Series) -> float:
    """Стандартизирана стойност спрямо историческото разпределение."""
    if len(history) == 0 or history.std() == 0:
        return 0.0
    return float((current - history.mean()) / history.std())


def normalize(value: float, lo: float, hi: float, invert: bool = False) -> float:
    """Линейна нормализация към 0–100. lo→0, hi→100 (или обратно с invert)."""
    if hi == lo:
        return 50.0
    score = (value - lo) / (hi - lo) * 100
    score = max(0.0, min(100.0, score))
    return 100.0 - score if invert else score


def score_series(
    series: pd.Series,
    history_start: str = "1999-01-01",
    invert: bool = False,
    name: str = "",
    is_rate: bool = False,
    polarity=None,
    window_years: int = 10,
    min_obs: int = 36,
    band: float = 1.0,
) -> dict:
    """Главна функция — РОБАСТЕН z спрямо 10-г. плъзгащ прозорец → 0–100.

    Единен примитив (US/EU/CN) — виж ../macro-satellite/LENS_SCORING_METHODOLOGY.md.
    Заменя percentile-of-full-history (който дрейфаше: китайският растеж се
    съдеше спрямо 10–14%-ната ера → трайно затиснат). Сега нормата е последните
    10 г. → следва структурния спад.

    invert=True → polarity -1 (по-високо=по-зле). Може да се подаде явна `polarity`:
      +1 / -1 / ("U","target",X) / ("U","self") — за U-форма (виж inflation модула).

    Args:
        is_rate: True ако стойността е вече в % → YoY промяна като pp delta.
        window_years/min_obs: 10-г. прозорец; под min_obs точки → fallback към
            пълната налична история (CN серии с къса история).
        band: толерантна лента (σ) за U-формата.
    """
    series = series.dropna()
    if len(series) == 0:
        return _empty_score(name)

    current_val = float(series.iloc[-1])
    last_date = str(series.index[-1].date())

    # Плъзгащ 10-г. прозорец (fallback към пълна история за къси серии)
    if isinstance(series.index, pd.DatetimeIndex):
        cutoff = series.index[-1] - pd.DateOffset(years=window_years)
        window = series[series.index >= cutoff]
    else:
        window = series
    # 10г прозорец под min_obs → fallback към пълна история, но маркирай: percentile/z
    # върху ~14-17 точки (policy-pinned тримесечни) са ненадеждни за display (#12).
    thin_window = len(window) < min_obs
    if thin_window:
        window = series

    med = float(window.median())
    mad = float((window - med).abs().median())
    scale = 1.4826 * mad
    pct = percentile_rank(current_val, window)  # второстепенно (за display)

    pol = polarity if polarity is not None else (-1 if invert else 1)

    if isinstance(pol, tuple) and pol and pol[0] == "U":
        # U-форма: отклонение в двете посоки = по-зле
        if scale == 0 or np.isnan(scale):
            z_h, z_report = float(band), 0.0
        else:
            center = float(pol[2]) if pol[1] == "target" else med
            z_report = (current_val - med) / scale
            z_h = band - abs((current_val - center) / scale)
    else:
        if scale == 0 or np.isnan(scale):
            z_h, z_report = 0.0, 0.0
        else:
            z_report = (current_val - med) / scale
            sign = float(pol) if pol in (1, -1, +1) else 1.0
            z_h = sign * z_report

    score = round(50.0 * (1.0 + np.tanh(z_h / 2.0)), 1)

    yoy = _calc_change(series, as_pp=is_rate)
    yoy_unit = "pp" if is_rate else "%"

    return {
        "name": name or series.name or "unknown",
        "score": score,
        "health_z": round(float(z_h), 3),
        "percentile": None if thin_window else round(pct, 1),
        "z_score": None if thin_window else round(float(z_report), 2),
        "current_value": round(current_val, 4),
        "last_date": last_date,
        "yoy_change": yoy,
        "yoy_unit": yoy_unit,
        "invert": invert,
        "history_n": len(window),
        "thin_window": thin_window,
    }


def composite_score(scores: list, weights: Optional[list] = None) -> float:
    """Weighted average на score dict-ове или числа."""
    if not scores:
        return 50.0

    vals = []
    for s in scores:
        if isinstance(s, dict):
            vals.append(s.get("score", 50.0))
        else:
            vals.append(float(s))

    if weights is None:
        weights = [1.0] * len(vals)

    total = sum(w * v for w, v in zip(weights, vals))
    return round(total / sum(weights), 1)


def get_regime(score: float, regimes: list) -> tuple:
    """(label, color) за score спрямо regime таблица.
    regimes = [(threshold, label, color), ...] — сортирани низходящо."""
    for threshold, label, color in sorted(regimes, reverse=True):
        if score >= threshold:
            return label, color
    return regimes[-1][1], regimes[-1][2]


def build_sparkline(series: pd.Series, months: int = 24) -> dict:
    """Последните N месеца като sparkline данни."""
    cutoff = pd.Timestamp.now() - pd.DateOffset(months=months)
    recent = series[series.index >= cutoff].dropna()
    if len(recent) == 0:
        return {"dates": [], "values": []}
    return {
        "dates": [str(d.date()) for d in recent.index],
        "values": [round(float(v), 4) for v in recent.values],
    }


def build_historical_context(
    series: pd.Series,
    current_val: float,
    history_start: str = "1999-01-01",
) -> dict:
    """Min, max, mean, percentile band от history_start насам."""
    history = series[series.index >= pd.Timestamp(history_start)].dropna()
    if len(history) == 0:
        return {}
    return {
        "min": round(float(history.min()), 4),
        "max": round(float(history.max()), 4),
        "mean": round(float(history.mean()), 4),
        "median": round(float(history.median()), 4),
        "p25": round(float(history.quantile(0.25)), 4),
        "p75": round(float(history.quantile(0.75)), 4),
        "since": history_start,
        "n_obs": len(history),
    }


# ─── helpers ─────────────────────────────────────────────────────

def _calc_change(series: pd.Series, as_pp: bool = False) -> Optional[float]:
    """YoY промяна между current и стойност отпреди година.

    Args:
        as_pp: ако True → връща absolute pp delta (cur − old);
               ако False → връща relative % change ((cur − old) / |old| * 100).

    pp mode се ползва за rate/percentage series (UNRATE, HICP YoY, DFR), където
    relative % change на percentage е объркваща (HICP от 2.4% → 2.0% YoY е
    "-0.4pp", не "-16.7%").
    """
    try:
        now = series.index[-1]
        year_ago = now - pd.DateOffset(years=1)
        past = series[series.index <= year_ago]
        if len(past) == 0:
            return None
        old_val = float(past.iloc[-1])
        cur_val = float(series.iloc[-1])
        if as_pp:
            return round(cur_val - old_val, 2)
        if old_val == 0:
            return None
        return round((cur_val - old_val) / abs(old_val) * 100, 2)
    except Exception:
        return None


# Backward-compat alias (старият export name)
_calc_yoy = _calc_change


def _empty_score(name: str) -> dict:
    return {
        "name": name,
        "score": 50.0,
        "percentile": 50.0,
        "z_score": 0.0,
        "current_value": None,
        "last_date": None,
        "yoy_change": None,
        "yoy_unit": "%",
        "invert": False,
        "history_n": 0,
        "thin_window": True,
    }
