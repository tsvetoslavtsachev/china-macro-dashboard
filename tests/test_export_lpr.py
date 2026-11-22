"""LPR експорт: празен/подменен отговор хвърля, здрав дава файл."""
from datetime import date

import pandas as pd
import pytest

from export_api import build_lpr, write_lpr

TODAY = date(2026, 11, 22)


def _good():
    return pd.DataFrame({
        "TRADE_DATE": ["2025-01-20", "2026-10-20", "2026-11-20"],
        "LPR1Y": [3.1, 3.0, 3.0],
        "LPR5Y": [3.6, 3.5, 3.5],
    })


def test_good_writes_file(tmp_path):
    p = tmp_path / "lpr.json"
    d = write_lpr(_good(), TODAY, p)
    assert p.exists()
    assert d["series"]["lpr_1y"][-1] == ["2026-11-20", 3.0]
    assert d["series"]["lpr_5y"][-1] == ["2026-11-20", 3.5]
    assert set(d) == {"generated_at", "source", "series"}


@pytest.mark.parametrize("bad", [
    pd.DataFrame(), pd.DataFrame(columns=["TRADE_DATE", "LPR1Y", "LPR5Y"]),
    "<html>blocked</html>", None, pd.DataFrame({"x": [1]}),
])
def test_bad_raises_and_no_file(tmp_path, bad):
    p = tmp_path / "lpr.json"
    with pytest.raises(ValueError):
        write_lpr(bad, TODAY, p)
    assert not p.exists()


def test_publish_failure_keeps_old_file_and_sets_marker(tmp_path):
    from export_api import publish_lpr
    p, m = tmp_path / "lpr.json", tmp_path / ".lpr_failed"
    p.write_text("OLD", encoding="utf-8")
    ok = publish_lpr(lambda: pd.DataFrame(), TODAY, p, m)
    assert ok is False and m.exists() and p.read_text(encoding="utf-8") == "OLD"


def test_publish_success_writes_and_clears_marker(tmp_path):
    from export_api import publish_lpr
    p, m = tmp_path / "lpr.json", tmp_path / ".lpr_failed"
    m.write_text("stale", encoding="utf-8")
    assert publish_lpr(_good, TODAY, p, m) is True
    assert p.exists() and not m.exists()


def test_main_other_files_written_when_lpr_fails(tmp_path, monkeypatch):
    """Мутация: LPR празен, а останалите файлове на main пак се записват."""
    import export_api as ea, types
    monkeypatch.setattr(ea, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(ea, "_build_adapters", lambda: {})
    monkeypatch.setattr(ea, "_auto_refresh_stale", lambda *a, **k: None)
    monkeypatch.setattr(ea, "_build_snapshot", lambda *a, **k: {"x": 1})
    monkeypatch.setattr(ea, "build_macro_state", lambda s, t: {"executive_summary": {"composite_score": 0, "regime_key": "k"}, "lenses": [], "top_anomalies": []})
    monkeypatch.setattr(ea, "build_series_data", lambda s, t, years=7: {"series_count": 0})
    import sys
    monkeypatch.setitem(sys.modules, "akshare", types.SimpleNamespace(macro_china_lpr=lambda: pd.DataFrame()))
    rc = ea.main(types.SimpleNamespace(refresh=False, years=10))
    assert rc == 0
    assert (tmp_path / "macro_state.json").exists() and (tmp_path / "series_data.json").exists()
    assert not (tmp_path / "lpr.json").exists() and (tmp_path / ".lpr_failed").exists()
