"""
tests/test_journal.py
=====================
Offline тестове за China research journal framework-а (Phase 4 companion).

  - VALID_TOPICS = China таксономия (5-те лещи + analogs/regime/methodology)
  - save → load roundtrip (temp dir, не пипа реалния journal/)
  - валидация на topic/status
  - build_journal_index групира по topic + empty-state
  - TOPIC_LABELS_BG покрива всички VALID_TOPICS

Без мрежа.
"""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from scripts._utils import (
    VALID_TOPICS, VALID_STATUSES, save_journal_entry, load_journal_entries,
)
from scripts.build_journal_index import build_index, TOPIC_LABELS_BG


def test_topics_are_china_taxonomy():
    # 5-те China лещи присъстват (вкл. property — липсва в US/EU)
    for lens in ("growth", "inflation", "labor", "credit", "property"):
        assert lens in VALID_TOPICS
    for analytical in ("analogs", "regime", "methodology"):
        assert analytical in VALID_TOPICS
    # всеки topic има BG label в индексатора
    for t in VALID_TOPICS:
        assert t in TOPIC_LABELS_BG


def test_save_load_roundtrip(tmp_path):
    p = save_journal_entry(
        topic="property", title="Имотен сигнал от FAI", body="## Извод\nтест тяло",
        tags=["fai", "bis"], status="finding", journal_dir=tmp_path,
    )
    assert p.exists() and p.parent.name == "property"
    entries = load_journal_entries(journal_dir=tmp_path)
    assert len(entries) == 1
    e = entries[0]
    assert e.topic == "property" and e.status == "finding"
    assert e.title == "Имотен сигнал от FAI"
    assert e.tags == ["fai", "bis"]
    assert "тест тяло" in e.body


def test_filters(tmp_path):
    save_journal_entry(topic="inflation", title="A", body="x", status="finding",
                       tags=["ppi"], journal_dir=tmp_path)
    save_journal_entry(topic="credit", title="B", body="y", status="open_question",
                       tags=["m2"], journal_dir=tmp_path)
    assert len(load_journal_entries(topic="inflation", journal_dir=tmp_path)) == 1
    assert len(load_journal_entries(status="open_question", journal_dir=tmp_path)) == 1
    assert len(load_journal_entries(tags_any=["m2"], journal_dir=tmp_path)) == 1
    assert len(load_journal_entries(journal_dir=tmp_path)) == 2


def test_rejects_invalid_topic_and_status(tmp_path):
    with pytest.raises(ValueError):
        save_journal_entry(topic="liquidity", title="t", body="b", journal_dir=tmp_path)
    with pytest.raises(ValueError):
        save_journal_entry(topic="credit", title="t", body="b",
                           status="nonsense", journal_dir=tmp_path)


def test_build_index_empty_and_grouped(tmp_path):
    # empty
    idx0 = build_index(journal_dir=tmp_path)
    assert "Няма записи" in idx0
    # с два записа в различни теми
    save_journal_entry(topic="property", title="Имоти запис", body="b",
                       status="finding", journal_dir=tmp_path)
    save_journal_entry(topic="analogs", title="Аналог запис", body="b",
                       status="hypothesis", journal_dir=tmp_path)
    idx = build_index(journal_dir=tmp_path)
    assert "## Имоти" in idx and "## Исторически аналози" in idx
    assert "2 записа" in idx
    assert "Имоти запис" in idx and "Аналог запис" in idx
