"""
tests/test_deep_briefing.py
===========================
Offline тестове за China deep briefing (Фаза 2):
  - catalog helper-и series_by_tag / series_by_peer_group (отключват non_consensus)
  - composite/regime математика — config.MODULE_WEIGHTS (НЕ landing-овото копие)
  - generate_deep_briefing рендира всички China-native секции
  - честни „предстои" placeholder-и (без фабрикувани US-копирани секции)
  - WoW delta: първи run vs run с предишен state
  - empty snapshot не крашва

Без мрежа — синтетичен snapshot покрива целия каталог.
"""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd

from config import MODULE_WEIGHTS, MACRO_REGIMES
from catalog.series import SERIES_CATALOG, series_by_tag, series_by_peer_group, ALLOWED_TAGS
from export.deep_briefing import (
    generate_deep_briefing,
    _overall_composite,
    _overall_regime,
)


def _monthly(values, end="2026-05-01"):
    idx = pd.date_range(end=end, periods=len(values), freq="MS")
    return pd.Series(values, index=idx)


def _synthetic_snapshot():
    """Покрива целия каталог; тренд + няколко spike-а за аномалии."""
    snap = {}
    for i, k in enumerate(SERIES_CATALOG.keys()):
        if i % 9 == 0:
            vals = [2.0 + 0.03 * np.sin(j * 0.3) for j in range(57)] + [9.0, 9.4, 9.9]
        else:
            vals = list(np.linspace(2.0 + (i % 4) * 0.2, 4.5 + (i % 3) * 0.3, 60))
        snap[k] = _monthly(vals)
    return snap


# ─── catalog helper-и (отключват non_consensus import) ───────────

def test_catalog_helpers_exist_and_work():
    # series_by_tag покрива всеки allowed tag
    for tag in ALLOWED_TAGS:
        rows = series_by_tag(tag)
        for r in rows:
            assert "_key" in r
            assert tag in r.get("tags", [])
    # има поне няколко non_consensus tagged серии (захранват highlights)
    assert len(series_by_tag("non_consensus")) >= 3
    # series_by_peer_group връща членовете на група
    cpi = series_by_peer_group("cpi")
    assert all(e.get("peer_group") == "cpi" for e in cpi)
    assert {e["_key"] for e in cpi}  # непразно


# ─── composite/regime — config тегла (authoritative) ────────────

def test_overall_composite_uses_config_weights():
    """Headline-ът трябва да е config.MODULE_WEIGHTS (= run.py --modules /
    export_api / manifest), НЕ остарялото локално копие на landing-а."""
    # Реалните per-lens скорове от run.py --modules след composite re-base (verified 2026-06-02)
    results = [
        {"module": "growth", "composite": 14.5, "regime": "РЕЦЕСИЯ"},
        {"module": "inflation", "composite": 35.1, "regime": "ДЕФЛАЦИОНЕН РИСК"},
        {"module": "labor", "composite": 12.3, "regime": "КРИЗА НА ТРУДА"},
        {"module": "credit", "composite": 47.9, "regime": "НЕУТРАЛНА ПОЛИТИКА"},
        {"module": "property", "composite": 18.2, "regime": "ИМОТНА КРИЗА"},
    ]
    overall = _overall_composite(results)
    assert overall == 26.5   # config weights, re-base на свежи 2026 данни (вкл. свеж CPI/PPI)

    label_bg, key, color = _overall_regime(overall)
    assert label_bg == "РЕЦЕСИОНЕН"
    assert key == "recessionary"
    assert color.startswith("#")


def test_module_weights_are_config_not_landing():
    """Регресионен guard: deep ползва config теглата (credit 0.25, labor 0.10)."""
    assert MODULE_WEIGHTS["credit"] == 0.25
    assert MODULE_WEIGHTS["labor"] == 0.10
    assert MODULE_WEIGHTS["property"] == 0.20


def test_composite_series_rebased_to_fresh():
    """Re-base guard (2026-06-02): композитът стъпва на СВЕЖИ месечни/тримесечни
    серии, не на застоялите годишни WB. Пази критичните hardcoded COMPOSITE_SERIES
    срещу тих revert. Виж HANDOFF-china-rebase.md."""
    import modules.growth as g, modules.inflation as i
    import modules.credit as c, modules.property as p
    # growth: свежи retail + PMI; годишният GDP вече е само контекст
    assert "CN_RETAIL_YOY" in g.COMPOSITE_SERIES
    assert "CN_PMI_MFG_NBS" in g.COMPOSITE_SERIES
    assert "CN_GDP_GROWTH" not in g.COMPOSITE_SERIES
    # credit: M2 YoY РАСТЕЖ + BIS кредит/БВП; не подвеждащото M2/БВП ниво
    assert "CN_M2_YOY" in c.COMPOSITE_SERIES
    assert "CN_BIS_CREDIT_GDP" in c.COMPOSITE_SERIES
    assert "CN_M2_GDP" not in c.COMPOSITE_SERIES
    # property: BIS имотни цени + FAI
    assert "CN_BIS_PROPERTY_YOY" in p.COMPOSITE_SERIES
    assert "CN_FAI_MOM_YOY" in p.COMPOSITE_SERIES
    # inflation: свеж akshare CPI + PPI (не мъртвите IMF CN_CPI_INDEX/CN_PPI_INDEX) + тримесечен дефлатор
    assert "CN_CPI_YOY_AK" in i.COMPOSITE_SERIES
    assert "CN_CPI_INDEX" not in i.COMPOSITE_SERIES
    assert "CN_PPI_YOY" in i.COMPOSITE_SERIES
    assert "CN_PPI_INDEX" not in i.COMPOSITE_SERIES
    assert "CN_GDP_DEFLATOR_Q" in i.COMPOSITE_SERIES
    # consistency: всеки модул има равен брой серии и тегла
    for mod in (g, i, c, p):
        assert len(mod.COMPOSITE_SERIES) == len(mod.COMPOSITE_WEIGHTS)


def test_deflator_absolute_anchor():
    """Q1 хибрид: тримесечният дефлатор се score-ва с absolute anchor, не percentile."""
    from modules.inflation import _deflator_anchor
    assert _deflator_anchor(-5) == 0.0      # дълбока дефлация
    assert _deflator_anchor(-3) == 0.0
    assert _deflator_anchor(0) == 35.0      # ценова стабилност (праг)
    assert _deflator_anchor(2) == 60.0      # рефлация
    assert _deflator_anchor(4) == 75.0
    assert _deflator_anchor(-0.06) == 34.3  # текущ 2026-Q1 (още дефлация, на ръба)


# ─── Phase 3 — China-native falsifiers ──────────────────────────

def test_china_falsifiers_recessionary_live_status():
    """Phase 3: China falsifiers оценяват ЖИВ статус срещу snapshot (не US Sahm/ICSA)."""
    import pandas as pd
    from analysis.guardrails import (
        compute_china_falsifiers, get_china_falsifiers, CHINA_FALSIFIERS_BY_REGIME,
    )
    qidx = pd.period_range("2023Q2", "2026Q1", freq="Q").to_timestamp(how="end")
    snap = {
        "CN_GDP_DEFLATOR_Q": pd.Series([-0.8] * 11 + [-0.06], index=qidx),  # 12 отриц., −0.06 близо
        "CN_BIS_PROPERTY_YOY": pd.Series([-7.5], index=[pd.Timestamp("2025-03-31")]),
        "CN_FAI_MOM_YOY": pd.Series([-12.0], index=[pd.Timestamp("2026-04-01")]),
        "CN_M2_YOY": pd.Series([8.6], index=[pd.Timestamp("2026-04-01")]),
    }
    fals = compute_china_falsifiers(snap, "recessionary", 26.5)
    assert len(fals) == 4
    by_key = {f.key: f for f in fals}
    assert by_key["deflator_positive_2q"].status == "approaching"   # −0.06 най-плитък → близо
    assert by_key["property_stabilizes"].status == "far"            # −7.5/−12 дълбоко надолу
    assert by_key["credit_transmission"].status == "far"            # 8.6 < 10
    assert by_key["composite_exits_band"].status == "far"           # 26.5 < 35
    # China-native, не US
    assert get_china_falsifiers("recessionary")
    assert "stagflation_confirmed" not in CHINA_FALSIFIERS_BY_REGIME
    assert set(CHINA_FALSIFIERS_BY_REGIME) == {
        "recessionary", "deteriorating", "mixed", "healthy", "expansionary"}


def test_china_falsifier_deflator_triggers():
    """Дефлатор ≥ 0 за 2 поредни тримесечия → falsifier-ът се задейства."""
    import pandas as pd
    from analysis.guardrails import compute_china_falsifiers
    qidx = pd.period_range("2025Q4", "2026Q1", freq="Q").to_timestamp(how="end")
    snap = {"CN_GDP_DEFLATOR_Q": pd.Series([0.3, 0.5], index=qidx)}
    by_key = {f.key: f for f in compute_china_falsifiers(snap, "recessionary", 26.5)}
    assert by_key["deflator_positive_2q"].status == "triggered"


def test_overall_regime_thresholds():
    assert _overall_regime(85)[1] == "expansionary"
    assert _overall_regime(70)[1] == "healthy"
    assert _overall_regime(55)[1] == "mixed"
    assert _overall_regime(40)[1] == "deteriorating"
    assert _overall_regime(20)[1] == "recessionary"


# ─── рендериране ─────────────────────────────────────────────────

def test_deep_renders_all_native_sections(tmp_path):
    snap = _synthetic_snapshot()
    out = tmp_path / "deep.html"
    generate_deep_briefing(snap, str(out), today=date(2026, 5, 30),
                           state_dir=str(tmp_path / "state"))
    html = out.read_text(encoding="utf-8")

    # China-native секции
    for section in [
        "Регимна диагноза", "Седмична промяна", "Cross-Lens Divergence",
        "Non-Consensus Highlights", "Top Anomalies", "Исторически аналози",
        "качеството на данните",
    ]:
        assert section in html, f"липсва секция: {section}"

    # 3 cross-lens двойки, 5 lens блока
    assert html.count('class="pair-card"') == 3
    assert html.count("data-lens=") == 5

    # Phase 4 — analogs имплементиран (НЕ „предстои"); честна рамка
    assert ">Предстои<" not in html and 'class="soon-card"' not in html
    assert html.count('class="analog-card"') >= 1
    assert "Какво последва аналозите" in html
    assert "римува се с" in html              # honest framing, не „днес = X"
    # journal е research-desk opt-in → НЕ се рендира в public (без journal_entries)
    assert "Свързани бележки" not in html
    # Phase 3 — China falsifiers секция с жив статус (не US Sahm/ICSA/T10Y2Y)
    assert "Какво би обърнало" in html
    assert html.count('class="fals-card"') >= 1
    for us_signal in ("Sahm", "ICSA", "T10Y2Y"):
        assert us_signal not in html

    # backlink към краткия преглед (М25: краткият landing се мести на
    # quick.html; index.html става входната страница)
    assert 'href="quick.html"' in html

    # дарк China-family тема + self-contained
    assert "#0d1117" in html
    assert "<script" not in html.lower()


def test_deep_has_no_us_executive_framing(tmp_path):
    """Anti-illusion: deep НЕ показва US executive рамка / US threshold flags
    като активни секции."""
    snap = _synthetic_snapshot()
    out = tmp_path / "deep.html"
    generate_deep_briefing(snap, str(out), today=date(2026, 5, 30),
                           state_dir=str(tmp_path / "state"))
    html = out.read_text(encoding="utf-8")
    # няма US executive заглавие
    assert "Executive Summary" not in html
    # няма активен US threshold-flags banner
    assert "Threshold алерти" not in html
    assert "flags-banner" not in html
    # няма US регимни ключове като активен режим
    assert "stagflation" not in html.lower()


def test_deep_wow_first_run_then_delta(tmp_path):
    snap = _synthetic_snapshot()
    state_dir = str(tmp_path / "state")

    # Run 1 — няма предишен state
    out1 = tmp_path / "deep1.html"
    generate_deep_briefing(snap, str(out1), today=date(2026, 5, 18), state_dir=state_dir)
    html1 = out1.read_text(encoding="utf-8")
    assert "Няма референтен snapshot" in html1

    # Run 2 — 7 дни по-късно → намира run1 (≥5 дни) като референция
    out2 = tmp_path / "deep2.html"
    generate_deep_briefing(snap, str(out2), today=date(2026, 5, 25), state_dir=state_dir)
    html2 = out2.read_text(encoding="utf-8")
    assert "спрямо 2026-05-18" in html2
    assert "Няма референтен snapshot" not in html2


def test_deep_handles_empty_snapshot(tmp_path):
    out = tmp_path / "empty.html"
    generate_deep_briefing({}, str(out), today=date(2026, 5, 30), state_dir=None)
    assert out.exists()
    html = out.read_text(encoding="utf-8")
    # graceful — секциите се рендират, без crash
    assert "Регимна диагноза" in html
    assert "Cross-Lens Divergence" in html
    # дори при празен snapshot — честен analogs fallback (не crash, не фабрикувана секция)
    assert "Исторически аналози" in html


def test_deep_renders_journal_when_entries_passed(tmp_path):
    """Research-desk opt-in: journal_entries → секция „Свързани бележки" с линкове.
    Без entries секцията липсва (виж test_deep_renders_all_native_sections)."""
    from datetime import date as _date
    from scripts._utils import JournalEntry
    entries = [
        JournalEntry(path=Path("journal/inflation/x.md"), date=_date(2026, 6, 1),
                     topic="inflation", title="PPI рефлация изпреварва CPI",
                     tags=["ppi", "deflation"], status="finding"),
        JournalEntry(path=Path("journal/analogs/y.md"), date=_date(2026, 5, 28),
                     topic="analogs", title="Режимът няма близък аналог",
                     tags=["cosine"], status="hypothesis"),
    ]
    out = tmp_path / "deep_j.html"
    generate_deep_briefing(_synthetic_snapshot(), str(out), today=date(2026, 5, 30),
                           state_dir=str(tmp_path / "state"), journal_entries=entries)
    html = out.read_text(encoding="utf-8")
    assert "Свързани бележки" in html
    assert "PPI рефлация изпреварва CPI" in html
    assert "Режимът няма близък аналог" in html
    assert 'class="journal-item"' in html
    assert "../journal/inflation/x.md" in html  # relative link спрямо output/
