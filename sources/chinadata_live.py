"""
sources/chinadata_live.py
=========================
Adapter за chinadata.live (ПРОЛЕТР4, 25.11.2026).

chinadata.live е независим проект без назован оператор, който препубликува официални
китайски редове (НБС, митница, НБК). Без ключ; лимит 1000 заявки на IP на ден. Тук е
ВТОРИ източник и кръстосана проверка на akshare, не единствена опора там, където akshare
е жив.

Формат (проверен на живо 25.11.2026):
  GET https://chinadata.live/api/v2/data/{id}
  -> {"success": true, "data": {"id", "title", "unit", "source", ..., "data": [ {...} ],
                                "meta": {"totalPoints", "dateRange", "lastUpdated"}}}
  data[] е списък от {"date": "YYYY-MM", "value": "<низ>"}; търговията има няколко полета
  ("export", "import", "ytd_export" ...) вместо "value". Празен низ = няма стойност.
  ?format=csv връща същото като CSV.

source_id в каталога:
  "china-youth-unemployment"            -> поле "value"
  "china-trade-monthly#export"          -> поле "export" (нива, USD млн.)
  "china-property-sales-area@cum_yoy"   -> yoy от кумулативни YTD нива: стойността за месеца M
                                            делено на стойността за същия месец година по-рано;
                                            само ако ИМА и двете (иначе месецът отпада).
"""
from __future__ import annotations

import csv
import io
import logging
import re
import time
from pathlib import Path
from typing import Any, Optional

import pandas as pd
import requests

from sources._base import BaseAdapter

logger = logging.getLogger(__name__)

BASE_URL = "https://chinadata.live/api/v2"
# Общ клиент без лични данни; без име на потребителя или проекта.
USER_AGENT = "macro-dashboard-client/1.0 (weekly research data fetch)"
REQUEST_TIMEOUT = 30
REQUEST_DELAY = 0.4          # учтива пауза между заявките (лимит 1000/IP/ден)


class ChinaDataError(RuntimeError):
    """Неочакван вид на отговора от chinadata.live."""


# ─── Чист разбор (без мрежа; покрит от тестове) ───────────────────────────────

def _records_from_json(payload: Any) -> list[dict]:
    """Вади списъка data[] от плика {"success":..,"data":{..,"data":[..]}}."""
    if not isinstance(payload, dict):
        raise ChinaDataError(f"отговорът не е JSON обект: {type(payload).__name__}")
    if payload.get("success") is False:
        raise ChinaDataError(f"success=false: {str(payload)[:120]}")
    body = payload.get("data")
    if isinstance(body, dict):
        body = body.get("data")
    if not isinstance(body, list):
        raise ChinaDataError("липсва списъкът data[] в отговора")
    return body


def _records_from_csv(text: str) -> list[dict]:
    return list(csv.DictReader(io.StringIO(text)))


_QUARTER_RE = re.compile(r"^\d{4}-?Q[1-4]$")


def parse_records(records: list[dict], field: str = "value") -> pd.Series:
    """[{date:'YYYY-MM', <field>:'низ'}] -> float Series с индекс първо число на месеца.

    Празни и нечислови стойности отпадат; дублирана дата — последната печели."""
    dates, vals = [], []
    for r in records:
        raw = str(r.get("date", "")).strip()
        if _QUARTER_RE.match(raw):
            # ПРОЛЕТР4 (КТ-1): тримесечни набори ('2013-Q1') -> краят на тримесечието, както
            # CN_GDP_GROWTH_Q и @qend при FRED; иначе '2013-Q1-01' става NaT и редът изпада.
            d = pd.Period(raw.replace("-", ""), freq="Q").end_time.normalize()
        else:
            d = pd.to_datetime(raw + "-01" if len(raw) == 7 else raw, errors="coerce")
        v = pd.to_numeric(str(r.get(field, "")).strip().replace(",", ""), errors="coerce")
        if pd.isna(d) or pd.isna(v):
            continue
        dates.append(d)
        vals.append(float(v))
    if not dates:
        return pd.Series(dtype=float)
    s = pd.Series(vals, index=pd.DatetimeIndex(dates), dtype=float)
    return s.groupby(level=0).last().sort_index()


def cumulative_yoy(cum: pd.Series) -> pd.Series:
    """YoY % от кумулативни YTD нива: само там, където има същия месец година по-рано
    (не се интерполира; не се смята срещу различен месец). Основата НЕ е ревизирана, затова
    може да се различава от официалния сравним темп на НБС."""
    prev = cum.copy()
    prev.index = prev.index + pd.DateOffset(years=1)
    both = pd.concat([cum.rename("cur"), prev.rename("base")], axis=1, sort=True).dropna()
    both = both[both["base"] != 0]
    return ((both["cur"] / both["base"] - 1.0) * 100.0).sort_index()


def parse_source_id(source_id: str) -> tuple[str, str, Optional[str]]:
    """'dataset#field' / 'dataset@mode' -> (dataset, field, mode)."""
    mode = None
    field = "value"
    ds = source_id
    if "@" in ds:
        ds, mode = ds.split("@", 1)
    if "#" in ds:
        ds, field = ds.split("#", 1)
    return ds, field, mode


# ─── Адаптерът ────────────────────────────────────────────────────────────────

class ChinaDataLiveAdapter(BaseAdapter):
    """Adapter за chinadata.live (месечни официални редове за Китай)."""

    SOURCE_NAME = "chinadata_live"

    def __init__(
        self,
        cache_path: str | Path = "data/cache_chinadata_live.json",
        base_dir: Optional[Path] = None,
        retry_backoff: Optional[list[int]] = None,
        session: Optional[requests.Session] = None,
        request_delay: float = REQUEST_DELAY,
    ):
        super().__init__(cache_path=cache_path, base_dir=base_dir, retry_backoff=retry_backoff)
        self._session = session or requests.Session()
        self._session.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})
        self._request_delay = request_delay

    # ─── мрежа ───────────────────────────────────────────────

    def _get(self, dataset: str, fmt: str = "json") -> Any:
        url = f"{BASE_URL}/data/{dataset}" + ("?format=csv" if fmt == "csv" else "")
        resp = self._session.get(url, timeout=REQUEST_TIMEOUT)
        if self._request_delay:
            time.sleep(self._request_delay)
        resp.raise_for_status()
        return resp.text if fmt == "csv" else resp.json()

    def fetch_records(self, dataset: str) -> list[dict]:
        """Суровите редове на набора (с един JSON опит; retry прави _fetch_with_retry)."""
        return _records_from_json(self._get(dataset, "json"))

    # ─── BaseAdapter hook ────────────────────────────────────

    def _fetch_remote(self, series_key: str, source_id: str) -> pd.Series:
        dataset, field, mode = parse_source_id(source_id)
        s = parse_records(self.fetch_records(dataset), field)
        if mode == "cum_yoy":
            s = cumulative_yoy(s)
        elif mode:
            raise ValueError(f"непознат режим '{mode}' в {source_id}")
        return s

    # ─── референтни редове за кръстосаните проверки ──────────

    def fetch_reference(self, source_id: str, force: bool = False,
                        release_schedule: str = "monthly") -> pd.Series:
        """Като fetch(), но под ключ 'ref:<source_id>' — референтен ред, който не е серия
        от каталога (не влиза в snapshot-а). Кешира се със същия TTL."""
        key = f"ref:{source_id}"
        s = self.fetch(key, source_id, release_schedule, force=force)
        self.save_cache()
        return s

    def fetch_all_china_series(self, catalog: dict, force: bool = False) -> dict[str, pd.Series]:
        specs = [
            {"key": k, "source_id": e["id"], "release_schedule": e.get("release_schedule", "monthly")}
            for k, e in catalog.items() if e.get("source") == self.SOURCE_NAME
        ]
        logger.info(f"ChinaDataLiveAdapter: fetching {len(specs)} series")
        return self.fetch_many(specs, force=force)
