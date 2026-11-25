"""
analysis/crosscheck.py
======================
ПРОЛЕТР4 (25.11.2026): кръстосани проверки на akshare срещу независим препубликатор
(chinadata.live) и сплитане на опашка за TSF.

Резултатът се закача към самата серия в `series.attrs` (за да не сменя формата на
snapshot-а) и export_api.build_series_data го копира в `meta`:

    meta.crosscheck = {"source": "chinadata.live/china-industrial-output", "tolerance": 0.15,
                       "window": 6, "n": 6, "max_diff": 0.0, "ok": True}
    meta.splice     = {"source": ..., "from": "2026-05-01", "n_overlap": 7, "max_rel_diff": 0.0095, ...}

Правила:
  - ok=False (и logger.warning) при |diff| > допуска на ПОНЕ един от последните `window`
    общи месеци. Серията се запазва; флагът е видим.
  - ok=None (и warning) когато проверката не може да се направи (референтният ред не се
    изтегли, или общите месеци са по-малко от MIN_COMMON).
  - ВНОС: без проверка. Нивата на вноса в chinadata.live не съвпадат с akshare и не се смесват.
Нищо от тук не хвърля към извикващия: провал на референтния ред е ok=None, не срив на износа.
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Optional

import pandas as pd

logger = logging.getLogger(__name__)

WINDOW = 6
MIN_COMMON = 3
SPLICE_TOL = 0.01      # 1 % относително
SPLICE_MIN_OVERLAP = 3

# series_key -> спецификация на проверката. ref е source_id за ChinaDataLiveAdapter.
CROSSCHECKS: dict[str, dict[str, Any]] = {
    "CN_IP_YOY": {"ref": "china-industrial-output", "tol": 0.15, "derive": None},
    "CN_UNEMP_SURVEYED": {"ref": "china-unemployment", "tol": 0.1, "derive": None},
    # YoY, изведен от нивата на износа (USD млн.) на chinadata: същия месец година по-рано
    "CN_EXPORTS_USD_YOY": {"ref": "china-trade-monthly#export", "tol": 1.0, "derive": "level_yoy"},
}
NOT_CHECKED = {
    "CN_IMPORTS_USD_YOY": "няма проверка: нивата на вноса в chinadata.live не съвпадат с akshare",
}
SPLICES = {
    # akshare е основният; опашката се дописва от chinadata само при съвпадение в припокриването
    "CN_TSF_FLOW": {"ref": "china-tsf-flow", "tol": SPLICE_TOL},
}


def level_yoy(levels: pd.Series) -> pd.Series:
    """YoY % от месечни нива: само там, където има същия месец година по-рано."""
    prev = levels.copy()
    prev.index = prev.index + pd.DateOffset(years=1)
    both = pd.concat([levels.rename("cur"), prev.rename("base")], axis=1, sort=True).dropna()
    both = both[both["base"] != 0]
    return ((both["cur"] / both["base"] - 1.0) * 100.0).sort_index()


def compare_series(primary: pd.Series, ref: pd.Series, tol: float,
                   window: int = WINDOW, min_common: int = MIN_COMMON) -> dict[str, Any]:
    """Сравнява последните `window` ОБЩИ месеца. ok=False ако някой |diff| > tol."""
    p = primary.dropna()
    r = ref.dropna()
    p.index = p.index.to_period("M").to_timestamp()
    r.index = r.index.to_period("M").to_timestamp()
    common = p.index.intersection(r.index).sort_values()
    out: dict[str, Any] = {"tolerance": tol, "window": window}
    if len(common) < min_common:
        out.update({"n": int(len(common)), "max_diff": None, "ok": None,
                    "note": f"твърде малко общи месеци ({len(common)} < {min_common})"})
        return out
    last = common[-window:]
    diffs = (p.loc[last] - r.loc[last]).abs()
    out.update({
        "n": int(len(last)),
        "max_diff": round(float(diffs.max()), 4),
        "worst_month": str(diffs.idxmax().date())[:7],
        "ok": bool(diffs.max() <= tol + 1e-9),
    })
    return out


def splice_series(primary: pd.Series, secondary: pd.Series,
                  tol: float = SPLICE_TOL, min_overlap: int = SPLICE_MIN_OVERLAP
                  ) -> tuple[pd.Series, dict[str, Any]]:
    """Допълва опашката на `primary` със стойностите на `secondary` СЛЕД последната дата на
    primary, но само ако в припокриването всички |secondary/primary - 1| <= tol. Стойностите
    на primary в припокриването остават негови. Връща (серия, инфо); при отказ — primary
    непроменена и инфо.applied=False с причина."""
    p = primary.dropna()
    s = secondary.dropna()
    p.index = p.index.to_period("M").to_timestamp()
    s.index = s.index.to_period("M").to_timestamp()
    common = p.index.intersection(s.index).sort_values()
    info: dict[str, Any] = {"tolerance": tol, "n_overlap": int(len(common)), "applied": False}
    if len(common) < min_overlap:
        info["reason"] = f"припокриване {len(common)} < {min_overlap} месеца"
        return primary, info
    base = p.loc[common]
    rel = ((s.loc[common] - base) / base.abs().where(base != 0)).abs().dropna()
    if rel.empty:
        info["reason"] = "няма сравними стойности"
        return primary, info
    info["max_rel_diff"] = round(float(rel.max()), 5)
    if rel.max() > tol:
        info["reason"] = f"разминаване {rel.max():.4f} > {tol}"
        info["worst_month"] = str(rel.idxmax().date())[:7]
        return primary, info
    tail = s[s.index > p.index.max()]
    info["applied"] = True
    info["spliced_months"] = int(len(tail))
    if tail.empty:
        return primary, info
    info["from"] = str(tail.index.min().date())
    return pd.concat([primary, tail]).sort_index(), info


def annotate_snapshot(snapshot: dict, ref_fetch: Optional[Callable[[str], pd.Series]]) -> dict[str, dict]:
    """Прилага сплитовете (сменя snapshot[key]) и закача crosscheck/splice в series.attrs.

    ref_fetch(source_id) -> Series на chinadata (или хвърля). None = адаптерът липсва.
    Връща {key: {"crosscheck"|"splice"|"note": ...}} за логове/тестове."""
    report: dict[str, dict] = {}
    cache: dict[str, Optional[pd.Series]] = {}

    def _ref(sid: str) -> Optional[pd.Series]:
        if sid not in cache:
            try:
                cache[sid] = ref_fetch(sid) if ref_fetch else None
            except Exception as e:  # noqa: BLE001
                logger.warning(f"crosscheck: референтният ред {sid} не се изтегли — {type(e).__name__}: {e}")
                cache[sid] = None
        return cache[sid]

    for key, spec in SPLICES.items():
        s = snapshot.get(key)
        if not isinstance(s, pd.Series) or s.dropna().empty:
            continue
        ref = _ref(spec["ref"])
        if ref is None or ref.dropna().empty:
            info = {"applied": False, "reason": "референтният ред не е наличен"}
            out = s
        else:
            out, info = splice_series(s, ref, spec["tol"])
        info["source"] = f"chinadata.live/{spec['ref']}"
        out = out.copy()
        out.attrs["splice"] = info
        snapshot[key] = out
        report.setdefault(key, {})["splice"] = info
        if info.get("applied"):
            logger.info(f"splice {key}: +{info.get('spliced_months', 0)} месеца от {info['source']}")
        else:
            logger.warning(f"splice {key}: НЕ е приложен — {info.get('reason')}")

    for key, spec in CROSSCHECKS.items():
        s = snapshot.get(key)
        if not isinstance(s, pd.Series) or s.dropna().empty:
            continue
        ref = _ref(spec["ref"])
        label = f"chinadata.live/{spec['ref']}"
        if ref is None or ref.dropna().empty:
            cc = {"ok": None, "tolerance": spec["tol"], "note": "референтният ред не е наличен"}
        else:
            ref_s = level_yoy(ref) if spec["derive"] == "level_yoy" else ref
            cc = compare_series(s, ref_s, spec["tol"])
        cc["source"] = label
        s.attrs["crosscheck"] = cc
        report.setdefault(key, {})["crosscheck"] = cc
        if cc.get("ok") is False:
            logger.warning(f"CROSSCHECK {key}: РАЗМИНАВАНЕ max_diff={cc['max_diff']} > {cc['tolerance']} "
                           f"({cc.get('worst_month')}) срещу {label}")
        elif cc.get("ok") is None:
            logger.warning(f"crosscheck {key}: не може да се провери — {cc.get('note')}")

    for key, note in NOT_CHECKED.items():
        s = snapshot.get(key)
        if isinstance(s, pd.Series):
            s.attrs["crosscheck"] = {"ok": None, "checked": False, "note": note}
            report.setdefault(key, {})["note"] = note
    return report
