# -*- coding: utf-8 -*-
"""ИЛЮ3 Е3 (23.11.2026): паднала серия в таблото е шумна.

От 14.11 до 22.11.2026 таблото губеше до 11 серии на ход, а ходовете бяха зелени: „fetch
failed“ беше ред в лога. Сега всяка серия, паднала при теглене (изключение или празен
отговор), се дописва в output/.fetch_failed и работните потоци червенеят в края, след
комита. Серия, която стои при източника (стара дата, без изключение), не е провал."""
from pathlib import Path

import pandas as pd
import pytest

from sources._base import BaseAdapter

REPO = Path(__file__).resolve().parents[1]
SPECS = [{"key": k, "source_id": k, "release_schedule": "monthly"} for k in ("ok", "old", "boom", "empty")]


class Fake(BaseAdapter):
    SOURCE_NAME = "fake"

    def _fetch_remote(self, series_key, source_id):
        if series_key == "boom":
            raise AttributeError("macro_china_money_supply 已在 1.20.42 更名")
        if series_key == "empty":
            return pd.Series(dtype=float)
        last = "2025-08-01" if series_key == "old" else "2026-10-01"   # old: стои при източника
        return pd.Series([1.0, 2.0], index=pd.to_datetime(["2025-07-01", last]))


@pytest.fixture
def adapter(tmp_path):
    return Fake(cache_path="data/cache_fake.json", base_dir=tmp_path, retry_backoff=[])


def test_mutation_one_failed_series_is_written_to_the_marker(adapter, tmp_path):
    adapter.fetch_many(SPECS, force=True)
    marker = tmp_path / "output" / ".fetch_failed"
    lines = marker.read_text(encoding="utf-8").splitlines()
    assert [x.split()[1] for x in lines] == ["boom", "empty"]
    assert "AttributeError" in lines[0] and "празен отговор" in lines[1]
    assert sorted(adapter.last_fetch_failures()) == ["boom", "empty"]


def test_series_standing_at_the_source_is_not_a_failure(adapter, tmp_path):
    adapter.fetch_many([s for s in SPECS if s["key"] in ("ok", "old")], force=True)
    assert not (tmp_path / "output" / ".fetch_failed").exists()
    assert adapter.last_fetch_failures() == []


@pytest.mark.parametrize("wf", ["export-api.yml", "weekly_update.yml"])
def test_both_workflows_turn_red_on_the_marker_after_the_commit(wf):
    text = (REPO / ".github" / "workflows" / wf).read_text(encoding="utf-8")
    assert "output/.fetch_failed" in text and "exit 1" in text
    assert text.index("output/.fetch_failed") > text.index("git commit")


def test_marker_is_gitignored():
    assert "output/.fetch_failed" in (REPO / ".gitignore").read_text(encoding="utf-8").splitlines()
