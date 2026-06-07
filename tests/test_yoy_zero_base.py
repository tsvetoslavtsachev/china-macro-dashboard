"""Tests за zero/near-zero база guard в YoY/MoM примитивите (parity с US/EU, нишка 7).

База минаваща през 0 → pct_change ±inf (фалшив екстремум) → guard заменя с NaN.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

from core.primitives import yoy_pct, mom_pct


def make_monthly(vals, start="2010-01-01"):
    return pd.Series([float(v) for v in vals],
                     index=pd.date_range(start, periods=len(vals), freq="MS"))


def test_yoy_zero_base_is_nan_not_inf():
    out = yoy_pct(make_monthly([0.0] + [1.0] * 11 + [5.0]))
    assert not np.isinf(out.to_numpy()).any()
    assert pd.isna(out.iloc[-1])


def test_mom_zero_base_is_nan():
    out = mom_pct(make_monthly([0.0, 3.0]))
    assert not np.isinf(out.to_numpy()).any()
    assert pd.isna(out.iloc[-1])


def test_normal_series_unaffected():
    out = yoy_pct(make_monthly(list(range(100, 114))))
    assert out.dropna().notna().all()
    assert not np.isinf(out.to_numpy()).any()
