"""
modules/property.py
===================
Property & Investment lens за China macro dashboard.

Специфики за Китай:
  - Имотният сектор е ~25-30% от GDP (директно + индиректно)
  - Evergrande (2021) и Country Garden (2023) са симптоми на системен проблем
  - Цените на нови жилища (70 града) са отрицателни YoY от 2023
  - Търговският баланс е рекорден 2024 — геополитически фактор
  - FDI срина се до исторически минимум (0.1% GDP 2024) — de-risking

Състав (подобрение 26.11.2026, равни тегла 0.25): цени на нови жилища (70 града) ·
инвестиции в имоти YTD YoY · FAI · BIS жилищни цени YoY. Членове на лещата, но не на
композита: продажби на жилища. Износът, текущата сметка и курсът са във външната леща
(modules/external.py); годишните WB серии са само фон в series_data.
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
    "CN_NEW_HOUSE_PRICE": {
        "label": "Цени на нови жилища — 70 града (YoY %)",
        "invert": False,
        "transform": "level",  # AkShare вече дава YoY % (индекс - 100)
        "is_rate": True,
    },
    # ── Свежи драйвери (re-base 2026-06) — годишните WB серии остават като readings/фон ──
    "CN_BIS_PROPERTY_YOY": {
        "label": "Жилищни имотни цени (YoY %, BIS номинал)",
        "invert": False,   # по-ниски цени = по-лошо
        "transform": "level",
        "is_rate": True,
    },
    "CN_FAI_MOM_YOY": {
        "label": "Инвестиции в дълготрайни активи (месечен YoY %)",
        "invert": False,   # свиване на инвестициите = по-лошо
        "transform": "level",
        "is_rate": True,
    },
    "CN_RE_INVEST_YOY": {
        "label": "Инвестиции в имоти — YTD YoY %",
        "invert": False,
        "transform": "level",
        "is_rate": True,
    },
    "CN_PROPERTY_SALES_YOY": {
        "label": "Продажби на жилища (площ) — YTD YoY %",
        "invert": False,
        "transform": "level",
        "is_rate": True,
    },
}

# Композитът: 70-градски къщи (akshare, месечно) + BIS имотни цени (тримесечно, по-широко
# покритие) + FAI (инвестиционен импулс, месечно) + текуща сметка (годишен external anchor).
COMPOSITE_SERIES  = ["CN_NEW_HOUSE_PRICE", "CN_RE_INVEST_YOY", "CN_FAI_MOM_YOY", "CN_BIS_PROPERTY_YOY"]
COMPOSITE_WEIGHTS = [0.25,                 0.25,               0.25,             0.25]

REGIMES = [
    (75, "СИЛЕН ИНВЕСТИЦИОНЕН ЦИКЪЛ", "#00c853"),
    (60, "УМЕРЕН РАСТЕЖ",             "#69f0ae"),
    (45, "СТАГНАЦИЯ В ИМОТИТЕ",       "#ffd600"),
    (30, "ИМОТНА КОРЕКЦИЯ",           "#ff6d00"),
    (0,  "ИМОТНА КРИЗА",              "#d50000"),
]


def _apply_transform(series: pd.Series, transform: str) -> pd.Series:
    if transform == "yoy_pct":
        return series.pct_change(periods=12).dropna() * 100
    if transform == "mom_pct":
        return series.pct_change().dropna() * 100
    return series


def run(snapshot: dict[str, pd.Series]) -> dict[str, Any]:
    """Изчислява Property & Trade lens за Китай."""
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
        "module": "property",
        "label": "Имоти и инвестиции",
        "icon": "🏗️",
        "scores": {
            "investment": {"score": composite, "label": "Инвестиционен цикъл"},
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

    house = indicators.get("CN_NEW_HOUSE_PRICE")
    if house:
        val = house.get("current_value", 0)
        if val < -5:
            hints.append(f"⚠️ Цени на жилища {val:.1f}% YoY — значителна корекция. Evergrande/Country Garden ефект.")
        elif val < 0:
            hints.append(f"Цени на жилища {val:.1f}% YoY — отрицателни. Имотният сектор под натиск.")
        else:
            hints.append(f"Цени на жилища (70 града, нови) +{val:.1f}% YoY — стабилизация след корекцията.")

    fai = indicators.get("CN_FAI_MOM_YOY")
    if fai:
        val = fai.get("current_value", 0)
        if val < 0:
            hints.append(f"⚠️ Инвестиции в дълготрайни активи {val:.1f}% YoY (месечно) — рязко свиване на инвестиционния цикъл.")

    bis = indicators.get("CN_BIS_PROPERTY_YOY")
    if bis:
        val = bis.get("current_value", 0)
        if val < 0:
            hints.append(f"BIS жилищни цени {val:.1f}% YoY — по-широкото покритие (вкл. вторичен пазар) още дълбоко отрицателно, въпреки стабилизацията на новия 70-градски пазар.")

    re_inv = indicators.get("CN_RE_INVEST_YOY")
    if re_inv:
        val = re_inv.get("current_value", 0)
        if val < 0:
            hints.append(f"Инвестиции в имоти {val:.1f}% YoY (от началото на годината) — свиването на строителния цикъл продължава.")

    return hints
