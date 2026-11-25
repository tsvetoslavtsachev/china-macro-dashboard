"""
sources/fred_csv.py
===================
Генеричен FRED adapter през публичния CSV (без API ключ):
    https://fred.stlouisfed.org/graph/fredgraph.csv?id=<ID>

ПРОЛЕТР4 (подобрение на състава): пренасочва CNY/USD (DEXCHUS), BIS кредит/БВП
(QCNPAM770A), BIS имотни цени (QCNN628BIS), реален ефективен курс (RBCNBIS) и
3М междубанков процент (IR3TIB01CNM156N) към един източник със свежи данни.

Catalog convention:
  source = "fred_csv"
  id     = "<FRED_ID>[@qend][@yoy]"
    @qend  → тримесечните FRED дати са начало на тримесечието (2026-01-01);
             преместваме ги в края му (2026-03-31) — същата конвенция като
             dbnomics/nbs_manual (стария BIS), та старите и новите стойности да
             се сравняват по една и съща дата.
    @yoy   → процентна промяна спрямо СЪЩАТА дата преди 1 година (по календар,
             не по позиция — дупка в реда не мести сравнението).

FRED маркира липсващите наблюдения с "." (или празно) — те се пропускат.
Кеш: data/cache_fred_csv.json (gitignored по конвенцията data/cache_*.json).
"""
from __future__ import annotations

import io
import logging
from pathlib import Path
from typing import Optional

import pandas as pd
import requests

from sources._base import BaseAdapter

logger = logging.getLogger(__name__)

FRED_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"
USER_AGENT = "macro-dashboard-research/1.0"


def split_id(source_id: str) -> tuple[str, set[str]]:
    """'QCNN628BIS@qend@yoy' → ('QCNN628BIS', {'qend', 'yoy'})."""
    parts = source_id.split("@")
    return parts[0].strip(), {p.strip().lower() for p in parts[1:] if p.strip()}


def parse_fred_csv(text: str) -> pd.Series:
    """FRED CSV текст → float Series (DatetimeIndex, възходящо). '.' и празно се пропускат."""
    df = pd.read_csv(io.StringIO(text))
    if df.shape[1] < 2 or df.empty:
        return pd.Series(dtype=float)
    dates = pd.to_datetime(df.iloc[:, 0], errors="coerce")
    values = pd.to_numeric(df.iloc[:, 1], errors="coerce")  # '.' → NaN
    s = pd.Series(values.values, index=dates, dtype=float)
    s = s[s.index.notna()].dropna().sort_index()
    s = s[~s.index.duplicated(keep="last")]
    return s


def quarter_start_to_end(s: pd.Series) -> pd.Series:
    out = s.copy()
    out.index = pd.DatetimeIndex(
        [pd.Period(ts, freq="Q").end_time.normalize() for ts in s.index]
    )
    return out


def yoy_pct(s: pd.Series) -> pd.Series:
    """% промяна спрямо същата дата преди 12 месеца (точно съвпадение на датата)."""
    prev = s.copy()
    prev.index = prev.index + pd.DateOffset(years=1)
    # тримесечен край на месец (31.03 → 31.03 / 30.06) се нормализира през месечен край
    base = prev.reindex(s.index)
    out = (s / base - 1.0) * 100.0
    return out.dropna()


class FredCsvAdapter(BaseAdapter):
    """Adapter за FRED серии през публичния fredgraph.csv."""

    SOURCE_NAME = "fred_csv"

    def __init__(
        self,
        cache_path: str | Path = "data/cache_fred_csv.json",
        base_dir: Optional[Path] = None,
        retry_backoff: Optional[list[int]] = None,
    ):
        super().__init__(cache_path=cache_path, base_dir=base_dir,
                         retry_backoff=retry_backoff)

    def _download(self, fred_id: str) -> str:
        try:
            resp = requests.get(
                FRED_CSV_URL, params={"id": fred_id},
                headers={"User-Agent": USER_AGENT}, timeout=30,
            )
            resp.raise_for_status()
        except requests.exceptions.HTTPError as e:
            raise RuntimeError(f"HTTP {resp.status_code}: {e}") from e
        except requests.exceptions.Timeout as e:
            raise RuntimeError(f"timed out: {e}") from e
        except requests.exceptions.ConnectionError as e:
            raise RuntimeError(f"Connection reset: {e}") from e
        return resp.text

    def _fetch_remote(self, series_key: str, source_id: str) -> pd.Series:
        fred_id, flags = split_id(source_id)
        if not fred_id:
            raise RuntimeError(f"{series_key}: невалиден fred_csv id '{source_id}'")
        s = parse_fred_csv(self._download(fred_id))
        if s.empty:
            logger.warning(f"{series_key} ({source_id}): празен FRED отговор")
            return s
        if "qend" in flags:
            s = quarter_start_to_end(s)
        if "yoy" in flags:
            s = yoy_pct(s)
        logger.info(f"{series_key} ({source_id}): {len(s)} obs, latest={s.index[-1].date()}")
        return s
