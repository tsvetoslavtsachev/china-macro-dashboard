"""
modules/growth.py
=================
Growth lens за China macro dashboard.

Специфики за Китай:
  - GDP таргет е explicit (~5%) — политически приоритет #1
  - Индустриалното производство е по-надеждна мярка от headline GDP
  - GDP deflator отрицателен → реалният растеж е надценен спрямо номиналния
  - Капиталообразуването (~40% GDP) е investment-driven growth модел

Композит (подобрение 26.11.2026, равни тегла 0.20): БВП тримесечен YoY · индустриално
производство YoY · продажби на дребно YoY · NBS Mfg PMI · NBS Non-Mfg PMI.
Членове на лещата, но не на композита: Caixin PMI (композитен, производствен, услуги).
Годишните WB серии (БВП, индустрия, услуги) са само фон в series_data.

Convention: висок YoY % растеж / PMI > 50 = висок score = здрав растеж.
"""
from __future__ import annotations
from typing import Any

import pandas as pd

from core.scorer import (
    score_series, build_sparkline, build_historical_context, get_regime,
)
from config import HISTORY_START
from catalog.polarity import polarity_for


# ─── Серии в lens-а ──────────────────────────────────────────────
SERIES = {
    # ── Свежи месечни драйвери (re-base 2026-06) — годишните горе остават като фон/readings ──
    "CN_RETAIL_YOY": {
        "label": "Продажби на дребно (месечен YoY %)",
        "invert": False,
        "transform": "level",
        "is_rate": True,
    },
    "CN_PMI_MFG_NBS": {
        "label": "NBS Manufacturing PMI",
        "invert": False,
        "transform": "level",
        "is_rate": False,
    },
    "CN_PMI_NON_MFG_NBS": {
        "label": "NBS Non-Manufacturing PMI",
        "invert": False,
        "transform": "level",
        "is_rate": False,
    },
    # S7 CN-2: независим частен PMI (S&P/Markit Caixin ~650 фирми) — cross-check на
    # официалните NBS; bloomberg-bridge източник (свеж, за разлика от akshare Caixin).
    "CN_PMI_COMPOSITE_CAIXIN": {
        "label": "Caixin Composite PMI (независим частен survey)",
        "invert": False,
        "transform": "level",
        "is_rate": False,
    },
    # ── Свеж контекст (НЕ в композита) ──
    "CN_GDP_GROWTH_Q": {
        "label": "БВП — реален растеж (тримесечен YoY %)",
        "invert": False,
        "transform": "level",
        "is_rate": True,
    },
    # ПРОЛЕТР4: членове на лещата (health_z), НЕ в композита
    "CN_IP_YOY": {
        "label": "Индустриално производство (месечен YoY %, akshare)",
        "invert": False,
        "transform": "level",
        "is_rate": True,
    },
    "CN_PMI_MFG_CAIXIN": {
        "label": "Частен производствен PMI (Caixin/S&P Global)",
        "invert": False,
        "transform": "level",
        "is_rate": False,
    },
    "CN_PMI_SVCS_CAIXIN": {
        "label": "Частен PMI за услуги (Caixin/S&P Global)",
        "invert": False,
        "transform": "level",
        "is_rate": False,
    },
    "CN_CONS_CONF": {
        "label": "Доверие на потребителите (индекс, NBS)",
        "invert": False,   # ПРОЛЕТР4 КТ-1: по-високо доверие = по-здраво
        "transform": "level",
        "is_rate": False,
    },
}

# Композитът стъпва на свежи месечни (2026), И-с-дълга-история серии (валиден percentile).
# Годишните WB серии остават като контекст/readings (фон), не драйвери — виж HANDOFF re-base.
# S7 CN-2: + Caixin composite (независим) за да не стъпва композитът само на NBS.
# Подобрение на състава (26.11.2026): равни тегла върху 5 свежи драйвера; Caixin са членове на лещата
# (health_z), не на композита; годишните WB серии остават само фон в series_data.
COMPOSITE_SERIES  = ["CN_GDP_GROWTH_Q", "CN_IP_YOY", "CN_RETAIL_YOY", "CN_PMI_MFG_NBS", "CN_PMI_NON_MFG_NBS"]
COMPOSITE_WEIGHTS = [0.20,              0.20,       0.20,            0.20,             0.20]

REGIMES = [
    (80, "СИЛНА ЕКСПАНЗИЯ",  "#00c853"),
    (65, "РАСТЕЖ НАД ТАРГЕТ","#69f0ae"),
    (50, "РАСТЕЖ НА ТАРГЕТ", "#ffd600"),
    (35, "ПОД ТАРГЕТ",       "#ff6d00"),
    (0,  "РЕЦЕСИЯ",          "#d50000"),
]


def _apply_transform(series: pd.Series, transform: str) -> pd.Series:
    if transform == "yoy_pct":
        return series.pct_change(periods=12).dropna() * 100
    if transform == "qoq_pct":
        return series.pct_change(periods=4).dropna() * 100
    if transform == "mom_pct":
        return series.pct_change().dropna() * 100
    return series


def run(snapshot: dict[str, pd.Series]) -> dict[str, Any]:
    """Изчислява Growth lens за Китай."""
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

    # China-специфична narrative
    narrative = _build_narrative(indicators)

    return {
        "module": "growth",
        "label": "Растеж и активност",
        "icon": "📈",
        "scores": {
            "activity": {"score": composite, "label": "Активност"},
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
    """China-специфични narrative hints — стъпват на свежите композитни драйвери."""
    hints = []

    retail = indicators.get("CN_RETAIL_YOY")
    if retail:
        val = retail.get("current_value", 0)
        if val < 2:
            hints.append(f"Продажби на дребно {val:+.1f}% YoY — слабо потребление, структурно под пред-COVID нивата.")
        else:
            hints.append(f"Продажби на дребно {val:+.1f}% YoY — потреблението се държи.")

    pmi = indicators.get("CN_PMI_MFG_NBS")
    if pmi:
        val = pmi.get("current_value", 0)
        if val < 50:
            hints.append(f"NBS Manufacturing PMI {val:.1f} — под 50 (свиване).")
        elif val < 50.5:
            hints.append(f"NBS Manufacturing PMI {val:.1f} — на границата 50; крехка активност.")
        else:
            hints.append(f"NBS Manufacturing PMI {val:.1f} — над 50 (експанзия).")

    gdp = indicators.get("CN_GDP_GROWTH_Q")
    if gdp:
        val = gdp.get("current_value", 0)
        hints.append(f"БВП растеж {val:.1f}% — около официалния таргет ~5% (policy-pinned, почти не мърда).")

    return hints
