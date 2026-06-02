"""
tests/test_analog_engine.py
===========================
Offline тестове за China historical analog engine (Phase 4).

Пазят го China-калибриран (регресионен guard срещу тихо връщане към US/EU копието):
  - STATE_VECTOR_DIMS = 8-те China dims (не EU EA_UNRATE/ECB_DFR/...)
  - HISTORICAL_EPISODES са China епизоди (без Draghi/ECB/Volcker/GFC labels)
  - forward DEFAULT_OUTCOME_DIMS ⊂ China dims
  - build_history_matrix чете CN_* от snapshot; real_10y = CGB − CPI
  - compute_analog_bundle дава кохерентен bundle (comparisons aligned, forward popúlated)

Без мрежа — синтетичен месечен snapshot 2011-2026.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd

from analysis.macro_vector import (
    STATE_VECTOR_DIMS, DIM_LABELS_BG, DIM_UNITS, DIM_SOURCE_KEYS,
    build_history_matrix, z_score_matrix, build_current_vector,
)
from analysis.analog_matcher import (
    HISTORICAL_EPISODES, lookup_episode, find_analogs, classify_strength,
)
from analysis.forward_path import DEFAULT_OUTCOME_DIMS
from analysis.analog_pipeline import compute_analog_bundle


EXPECTED_DIMS = ["cpi_yoy", "ppi_yoy", "m2_yoy", "retail_yoy",
                 "fai_yoy", "house_yoy", "pmi", "real_10y"]


def _synthetic_china_snapshot(n=180, end="2026-04-01"):
    """8-те source серии, месечни 2011→2026, с разнопосочна вариация (за z + cosine)."""
    idx = pd.date_range(end=end, periods=n, freq="MS")
    snap = {}
    for j, key in enumerate(DIM_SOURCE_KEYS.values()):
        base = 2.0 + j
        vals = base + 3.0 * np.sin(np.arange(n) * (0.15 + 0.02 * j) + j)
        snap[key] = pd.Series(vals, index=idx)
    return snap


# ─── China-калибриран регресионен guard ─────────────────────────

def test_state_vector_is_china_not_eu():
    assert STATE_VECTOR_DIMS == EXPECTED_DIMS
    # не са останали EU/US dims
    for eu in ("unrate", "core_hicp_yoy", "real_dfr", "sovereign_stress", "sahm",
               "real_ffr", "yc_10y2y"):
        assert eu not in STATE_VECTOR_DIMS
    # всеки dim има BG label + unit + source key
    for d in STATE_VECTOR_DIMS:
        assert d in DIM_LABELS_BG and d in DIM_UNITS and d in DIM_SOURCE_KEYS


def test_episodes_are_china_not_eu():
    labels = [e["label"] for e in HISTORICAL_EPISODES]
    joined = " ".join(labels)
    for foreign in ("Draghi", "ECB", "Volcker", "Dotcom", "PEPP", "Bund", "Sahm"):
        assert foreign not in joined
    # познати China епизоди се мапват правилно
    assert lookup_episode(pd.Timestamp("2022-05-01")) == "Имотна криза + нулев COVID"
    assert lookup_episode(pd.Timestamp("2020-03-01")) == "COVID шок + възстановяване"
    assert lookup_episode(pd.Timestamp("2008-10-01")).startswith("ГФК")
    # дата извън покритието → None
    assert lookup_episode(pd.Timestamp("1999-01-01")) is None


def test_forward_outcome_dims_are_china():
    assert DEFAULT_OUTCOME_DIMS == ["cpi_yoy", "ppi_yoy", "retail_yoy", "house_yoy"]
    assert set(DEFAULT_OUTCOME_DIMS) <= set(STATE_VECTOR_DIMS)


# ─── matrix builder ─────────────────────────────────────────────

def test_build_history_matrix_reads_cn_keys():
    snap = _synthetic_china_snapshot()
    df = build_history_matrix(snap)
    assert list(df.columns) == STATE_VECTOR_DIMS
    # real_10y = CGB − CPI: проверка на стойност на произволен пълен ред
    complete = df.dropna()
    assert len(complete) > 100  # ~180 минус 3mma loss
    row = complete.iloc[-1]
    cgb = snap["CN_CGB_10Y"].resample("MS").mean()
    cpi = snap["CN_CPI_YOY_AK"].resample("MS").mean()
    expected_real = (cgb - cpi).dropna().iloc[-1]
    assert abs(row["real_10y"] - expected_real) < 1e-6


def test_build_history_matrix_empty_when_no_keys():
    df = build_history_matrix({"UNRELATED": pd.Series([1, 2, 3])})
    assert df.empty or df.dropna().empty


# ─── end-to-end bundle ──────────────────────────────────────────

def test_compute_analog_bundle_coherent():
    snap = _synthetic_china_snapshot()
    bundle = compute_analog_bundle(snap)
    assert bundle is not None
    assert bundle.current_state.is_complete()
    assert len(bundle.analogs) >= 1
    # comparisons aligned 1:1 с analogs
    assert len(bundle.comparisons) == len(bundle.analogs)
    # всеки analog има episode label (синтетичните дати са в покритието)
    for a in bundle.analogs:
        assert a.episode_label is not None
        assert -1.0 <= a.similarity <= 1.0
    # forward outcomes — China dims, 3 horizons
    assert set(bundle.forward.dims) <= set(STATE_VECTOR_DIMS)
    assert bundle.forward.horizons == [3, 6, 12]


def test_compute_analog_bundle_none_on_thin_data():
    """Недостатъчна история → None (briefing показва честен fallback, не crash)."""
    idx = pd.date_range(end="2026-04-01", periods=2, freq="MS")
    snap = {k: pd.Series([1.0, 2.0], index=idx) for k in DIM_SOURCE_KEYS.values()}
    assert compute_analog_bundle(snap) is None


def test_classify_strength_thresholds():
    assert classify_strength(0.95) == "strong"
    assert classify_strength(0.80) == "good"
    assert classify_strength(0.60) == "weak"
    assert classify_strength(0.30) == "marginal"
