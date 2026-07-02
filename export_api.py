"""
export_api.py  (China)
======================
Генерира двата статични JSON файла за AI-consumption слоя (Фаза 4 / C3):

  output/api/macro_state.json   — аналитичен слой (composite, lens scores,
                                  cross-lens divergences, top anomalies)
  output/api/series_data.json   — времеви редове за графиките (последните N години)

China-native: ползва СЪЩИЯ pipeline като weekly_briefing.py — 5-те модула
(growth/inflation/labor/credit/property) + analysis/ слоя (B2). Без нови
изчисления, само сериализира вече изчислените резултати в JSON.

Схемата на macro_state.json е ХАРМОНИЗИРАНА с US/EU (region, as_of_date,
executive_summary{composite_score, regime_key, regime_label_bg, narrative},
lenses{...}, top_anomalies, cross_lens_divergences) така че общият
manifest.json builder (export/build_latest.py) работи идентично за трите.

Употреба:
  python export_api.py                  # от cache (без мрежа)
  python export_api.py --refresh        # force-fetch преди export
  python export_api.py --years 10       # последните 10 години в series_data
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd

# ── path setup ──────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

# Windows cp1252 stdout guard
try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:
    pass

from config import MODULE_WEIGHTS, MACRO_REGIMES, overall_composite
from catalog.series import SERIES_CATALOG
from core.scorer import score_series
from analysis.divergence import compute_cross_lens_divergence
from analysis.anomaly import compute_anomalies
from run import _build_adapters, _build_snapshot, _auto_refresh_stale

import modules.growth
import modules.credit
import modules.property
import modules.inflation
import modules.labor

# ── константи ───────────────────────────────────────────────────────────────
OUTPUT_DIR = BASE_DIR / "output" / "api"
HISTORY_START = "1999-01-01"

# Ред на лещите за извеждане (core 4 + China extension "имоти")
MODULES_ORDER = [
    ("growth", "modules.growth"),
    ("inflation", "modules.inflation"),
    ("labor", "modules.labor"),
    ("credit", "modules.credit"),
    ("property", "modules.property"),
]

# REVIEW-03 т.0.2 (P3-fix-A): агрегатен invert/transform lookup от петте
# модула — build_series_data() трябва да score-ва СЪЩАТА (invert+трансформ.)
# серия като модулите (modules/*.py), иначе export-ът дава грешен score
# (напр. CN_YOUTH_UNEMPLOYMENT invert=True излизаше "отличен" при рекорден
# връх; CN_CPI_INDEX transform=yoy_pct се score-ваше на суровото ниво).
# Единен източник = модулните SERIES dict-ове (НЕ hardcode копие тук).
_META_MODULES = [
    modules.growth.SERIES,
    modules.credit.SERIES,
    modules.property.SERIES,
    modules.inflation.SERIES,
    modules.labor.SERIES,
]
SERIES_META: dict[str, dict[str, Any]] = {}
for _series_dict in _META_MODULES:
    for _sid, _meta in _series_dict.items():
        SERIES_META[_sid] = {
            "invert": _meta.get("invert", False),
            "transform": _meta.get("transform", "level"),
        }
del _series_dict, _sid, _meta, _META_MODULES


def _apply_transform(series: pd.Series, transform: str) -> pd.Series:
    """Union на всички transform типове, наблюдавани в петте модула
    (modules/growth.py, credit.py, inflation.py, property.py, labor.py).
    Огледален механизъм — level е no-op passthrough (fallback за неизвестен
    transform стринг), както при всеки модул."""
    if transform == "yoy_pct":
        return series.pct_change(periods=12).dropna() * 100
    if transform == "qoq_pct":
        return series.pct_change(periods=4).dropna() * 100
    if transform == "mom_pct":
        return series.pct_change().dropna() * 100
    if transform == "first_diff":
        return series.diff().dropna()
    return series

# China MACRO_REGIMES BG label → english slug (за regime_key, симетрия с US/EU)
REGIME_KEY_MAP = {
    "ЕКСПАНЗИОНЕН": "expansionary",
    "ЗДРАВ": "healthy",
    "СМЕСЕН": "mixed",
    "ВЛОШАВАЩ СЕ": "deteriorating",
    "РЕЦЕСИОНЕН": "recessionary",
}


def _clean(val: Any) -> Any:
    """NaN/inf → None; numpy скалари → native; за JSON сериализация."""
    if val is None:
        return None
    if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
        return None
    try:
        import numpy as np
        if isinstance(val, (np.integer,)):
            return int(val)
        if isinstance(val, (np.floating,)):
            f = float(val)
            return None if (math.isnan(f) or math.isinf(f)) else f
    except Exception:
        pass
    return val


def _direction_from_score(score: float | None) -> str:
    """Хармонизирана direction от composite score, по праговете на MACRO_REGIMES:
    >=65 (ЗДРАВ/ЕКСПАНЗИОНЕН) → expanding · <35 (РЕЦЕСИОНЕН) → contracting ·
    35–65 (СМЕСЕН/ВЛОШАВАЩ) → mixed. Прозрачно и обяснимо."""
    if score is None or (isinstance(score, float) and math.isnan(score)):
        return "insufficient_data"
    if score >= 65:
        return "expanding"
    if score < 35:
        return "contracting"
    return "mixed"


def _run_modules(snapshot: dict) -> list[dict]:
    import importlib
    results = []
    for name, modpath in MODULES_ORDER:
        try:
            mod = importlib.import_module(modpath)
            results.append(mod.run(snapshot))
        except Exception as e:
            print(f"  ⚠ модул {name} се провали: {e}")
    return results


def _overall_composite(results: list[dict]) -> float:
    return overall_composite(results)   # config: None-safe reweight върху backed лещи (#9)


def _overall_regime(overall: float) -> tuple[str, str]:
    """Връща (regime_label_bg, regime_key) по MACRO_REGIMES праговете."""
    for threshold, label, _color in MACRO_REGIMES:
        if overall >= threshold:
            return label, REGIME_KEY_MAP.get(label, label)
    return "—", "unknown"


def _series_regime(score) -> str | None:
    """Per-series режим-етикет от 0–100 score (същите MACRO_REGIMES прагове като
    композита). Заменя `score_data.get("regime_label")` — score_series НЕ връща
    такъв ключ (нито `regime`), затова `latest.regime` беше null по конструкция."""
    if score is None or (isinstance(score, float) and math.isnan(score)):
        return None
    return _overall_regime(score)[0]


# ── macro_state.json builder ─────────────────────────────────────────────────
def build_macro_state(snapshot: dict, today: date) -> dict:
    print("  🧮 Изпълнявам 5-те модула...")
    results = _run_modules(snapshot)

    overall = _overall_composite(results)
    regime_label_bg, regime_key = _overall_regime(overall)

    print("  🧮 Изчислявам cross-lens divergences...")
    cross_report = compute_cross_lens_divergence(snapshot)
    print("  🧮 Изчислявам anomalies...")
    anomaly_report = compute_anomalies(snapshot, z_threshold=2.0, top_n=15)

    # ── Per-lens (модулен) summary ──────────────────────────────────────────
    lenses_out = {}
    for r in results:
        score = round(float(r["composite"]), 1) if r.get("composite") is not None else None
        # key_readings: компактен native слой (label/value/percentile където има)
        readings = []
        for kr in (r.get("key_readings") or [])[:4]:
            readings.append({
                "label": kr.get("label"),
                "value": _clean(kr.get("value")),
                "percentile": _clean(kr.get("percentile")),
            })
        lenses_out[r["module"]] = {
            "score": _clean(score),
            "direction": _direction_from_score(score),
            "regime": r.get("regime"),
            "label_bg": r.get("label"),
            "indicators_count": len(r.get("indicators", {}) or {}),
            "key_readings": readings,
            "narrative": r.get("narrative", []),
        }

    # ── Top anomalies (огледало на US/EU сериализацията) ─────────────────────
    top_anomalies = []
    for a in anomaly_report.top[:10]:
        lens = getattr(a, "lens", None)
        top_anomalies.append({
            "series_id": getattr(a, "series_key", None),
            "name_bg": getattr(a, "series_name_bg", None),
            "lens": lens,
            "peer_group": getattr(a, "peer_group", None),
            "z_score": _clean(getattr(a, "z_score", None)),
            "direction": getattr(a, "direction", None),
            "current_value": _clean(getattr(a, "last_value", None)),
            "last_date": getattr(a, "last_date", None),
            "is_new_extreme": getattr(a, "is_new_extreme", None),
            "new_extreme_direction": getattr(a, "new_extreme_direction", None),
            "stale": getattr(a, "stale", False),
            "periods_behind": _clean(getattr(a, "periods_behind", None)),
            "narrative_hint": getattr(a, "narrative_hint", None),
        })

    # ── Cross-lens divergences ───────────────────────────────────────────────
    cross_divs = []
    for p in cross_report.pairs:
        cross_divs.append({
            "pair_id": getattr(p, "pair_id", None),
            "name_bg": getattr(p, "name_bg", None),
            "question_bg": getattr(p, "question_bg", None),
            "state": getattr(p, "state", None),
            "interpretation": getattr(p, "interpretation", None),
            "slot_a_label": getattr(p, "slot_a_label", None),
            "slot_b_label": getattr(p, "slot_b_label", None),
            "breadth_a": _clean(getattr(p, "breadth_a", None)),
            "breadth_b": _clean(getattr(p, "breadth_b", None)),
        })

    stale_note = (
        f" ({anomaly_report.stale_excluded} застояли изключени)"
        if anomaly_report.stale_excluded else ""
    )
    narrative = (
        f"Претеглен композитен macro score {overall:.1f}/100 → режим „{regime_label_bg}“. "
        f"{len(lenses_out)} лещи, {anomaly_report.total_flagged} flagged аномалии{stale_note}, "
        f"{len(cross_divs)} cross-lens двойки."
    )

    return {
        "region": "CN",
        "as_of_date": str(today),
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "executive_summary": {
            "composite_score": overall,
            "regime_key": regime_key,
            "regime_label_bg": regime_label_bg,
            "css_class": None,
            "narrative": narrative,
            "supporting_signals": [],
            "primary_driver": None,
        },
        "lenses": lenses_out,
        "top_anomalies": top_anomalies,
        "anomalies_stale_excluded": anomaly_report.stale_excluded,
        "anomalies_stale_excluded_keys": list(anomaly_report.stale_excluded_keys),
        "cross_lens_divergences": cross_divs,
        "non_consensus_highlights": [],
    }


# ── series_data.json builder ─────────────────────────────────────────────────
def build_series_data(snapshot: dict, today: date, years: int = 7) -> dict:
    cutoff = pd.Timestamp(today) - pd.DateOffset(years=years)
    series_out = {}

    for series_id, raw_series in snapshot.items():
        if not isinstance(raw_series, pd.Series):
            continue
        meta = SERIES_CATALOG.get(series_id, {})
        filtered = raw_series[raw_series.index >= cutoff].dropna()
        if filtered.empty:
            continue

        lens_list = meta.get("lens", [])
        primary_lens = lens_list[0] if lens_list else "other"
        is_rate = meta.get("is_rate", False)

        # REVIEW-03 т.0.2 (P3-fix-A): invert/transform от SERIES_META (петте
        # модула) — БЕЗ това, invert=True серии (CN_YOUTH_UNEMPLOYMENT) и
        # transform=yoy_pct серии (CN_CPI_INDEX) score-ваха грешно (виж
        # docstring на SERIES_META по-горе). Ключ извън SERIES_META (нито
        # един модул не го носи) → fallback към старото поведение
        # (invert=False, level passthrough) — БЕЗ exception.
        series_meta = SERIES_META.get(series_id, {})
        series_invert = series_meta.get("invert", False)
        series_transform = series_meta.get("transform", "level")
        scored_series = _apply_transform(raw_series, series_transform)

        try:
            score_data = score_series(
                scored_series,
                history_start=meta.get("historical_start", HISTORY_START),
                invert=series_invert,
                name=series_id,
                is_rate=is_rate,
            )
        except Exception:
            score_data = {}

        dates = [str(d.date()) for d in filtered.index]
        values = [_clean(float(v)) for v in filtered.values]

        series_out[series_id] = {
            "meta": {
                "name_bg": meta.get("name_bg", series_id),
                "name_en": meta.get("name_en", series_id),
                "lens": primary_lens,
                "lens_all": lens_list,
                "peer_group": meta.get("peer_group", ""),
                "transform": meta.get("transform", "level"),
                "is_rate": is_rate,
                "release_schedule": meta.get("release_schedule", "monthly"),
                "narrative_hint": meta.get("narrative_hint", ""),
            },
            "latest": {
                "date": str(filtered.index[-1].date()),
                "value": _clean(float(filtered.iloc[-1])),
                "percentile": _clean(score_data.get("percentile")),
                "z_score": _clean(score_data.get("z_score")),
                "score": _clean(score_data.get("score")),
                "regime": _series_regime(score_data.get("score")),
            },
            "chart": {"dates": dates, "values": values},
        }

    return {
        "region": "CN",
        "last_updated": datetime.utcnow().isoformat() + "Z",
        "years_included": years,
        "series_count": len(series_out),
        "series": series_out,
    }


def _safe_dump(obj: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, default=str)


def main(args) -> int:
    today = date.today()
    print("\n" + "═" * 60)
    print("  🇨🇳  Export API JSON (China)  —  macro_state + series_data")
    print("═" * 60 + "\n")

    adapters = _build_adapters()
    if args.refresh:
        from catalog.series import series_by_source
        print("🔄 --refresh: force fetch...")
        for source_name, adapter in adapters.items():
            specs = [
                {"key": s["_key"], "source_id": s["id"], "release_schedule": s["release_schedule"]}
                for s in series_by_source(source_name)
            ]
            if specs:
                adapter.fetch_many(specs, force=True)
    else:
        _auto_refresh_stale(adapters, verbose=True)

    snapshot = _build_snapshot(adapters, force=False)
    if not snapshot:
        print("⚠ Snapshot е празен. Стартирай `python run.py --status --refresh` първо.")
        return 1
    print(f"📦 Snapshot: {len(snapshot)} серии\n")

    print("📝 Генерирам macro_state.json...")
    macro_state = build_macro_state(snapshot, today)
    _safe_dump(macro_state, OUTPUT_DIR / "macro_state.json")

    print("📈 Генерирам series_data.json...")
    series_data = build_series_data(snapshot, today, years=args.years)
    _safe_dump(series_data, OUTPUT_DIR / "series_data.json")

    es = macro_state["executive_summary"]
    print(f"\n✅ Done! composite={es['composite_score']} regime={es['regime_key']} "
          f"lenses={len(macro_state['lenses'])} anomalies={len(macro_state['top_anomalies'])} "
          f"series={series_data['series_count']}")
    print(f"   → {OUTPUT_DIR}\n")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="China — export macro_state + series_data JSON.")
    parser.add_argument("--refresh", action="store_true", help="Force-fetch преди export.")
    parser.add_argument("--years", type=int, default=7, help="Години история в series_data (default 7).")
    raise SystemExit(main(parser.parse_args()))
