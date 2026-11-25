"""PROLETR4: лещов health_z (analysis/health.py)."""
import pandas as pd
import pytest

from analysis.health import lens_health, ALL_STALE_NOTE

TODAY = "2026-11-23"
FRESH = pd.Timestamp("2026-10-31")      # месечна, ~1 период назад
OLD = pd.Timestamp("2025-01-31")        # месечна, >3 периода


def _ind(z, cur=1.0):
    return {"health_z": z, "current_value": cur}


def _call(ids, inds, pg, last, sched=None):
    return lens_health(ids, inds, pg, last,
                       sched or {i: "monthly" for i in ids}, TODAY)


def test_hand_computed_value():
    # peer A: (1.0, 3.0) -> 2.0 ; peer B: (-1.0) -> -1.0 ; тежести 1.0 -> (2 + -1)/2 = 0.5
    ids = ["a1", "a2", "b1"]
    r = _call(ids, {"a1": _ind(1.0), "a2": _ind(3.0), "b1": _ind(-1.0)},
              {"a1": "A", "a2": "A", "b1": "B"}, {i: FRESH for i in ids})
    assert r["health_z"] == pytest.approx(0.5)
    assert r["n_series"] == 3 and r["excluded_stale"] == []


def test_stale_series_excluded():
    # MUTATION PROOF: ако изключването на стари серии се махне, a2 (z=9) вдига резултата.
    ids = ["a1", "a2"]
    r = _call(ids, {"a1": _ind(1.0), "a2": _ind(9.0)}, {"a1": "A", "a2": "A"},
              {"a1": FRESH, "a2": OLD})
    assert r["excluded_stale"] == ["a2"]
    assert r["n_series"] == 1
    assert r["health_z"] == pytest.approx(1.0)


def test_all_stale_gives_none_and_flag():
    ids = ["a1", "a2"]
    r = _call(ids, {"a1": _ind(1.0), "a2": _ind(2.0)}, {"a1": "A", "a2": "A"},
              {"a1": OLD, "a2": OLD})
    assert r["health_z"] is None and r["all_stale"] is True
    assert r["excluded_stale"] == ["a1", "a2"]
    assert ALL_STALE_NOTE == "всички серии в лещата са стари"


def test_empty_score_not_counted_as_zero():
    from core.scorer import _empty_score
    ids = ["a1", "a2"]
    r = _call(ids, {"a1": _ind(2.0), "a2": _empty_score("x")}, {"a1": "A", "a2": "A"},
              {i: FRESH for i in ids})
    assert r["n_series"] == 1
    assert r["health_z"] == pytest.approx(2.0)     # не 1.0 (което би дало z=0 за a2)
    assert r["all_stale"] is False


def test_stale_rule_same_as_series_data():
    # едно и също правило като build_series_data (latest.stale)
    from analysis.anomaly import _periods_behind, _is_stale
    from analysis.health import series_is_stale
    for sched in ("monthly", "quarterly", "annually", "daily"):
        for last in (FRESH, OLD, pd.Timestamp("2026-03-31")):
            pb = _periods_behind(last, pd.Timestamp(TODAY), sched)
            assert series_is_stale(last, TODAY, sched) == _is_stale(pb, sched)
