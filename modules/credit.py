"""
modules/credit.py
=================
Credit & Monetary Policy lens за China macro dashboard.

Специфики за Китай:
  - PBoC управлява чрез лихвени проценти (LPR/repo), RRR и кредитни квоти
  - China Credit Impulse (промяна в новия кредит като % от GDP) е
    доказан глобален leading indicator (leads global PMI с 6-12 месеца)
  - Кредитът към частния сектор е 194% от GDP — debt overhang
  - M2 е 227% от GDP — най-висок в света сред G20
  - CNY/USD е управляван флоат — PBoC контролира дневния band

Composite weights:
  Policy rate      0.25 — PBoC stance (намаляване = easing)
  Lending rate     0.20 — реален cost of credit
  Credit/GDP       0.25 — кредитна дълбочина и debt overhang
  M2/GDP           0.20 — монетарна маса
  CNY/USD          0.10 — валутен курс (слабо CNY = конкурентност)

Convention:
  - Ниски лихви = easing = по-добре за растеж → invert=True за rate серии
  - Висок кредит/GDP = debt overhang = по-лошо → invert=True
  - Слабо CNY (висок CNY/USD) = по-добре за exports → invert=False
"""
from __future__ import annotations
from typing import Any

import pandas as pd

from core.scorer import (
    score_series, build_sparkline, build_historical_context, get_regime,
)
from config import HISTORY_START


SERIES = {
    "CN_POLICY_RATE": {
        "label": "Политическа лихва — PBoC 7-day repo (%)",
        "invert": True,   # по-ниска = easing = по-добре
        "transform": "level",
        "is_rate": False,
    },
    "CN_LENDING_RATE": {
        "label": "Кредитна лихва (%)",
        "invert": True,   # по-ниска = по-евтин кредит = по-добре
        "transform": "level",
        "is_rate": False,
    },
    "CN_DEPOSIT_RATE": {
        "label": "Депозитна лихва (%)",
        "invert": True,
        "transform": "level",
        "is_rate": False,
    },
    "CN_CREDIT_PRIVATE": {
        "label": "Кредит към частния сектор (% от БВП)",
        "invert": True,   # висок кредит/GDP = debt overhang = по-лошо
        "transform": "level",
        "is_rate": False,
    },
    "CN_M2_GDP": {
        "label": "М2 — дял от БВП (%)",
        "invert": False,  # по-висок M2 = повече ликвидност = неутрален
        "transform": "level",
        "is_rate": False,
    },
    "CN_CNY_USD": {
        "label": "Валутен курс CNY/USD",
        "invert": False,
        "transform": "level",
        "is_rate": False,
    },
    # ── Свежи драйвери (re-base 2026-06) — годишните CREDIT_PRIVATE/M2_GDP остават като readings ──
    "CN_LPR_1Y": {
        "label": "1-годишен Loan Prime Rate (%)",
        "invert": True,    # по-ниска = easing = по-добре
        "transform": "level",
        "is_rate": True,
    },
    # S7 CN-1 fix: catalog-only досега → SERIES_META fallback invert=False →
    # рекордно нисък ипотечен LPR четеше "17.6 РЕЦЕСИОНЕН" вместо easing (~82).
    # LPR клас = rate, по-ниска = easing = по-добре → invert=True. Reading, НЕ в
    # композита (COMPOSITE_SERIES остава непроменен — 1Y LPR носи policy stance).
    "CN_LPR_5Y": {
        "label": "5-годишен Loan Prime Rate — mortgage benchmark (%)",
        "invert": True,    # по-ниска = easing = по-добре (ипотечен бенчмарк)
        "transform": "level",
        "is_rate": True,
    },
    "CN_BIS_CREDIT_GDP": {
        "label": "Кредит към частния нефинансов сектор (% от БВП, BIS)",
        "invert": True,    # висок дял = debt overhang = по-лошо
        "transform": "level",
        "is_rate": False,
    },
    "CN_M2_YOY": {
        "label": "M2 паричен агрегат (месечен YoY %)",
        "invert": False,   # по-висок паричен растеж = повече ликвидност
        "transform": "level",
        "is_rate": True,
    },
    "CN_TSF_FLOW": {
        "label": "Total Social Financing — поток (месечен)",
        "invert": False,   # по-висок поток = по-силен кредитен импулс
        "transform": "level",
        "is_rate": False,
    },
}

# Композитът: LPR (текуща policy stance) + BIS кредит/БВП (debt overhang, тримесечно) +
# M2 YoY РАСТЕЖ (реални текущи парични условия, вместо подвеждащото M2/БВП ниво) + TSF импулс.
COMPOSITE_SERIES  = ["CN_LPR_1Y", "CN_BIS_CREDIT_GDP", "CN_M2_YOY", "CN_TSF_FLOW", "CN_CNY_USD"]
COMPOSITE_WEIGHTS = [0.20,        0.20,                0.25,         0.20,          0.15]

REGIMES = [
    (75, "СИЛНО МОНЕТАРНО СТИМУЛИРАНЕ", "#00c853"),
    (60, "УМЕРЕНО СТИМУЛИРАНЕ",         "#69f0ae"),
    (45, "НЕУТРАЛНА ПОЛИТИКА",          "#ffd600"),
    (30, "УМЕРЕНО ЗАТЯГАНЕ",            "#ff6d00"),
    (0,  "РЕСТРИКТИВНА ПОЛИТИКА",       "#d50000"),
]


def _apply_transform(series: pd.Series, transform: str) -> pd.Series:
    if transform == "yoy_pct":
        return series.pct_change(periods=12).dropna() * 100
    if transform == "first_diff":
        return series.diff().dropna()
    return series


def run(snapshot: dict[str, pd.Series]) -> dict[str, Any]:
    """Изчислява Credit & Monetary Policy lens за Китай."""
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
                    invert=meta["invert"],
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
        "module": "credit",
        "label": "Монетарна политика и кредит",
        "icon": "🏦",
        "scores": {
            "monetary": {"score": composite, "label": "Монетарни условия"},
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

    lpr = indicators.get("CN_LPR_1Y")
    policy = indicators.get("CN_POLICY_RATE")
    if lpr:
        val = lpr.get("current_value", 0)
        hints.append(f"1Y LPR {val:.2f}% — на/близо до исторически дъна; активен easing цикъл.")
    elif policy:
        val = policy.get("current_value", 0)
        hints.append("PBoC policy rate {:.2f}% — {}".format(
            val, "активен easing цикъл." if val < 2.0 else "умерено ниво."))

    bis = indicators.get("CN_BIS_CREDIT_GDP")
    if bis:
        val = bis.get("current_value", 0)
        if val > 190:
            hints.append(f"Кредит към частния нефинансов сектор {val:.0f}% от БВП (BIS) — debt overhang. Ограничава трансмисията на политиката.")

    m2 = indicators.get("CN_M2_YOY")
    if m2:
        val = m2.get("current_value", 0)
        if val < 9:
            hints.append(f"M2 растеж {val:.1f}% YoY — исторически слаб. Лихвите паднаха, но кредитът не се ускорява (слаба трансмисия).")
        else:
            hints.append(f"M2 растеж {val:.1f}% YoY.")

    cny = indicators.get("CN_CNY_USD")
    if cny:
        val = cny.get("current_value", 0)
        hints.append(f"CNY/USD {val:.4f} — управляван флоат. PBoC контролира дневния band ±2%.")

    return hints
