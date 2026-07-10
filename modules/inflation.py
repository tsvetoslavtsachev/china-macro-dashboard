"""
modules/inflation.py
====================
Inflation lens за China macro dashboard.

Специфики за Китай:
  - Дефлационен риск, не инфлационен (CPI ~0%, GDP deflator < 0)
  - PPI отрицателна → дефлационен натиск в производствения сектор
  - Japan-style deflation scenario е реален риск
  - Инверсия: ниска инфлация = нисък score (дефлация е лоша)
    НО: висока инфлация също е лоша → U-shape scoring
    За простота: score-ваме спрямо optimal range 1-3%

Composite weights:
  CPI YoY (WB)       0.35 — headline, годишен
  GDP deflator       0.25 — по-широка мярка, отрицателна
  CPI Index (IMF)    0.25 — месечен, по-актуален
  PPI Index (IMF)    0.15 — leading indicator за CPI

Convention: score близо до 50 = инфлация в optimal range (1-3%).
  Дефлация (< 0%) → нисък score.
  Хиперинфлация (> 5%) → нисък score.
"""
from __future__ import annotations
from typing import Any

import numpy as np
import pandas as pd

from core.scorer import (
    score_series, build_sparkline, build_historical_context, get_regime,
)
from config import HISTORY_START
from catalog.polarity import polarity_for


SERIES = {
    "CN_CPI_YOY": {
        "label": "ИПЦ — инфлация (YoY %)",
        "invert": False,
        "transform": "level",
        "is_rate": True,
    },
    "CN_GDP_DEFLATOR": {
        "label": "БВП дефлатор (YoY %)",
        "invert": False,
        "transform": "level",
        "is_rate": True,
    },
    "CN_CPI_INDEX": {
        "label": "ИПЦ — индекс (месечен, YoY %)",
        "invert": False,
        "transform": "yoy_pct",
        "is_rate": True,
    },
    "CN_PPI_INDEX": {
        "label": "ИПП — индекс (месечен, YoY %)",
        "invert": False,
        "transform": "yoy_pct",
        "is_rate": True,
    },
    # ── Свежи драйвери (re-base 2026-06) ──
    "CN_CPI_YOY_AK": {
        "label": "ИПЦ — инфлация (месечен YoY %)",
        "invert": False,   # ниска/отрицателна = дефлация = нисък score
        "transform": "level",  # akshare вече дава YoY %
        "is_rate": True,
    },
    "CN_PPI_YOY": {
        "label": "ИПП — производствени цени (месечен YoY %)",
        "invert": False,   # ниски/отрицателни = дефлация = нисък score
        "transform": "level",  # akshare вече дава YoY %
        "is_rate": True,
    },
    "CN_GDP_DEFLATOR_Q": {
        "label": "БВП дефлатор (тримесечен YoY %)",
        "invert": False,
        "transform": "level",
        "is_rate": True,
    },
}

# Композитът: свеж месечен CPI (akshare NBS, замества застоялия IMF CN_CPI_INDEX 2025-07) +
# свеж месечен PPI (замества мъртвия IMF CN_PPI_INDEX 2022-12) + тримесечен дефлатор (absolute
# anchor, виж _deflator_anchor) + годишен CPI (дълга история, фон).
COMPOSITE_SERIES  = ["CN_CPI_YOY_AK", "CN_PPI_YOY", "CN_GDP_DEFLATOR_Q", "CN_CPI_YOY"]
COMPOSITE_WEIGHTS = [0.30,            0.25,         0.25,                0.20]

REGIMES = [
    (75, "ИНФЛАЦИОНЕН НАТИСК", "#ff6d00"),
    (60, "УМЕРЕНА ИНФЛАЦИЯ",   "#ffd600"),
    (45, "ЦЕНОВА СТАБИЛНОСТ",  "#69f0ae"),
    (30, "ДЕФЛАЦИОНЕН РИСК",   "#ff6d00"),
    (0,  "ДЕФЛАЦИЯ",           "#d50000"),
]


def _apply_transform(series: pd.Series, transform: str) -> pd.Series:
    if transform == "yoy_pct":
        return series.pct_change(periods=12).dropna() * 100
    if transform == "mom_pct":
        return series.pct_change().dropna() * 100
    return series


def _deflator_anchor(v: float) -> float:
    """Absolute-anchor score за тримесечния БВП дефлатор (Q1 хибрид).

    Дефлаторът е policy-pinned серия с КЪСА история (n~14, само 2022→) → raw
    percentile е подвеждащ (−0.06% би дал ~86, „инфлационно"). Затова го
    анкерираме абсолютно: дефлация → нисък score, ценова стабилност → среден,
    рефлация → по-висок. Крива:
      ≤ −3%  → 0   (дълбока debt-deflation)
      −3..0  → 0..35 линейно (35 при 0%)
      0..+2  → 35..60 (здрава рефлация)
      +2..+4 → 60..75
      > +4   → 75
    """
    if v <= -3:
        return 0.0
    if v < 0:
        return round(35 * (1 + v / 3), 1)      # -3→0, 0→35
    if v <= 2:
        return round(35 + (v / 2) * 25, 1)      # 0→35, +2→60
    if v <= 4:
        return round(60 + (v - 2) / 2 * 15, 1)  # +2→60, +4→75
    return 75.0


def _score_inflation(value: float) -> float:
    """China-специфично scoring за инфлация.

    Optimal range: 1-3% (PBoC неформален таргет).
    Дефлация (< 0%) → нисък score (лошо).
    Ниска инфлация (0-1%) → средно-нисък score.
    Optimal (1-3%) → висок score.
    Висока (> 4%) → намаляващ score.
    """
    if value < 0:
        # Дефлация: score 0-30
        return max(0, 30 + value * 5)  # -6% → 0, 0% → 30
    elif value < 1:
        # Ниска инфлация: score 30-50
        return 30 + value * 20
    elif value <= 3:
        # Optimal: score 50-80
        return 50 + (value - 1) * 15
    elif value <= 5:
        # Висока: score 80-50
        return 80 - (value - 3) * 15
    else:
        # Много висока: score 50-0
        return max(0, 50 - (value - 5) * 10)


def run(snapshot: dict[str, pd.Series]) -> dict[str, Any]:
    """Изчислява Inflation lens за Китай."""
    indicators: dict[str, dict] = {}
    transformed: dict[str, pd.Series] = {}

    for sid, meta in SERIES.items():
        if sid in snapshot and not snapshot[sid].empty:
            transform = meta.get("transform", "level")
            ts = _apply_transform(snapshot[sid], transform)
            transformed[sid] = ts
            if not ts.empty:
                indicators[sid] = score_series(
                    ts,
                    history_start=HISTORY_START,
                    polarity=polarity_for(sid),   # O3: централен каталог (линейно; score-ът се
                    name=meta["label"],           #     презаписва от абсолютните котви по-долу)
                    is_rate=meta.get("is_rate", False),
                )

    # Инфлация = U-форма около 1-3% band (абсолютна, China-калибрована — по-надеждна
    # от MAD-scaling за policy-pinned серии с ниска вариация). Активира _score_inflation
    # (досега дефинирана, но НЕизползвана). Дефлаторът: специфичен absolute anchor.
    # Виж ../macro-satellite/LENS_SCORING_METHODOLOGY.md §3 (inflation = U около цел).
    for sid, ind in indicators.items():
        cv = ind.get("current_value")
        if cv is None:
            continue
        if sid == "CN_GDP_DEFLATOR_Q":
            ind["score"] = _deflator_anchor(float(cv))
        else:
            ind["score"] = _score_inflation(float(cv))

    composite = _composite(indicators, COMPOSITE_SERIES, COMPOSITE_WEIGHTS)
    regime_label, regime_color = get_regime(composite, REGIMES)

    sparklines: dict[str, dict] = {}
    hist_context: dict[str, dict] = {}
    for sid in SERIES:
        if sid in transformed and not transformed[sid].empty:
            sparklines[sid] = build_sparkline(transformed[sid], months=36)
            hist_context[sid] = build_historical_context(
                transformed[sid],
                float(transformed[sid].iloc[-1]),
                history_start=HISTORY_START,
            )

    narrative = _build_narrative(indicators)

    return {
        "module": "inflation",
        "label": "Инфлация и цени",
        "icon": "🔥",
        "scores": {
            "prices": {"score": composite, "label": "Ценова стабилност"},
        },
        "composite": composite,
        "regime": regime_label,
        "regime_color": regime_color,
        "indicators": indicators,
        "sparklines": sparklines,
        "historical_context": hist_context,
        "key_readings": _key_readings(indicators),
        "narrative": narrative,
    }


def _composite(scores: dict, series_list: list, weights: list) -> float | None:
    vals = [scores[s]["score"] for s in series_list if s in scores]
    wts = [weights[i] for i, s in enumerate(series_list) if s in scores]
    if not vals:
        return None   # няма композитни серии → изключи лещата от headline (#9)
    return round(sum(v * w for v, w in zip(vals, wts)) / sum(wts), 1)


def _key_readings(indicators: dict) -> list[dict]:
    out = []
    for sid in SERIES:
        if sid in indicators:
            s = indicators[sid]
            out.append({
                "id": sid,
                "label": s["name"],
                "value": s["current_value"],
                "date": s["last_date"],
                "yoy": s["yoy_change"],
                "yoy_unit": s.get("yoy_unit", "%"),
                "percentile": s["percentile"],
                "score": s["score"],
            })
    return out


def _build_narrative(indicators: dict) -> list[str]:
    hints = []

    cpi = indicators.get("CN_CPI_YOY_AK") or indicators.get("CN_CPI_YOY")
    if cpi:
        val = cpi.get("current_value", 0)
        if val < 0:
            hints.append(f"⚠️ CPI {val:.1f}% YoY — дефлация. Japan-style сценарий е реален риск.")
        elif val < 1:
            hints.append(f"CPI {val:.1f}% YoY — близо до нула, но рефлира от отрицателните стойности на 2025.")
        elif val <= 3:
            hints.append(f"CPI {val:.1f}% YoY — обратно в долната част на optimal range; потребителската дефлация отслабва.")
        else:
            hints.append(f"CPI {val:.1f}% YoY — над optimal range. Инфлационен натиск.")

    ppi = indicators.get("CN_PPI_YOY")
    if ppi:
        val = ppi.get("current_value", 0)
        if val < 0:
            hints.append(f"PPI {val:.1f}% YoY — производствените цени още в дефлация.")
        else:
            hints.append(f"PPI {val:+.1f}% YoY — производствените цени излязоха от дефлация (от ~−3.6% средата на 2025). Край на 3-годишния PPI спад.")

    deflator = indicators.get("CN_GDP_DEFLATOR_Q") or indicators.get("CN_GDP_DEFLATOR")
    if deflator:
        val = deflator.get("current_value", 0)
        if val < 0:
            hints.append(f"БВП дефлатор {val:.2f}% (тримесечно) — още отрицателен, но най-плитък от началото на debt-deflation (2Q2023). Близо до изход.")
        else:
            hints.append(f"БВП дефлатор {val:+.2f}% — обратно положителен; край на debt-deflation.")

    return hints
