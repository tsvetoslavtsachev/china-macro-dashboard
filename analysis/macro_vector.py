"""
analysis/macro_vector.py
========================
8-dimensional macro state vector за China historical analog engine.

Дименсии (8) — всичките стъпват на свежи месечни NBS/akshare/BIS серии
(свежи към 2026-04/05), за да не дърпа застояла серия „текущия" вектор назад:
  1. cpi_yoy    — CN_CPI_YOY_AK (akshare NBS, вече YoY %)
  2. ppi_yoy    — CN_PPI_YOY (akshare, вече YoY %)
  3. m2_yoy     — CN_M2_YOY (вече YoY %)
  4. retail_yoy — CN_RETAIL_YOY, 3-мес. mma (изглажда Lunar-New-Year Jan/Feb шум)
  5. fai_yoy    — CN_FAI_MOM_YOY, 3-мес. mma (single-month FAI YoY е силно шумен)
  6. house_yoy  — CN_NEW_HOUSE_PRICE (NBS 70 града, YoY %)
  7. pmi        — CN_PMI_MFG_NBS (дифузионен индекс, ниво ~50)
  8. real_10y   — CN_CGB_10Y − CN_CPI_YOY_AK (реален 10г. лихвен процент, pp)

Window: 2008-01-01 → сега. Complete-case прозорецът реално започва **2011-03**
(обвързан от началото на house price серията 2011-01 + 3mma lag) → ~150 месеца.

⚠ Честни ограничения (документирани в briefing-а):
  - z-прозорецът 2011-26 е почти изцяло „China slowdown" ера (без пълен бум-крах
    цикъл) → z-score = отклонение от skorošната норма, не от пълен цикъл.
  - house_yoy (NBS new-home) е policy-floored → подценява реалния имотен distress
    (той е в BIS −7.5% / FAI); месечният property сигнал е по-мек от истинския.
  - ppi_yoy може да носи транзитен base-effect (виж re-base находката).

Различия от US/EU version:
  - Няма Sahm rule / unemployment dim — официалната China безработица е ~5%
    policy-pinned и не носи сигнал (виж data quality бележките).
  - Векторът се строи ДИРЕКТНО от съществуващия 50-сериен snapshot (CN_* ключове),
    БЕЗ отделен ANALOG_FETCH_SPEC — всички 8 серии вече са в дневния snapshot.

Запазен интерфейс (за analog_matcher.py / analog_comparison.py / analog_pipeline.py):
  STATE_VECTOR_DIMS, DIM_LABELS_BG, DIM_UNITS — public consts
  MacroState — dataclass с as_array()
  build_history_matrix, z_score_matrix, build_current_vector — public functions
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd


# ─── Public constants ────────────────────────────────────────────

ANALOG_WINDOW_START = "2008-01-01"  # месечната NBS/akshare ера; complete-case ~2011-03

STATE_VECTOR_DIMS: list[str] = [
    "cpi_yoy",
    "ppi_yoy",
    "m2_yoy",
    "retail_yoy",
    "fai_yoy",
    "house_yoy",
    "pmi",
    "real_10y",
]

DIM_LABELS_BG: dict[str, str] = {
    "cpi_yoy":    "CPI инфлация",
    "ppi_yoy":    "PPI (производствена инфлация)",
    "m2_yoy":     "M2 паричен растеж",
    "retail_yoy": "Търговия на дребно (3мма)",
    "fai_yoy":    "Инвестиции в осн. активи (3мма)",
    "house_yoy":  "Цени на жилища (NBS 70 града)",
    "pmi":        "PMI производство (NBS)",
    "real_10y":   "Реален 10г. лихвен %",
}

DIM_UNITS: dict[str, str] = {
    "cpi_yoy":    "%",
    "ppi_yoy":    "%",
    "m2_yoy":     "%",
    "retail_yoy": "%",
    "fai_yoy":    "%",
    "house_yoy":  "%",
    "pmi":        "",
    "real_10y":   "pp",
}

# Snapshot ключове → дименсии (за прозрачност + тестове)
DIM_SOURCE_KEYS: dict[str, str] = {
    "cpi_yoy":    "CN_CPI_YOY_AK",
    "ppi_yoy":    "CN_PPI_YOY",
    "m2_yoy":     "CN_M2_YOY",
    "retail_yoy": "CN_RETAIL_YOY",
    "fai_yoy":    "CN_FAI_MOM_YOY",
    "house_yoy":  "CN_NEW_HOUSE_PRICE",
    "pmi":        "CN_PMI_MFG_NBS",
    "real_10y":   "CN_CGB_10Y",  # минус CN_CPI_YOY_AK (виж build_history_matrix)
}


# ─── MacroState dataclass ─────────────────────────────────────────

@dataclass
class MacroState:
    """Snapshot на macro state в конкретна дата."""
    as_of: pd.Timestamp
    raw: dict[str, float] = field(default_factory=dict)
    z: dict[str, float] = field(default_factory=dict)

    def as_array(self) -> np.ndarray:
        """z-score vector за cosine similarity (ред = STATE_VECTOR_DIMS)."""
        return np.array([self.z.get(d, np.nan) for d in STATE_VECTOR_DIMS])

    def is_complete(self) -> bool:
        """True ако всички dimensions са set (не NaN)."""
        arr = self.as_array()
        return not np.any(np.isnan(arr))


# ─── Helper transforms ────────────────────────────────────────────

def _to_month_start(s: pd.Series) -> pd.Series:
    """Resample към month-start (period start convention), mean за под-месечни."""
    if s is None or s.empty:
        return pd.Series(dtype=float)
    s = s.copy()
    if not isinstance(s.index, pd.DatetimeIndex):
        s.index = pd.to_datetime(s.index)
    return s.resample("MS").mean().dropna()


# ─── History matrix builder ───────────────────────────────────────

def build_history_matrix(
    snapshot: dict[str, pd.Series],
    window_start: str = ANALOG_WINDOW_START,
) -> pd.DataFrame:
    """От дневния snapshot {series_key → pd.Series} построява monthly DataFrame
    с колоните = STATE_VECTOR_DIMS.

    Чете директно CN_* ключовете (виж DIM_SOURCE_KEYS). Връща празен
    DataFrame ако ключовите серии напълно липсват.
    """
    cols: dict[str, pd.Series] = {}

    cpi = _to_month_start(snapshot.get("CN_CPI_YOY_AK"))
    if not cpi.empty:
        cols["cpi_yoy"] = cpi

    ppi = _to_month_start(snapshot.get("CN_PPI_YOY"))
    if not ppi.empty:
        cols["ppi_yoy"] = ppi

    m2 = _to_month_start(snapshot.get("CN_M2_YOY"))
    if not m2.empty:
        cols["m2_yoy"] = m2

    retail = _to_month_start(snapshot.get("CN_RETAIL_YOY"))
    if not retail.empty:
        cols["retail_yoy"] = retail.rolling(3).mean()

    fai = _to_month_start(snapshot.get("CN_FAI_MOM_YOY"))
    if not fai.empty:
        cols["fai_yoy"] = fai.rolling(3).mean()

    house = _to_month_start(snapshot.get("CN_NEW_HOUSE_PRICE"))
    if not house.empty:
        cols["house_yoy"] = house

    pmi = _to_month_start(snapshot.get("CN_PMI_MFG_NBS"))
    if not pmi.empty:
        cols["pmi"] = pmi

    # real_10y = 10г. доходност − CPI YoY (реален лихвен процент)
    cgb = _to_month_start(snapshot.get("CN_CGB_10Y"))
    if not cgb.empty and not cpi.empty:
        idx = cgb.index.intersection(cpi.index)
        if len(idx):
            cols["real_10y"] = (cgb.loc[idx] - cpi.loc[idx]).dropna()

    if not cols:
        return pd.DataFrame(columns=STATE_VECTOR_DIMS)

    df = pd.DataFrame(cols)
    df = df.reindex(columns=STATE_VECTOR_DIMS)  # стабилен column order
    df = df[df.index >= pd.Timestamp(window_start)]
    return df


def z_score_matrix(history_df: pd.DataFrame) -> pd.DataFrame:
    """Z-score всяка колонка спрямо собствената history."""
    if history_df.empty:
        return history_df

    z = pd.DataFrame(index=history_df.index, columns=history_df.columns, dtype=float)
    for col in history_df.columns:
        s = history_df[col].dropna()
        if len(s) < 2 or s.std() == 0:
            z[col] = 0.0
        else:
            mean = s.mean()
            std = s.std()
            z[col] = (history_df[col] - mean) / std
    return z


def build_current_vector(
    history_df: pd.DataFrame,
    z_df: Optional[pd.DataFrame] = None,
    today: Optional[pd.Timestamp] = None,
) -> Optional[MacroState]:
    """Връща MacroState за последния complete-case observation в history_df.

    Args:
        history_df: history matrix (от build_history_matrix)
        z_df: precomputed z-score matrix; ако None, изчислява го
        today: cut-off дата (default = последната налична)

    Returns:
        MacroState с raw + z за последния complete-case ред (всички dims),
        или None ако няма такъв ред.
    """
    if history_df.empty:
        return None

    if z_df is None:
        z_df = z_score_matrix(history_df)

    df = history_df
    if today is not None:
        df = df[df.index <= today]
        if df.empty:
            return None

    available_dims = [d for d in STATE_VECTOR_DIMS if d in df.columns]
    if not available_dims:
        return None

    complete_mask = df[available_dims].notna().all(axis=1)
    if not complete_mask.any():
        return None

    last_complete_idx = df[complete_mask].index[-1]

    last_row = df.loc[last_complete_idx]
    last_z_row = z_df.loc[last_complete_idx] if last_complete_idx in z_df.index else None
    if last_z_row is None:
        return None

    raw = {
        col: float(last_row[col])
        for col in STATE_VECTOR_DIMS
        if col in last_row.index and pd.notna(last_row[col])
    }
    z = {
        col: float(last_z_row[col])
        for col in STATE_VECTOR_DIMS
        if col in last_z_row.index and pd.notna(last_z_row[col])
    }

    return MacroState(as_of=last_complete_idx, raw=raw, z=z)
