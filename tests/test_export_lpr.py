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
