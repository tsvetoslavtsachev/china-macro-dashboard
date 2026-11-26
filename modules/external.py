"""
modules/external.py
===================
Външна леща (търговия, курс, резерви) за China macro dashboard — 6-а леща, нова от
подобрението на състава (26.11.2026); излязла от старата леща "Имоти и търговия".

Специфики за Китай:
  - Износът е основният външен двигател; рекорден търговски излишък 2024 → търговско напрежение
  - Юанът е управляван флоат: курсът (CNY за 1 USD) и реалният ефективен курс (BIS) заедно
    показват конкурентоспособност и натиск за изтичане на капитал
  - Резервите и текущата сметка са буферът (текущата сметка е годишна: в лещата, не в композита)

Композит (равни по дух тегла): износ USD YoY 0.40 · реален ефективен курс 0.30 · курс CNY/USD 0.30.
Членове на лещата, но не на композита: внос USD YoY, валутни резерви, текуща сметка (годишна).

Convention (catalog/polarity.py):
  - Износ/внос/резерви/текуща сметка: нагоре = по-здраво (+1)
  - Курс CNY/USD (юана за 1 USD): +1 (по-слаб юан = по-добра ценова конкурентност, запазено от старата леща)
  - REER: нагоре = по-скъп юан = по-слаба конкурентност (-1), като EA_REER в EU каталога
"""
from __future__ import annotations
from typing import Any

import pandas as pd

from core.scorer import (
    score_series, build_sparkline, build_historical_context, get_regime,
)
from config import HISTORY_START
from catalog.polarity import polarity_for


SERIES = {
    "CN_EXPORTS_USD_YOY": {
        "label": "Износ USD (месечно YoY %)",
        "invert": False,
        "transform": "level",
        "is_rate": True,
    },
    "CN_REER": {
        "label": "Реален ефективен курс на юана (BIS, индекс)",
        "invert": True,
        "transform": "level",
        "is_rate": False,
    },
    "CN_CNY_USD": {
        "label": "Валутен курс CNY/USD (юана за 1 долар)",
        "invert": False,
        "transform": "level",
        "is_rate": False,
    },
    "CN_IMPORTS_USD_YOY": {
        "label": "Внос USD (месечно YoY %)",
        "invert": False,
        "transform": "level",
        "is_rate": True,
    },
    "CN_FX_RESERVES": {
        "label": "Валутни резерви",
        "invert": False,
        "transform": "level",
        "is_rate": False,
    },
    "CN_CURRENT_ACCOUNT": {
        "label": "Текуща сметка - баланс (годишно, % от БВП)",
        "invert": False,
        "transform": "level",
        "is_rate": False,
    },
}

# Композитът: износ (месечен импулс) + реален ефективен курс + курс към долара.
# Текущата сметка е годишна → само в SERIES (health_z), не в композита.
COMPOSITE_SERIES  = ["CN_EXPORTS_USD_YOY", "CN_REER", "CN_CNY_USD"]
COMPOSITE_WEIGHTS = [0.40,                 0.30,       0.30]

REGIMES = [
    (75, "СИЛНА ВЪНШНА ПОЗИЦИЯ",      "#00c853"),
    (60, "УСТОЙЧИВА ВЪНШНА ПОЗИЦИЯ",  "#69f0ae"),
    (45, "НЕУТРАЛНА ВЪНШНА КАРТИНА",  "#ffd600"),
    (30, "НАТИСК ВЪРХУ ВЪНШНИЯ СЕКТОР", "#ff6d00"),
    (0,  "ВЪНШЕН ШОК",                "#d50000"),
]

def _apply_transform(series: pd.Series, transform: str) -> pd.Series:
    if transform == "yoy_pct":
        return series.pct_change(periods=12).dropna() * 100
    if transform == "mom_pct":
        return series.pct_change().dropna() * 100
    return series


def run(snapshot: dict[str, pd.Series]) -> dict[str, Any]:
    """Изчислява External lens за Китай."""
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
                    polarity=polarity_for(sid),   # O3: централен каталог, не per-серия invert
                    name=meta["label"],
                    is_rate=meta.get("is_rate", False),
                )

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
        "module": "external",
        "label": "Външен сектор и курс",
        "icon": "🌐",
        "scores": {
            "external": {"score": composite, "label": "Външна позиция"},
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

    exp = indicators.get("CN_EXPORTS_USD_YOY")
    if exp:
        val = exp.get("current_value", 0)
        if val < 0:
            hints.append(f"Износ {val:.1f}% YoY (USD) — свиване на външното търсене или търговски бариери.")
        else:
            hints.append(f"Износ {val:+.1f}% YoY (USD) — външното търсене подкрепя растежа.")

    reer = indicators.get("CN_REER")
    if reer:
        val = reer.get("current_value", 0)
        hints.append(f"Реален ефективен курс {val:.1f} (BIS) — по-висок индекс означава по-скъп юан и по-слаба ценова конкурентност.")

    cny = indicators.get("CN_CNY_USD")
    if cny:
        val = cny.get("current_value", 0)
        hints.append(f"CNY/USD {val:.4f} — управляван флоат; PBoC контролира дневния курс.")

    ca = indicators.get("CN_CURRENT_ACCOUNT")
    if ca:
        val = ca.get("current_value", 0)
        if val > 2:
            hints.append(f"Текуща сметка +{val:.1f}% от БВП — голям излишък; износът компенсира слабото вътрешно търсене и носи търговско напрежение.")

    return hints
