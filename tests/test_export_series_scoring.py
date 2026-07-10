"""
tests/test_export_series_scoring.py
=====================================
REVIEW-03 т.0.2 (P3-fix-A): export_api.build_series_data сервираше score БЕЗ
invert/transform → CN_YOUTH_UNEMPLOYMENT (15.8%, invert=True) излизаше score
99.6 "отлично"; CN_CPI_INDEX се score-ваше на ниво индекс вместо YoY.

Тестовете тук проверяват, че build_series_data (export_api.py) прилага
СЪЩИЯ invert/transform механизъм като модулите (modules/*.py) преди
score_series — консистентно с останалия pipeline.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from export_api import build_series_data, SERIES_META


# ── (а) invert=True на исторически връх → score < 50 ────────────────────────

def test_invert_series_at_historical_peak_scores_low():
    """CN_YOUTH_UNEMPLOYMENT (invert=True в modules/labor.py): серия на
    исторически ВРЪХ (най-високата стойност в прозореца) трябва да score-ва
    ниско (лошо), не високо — invert-ът трябва да е приложен."""
    idx = pd.date_range(end="2026-06-01", periods=60, freq="MS")
    # Възходящ тренд, последната точка е абсолютният връх на прозореца.
    values = np.linspace(5.0, 21.3, 60)
    snapshot = {"CN_YOUTH_UNEMPLOYMENT": pd.Series(values, index=idx)}

    out = build_series_data(snapshot, today=pd.Timestamp("2026-06-01").date(), years=7)
    score = out["series"]["CN_YOUTH_UNEMPLOYMENT"]["latest"]["score"]

    assert score is not None
    assert score < 50, (
        f"CN_YOUTH_UNEMPLOYMENT на исторически връх с invert=True трябва да "
        f"score-ва <50 (лошо), а не {score} — invert не е приложен."
    )


# ── (б) transform=yoy_pct → score съответства на YoY, не на нивото ──────────

def test_transform_yoy_pct_scores_on_transformed_series():
    """CN_CPI_INDEX (transform=yoy_pct в modules/inflation.py): индексна серия
    расте монотонно (нивото винаги е нов връх → score~100 ако не се
    трансформира). YoY растежът обаче е КОНСТАНТЕН (~2%/год за всяка точка от
    прозореца) → score на трансформираната серия трябва да е близо до
    неутрално (~50), защото последната YoY точка не се различава от
    историята на YoY серията."""
    idx = pd.date_range(end="2026-06-01", periods=180, freq="MS")
    # Индекс расте с фиксиран месечен темп → YoY % е ПОСТОЯНЕН през целия прозорец.
    monthly_growth = (1.02) ** (1 / 12)
    index_values = 100.0 * (monthly_growth ** np.arange(180))
    snapshot = {"CN_CPI_INDEX": pd.Series(index_values, index=idx)}

    out = build_series_data(snapshot, today=pd.Timestamp("2026-06-01").date(), years=15)
    latest = out["series"]["CN_CPI_INDEX"]["latest"]

    # Директно смятане на очакваната YoY стойност в последната точка, за
    # сравнение с current_value отразено в score_data (verify чрез самия score
    # механизъм — score трябва да е near-неутрален, НЕ near-100 както би било
    # ако score-ва суровия индекс ниво, което е винаги нов максимум).
    assert latest["score"] is not None
    assert 40 <= latest["score"] <= 60, (
        f"CN_CPI_INDEX с transform=yoy_pct: YoY е константен през прозореца → "
        f"score трябва да е near-неутрален (40-60), а не {latest['score']} "
        f"— ако score-ва суровото ниво (винаги нов връх), score ще е ~100."
    )
    # O3 G7-2: percentile-ът също е върху ТРАНСФОРМИРАНАТА величина (YoY), не суровия
    # индекс. Суровото ниво (монотонен растеж) би дало percentile ~100 (винаги нов
    # максимум); YoY-темпът е константен → percentile НЕ е екстремен.
    pct = latest["percentile"]
    assert pct is None or pct < 90, (
        f"CN_CPI_INDEX percentile={pct} — ако беше върху суровото ниво щеше да е ~100."
    )
    assert "percentile_window" in latest


# ── (в) регресионно: ключ без запис в SERIES_META → fallback без exception ──

def test_unknown_series_key_falls_back_without_exception():
    """Серия, която не е в нито един от петте модула (не е в SERIES_META) —
    build_series_data не трябва да хвърля, а да падне към досегашното
    поведение (score_series без invert/transform, level по подразбиране)."""
    idx = pd.date_range(end="2026-06-01", periods=48, freq="MS")
    snapshot = {"CN_TOTALLY_UNKNOWN_SERIES": pd.Series(range(48), index=idx, dtype=float)}

    assert "CN_TOTALLY_UNKNOWN_SERIES" not in SERIES_META

    out = build_series_data(snapshot, today=pd.Timestamp("2026-06-01").date(), years=7)

    assert "CN_TOTALLY_UNKNOWN_SERIES" in out["series"]
    latest = out["series"]["CN_TOTALLY_UNKNOWN_SERIES"]["latest"]
    assert latest["score"] is not None


# ── SERIES_META съдържание — sanity check срещу модулните дефиниции ─────────

def test_series_meta_contains_known_invert_and_transform_entries():
    """SERIES_META трябва да е агрегиран от петте модула и да отразява
    ТОЧНО техните invert/transform стойности (не hardcode-нати копия)."""
    assert SERIES_META["CN_YOUTH_UNEMPLOYMENT"]["invert"] is True
    assert SERIES_META["CN_YOUTH_UNEMPLOYMENT"]["transform"] == "level"
    assert SERIES_META["CN_CPI_INDEX"]["invert"] is False
    assert SERIES_META["CN_CPI_INDEX"]["transform"] == "yoy_pct"
    assert SERIES_META["CN_UNEMPLOYMENT"]["invert"] is True
