"""
sources/dbnomics.py
===================
Генеричен DBnomics adapter — provider/dataset/series (за разлика от
``imf_ifs.py``, който е hardcoded на IMF/IFS).

DBnomics (api.db.nomics.world/v22) агрегира публична официална статистика
(IMF, OECD, BIS, национални статистики). Безплатен, commercially-usable —
лицензът зависи от underlying provider (IMF/BIS/нац. статистики са свободни).
Public v22 API е отворен (без ключ). Опционален ``config.DBNOMICS_API_KEY``
е резерв за по-висок rate-limit под натоварване.

Catalog convention:
  source = "dbnomics"
  id     = "PROVIDER/DATASET/SERIES_CODE"
           напр. "BIS/WS_TC/Q.CN.P.A.M.770.A"  (China credit/GDP, тримесечно)
                 "BIS/WS_SPP/Q.CN.N.771"        (China property prices YoY)
                 "NBS/M_A0703/A07030B"          (China retail sales growth)

Период-парсинг покрива трите DBnomics формата:
  "2025-07"   → месечно   (month start)
  "2024-Q4"   → тримесечно (quarter end — съгласувано с nbs_manual)
  "2024"      → годишно   (year end)
"""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Optional

import pandas as pd
import requests

from sources._base import BaseAdapter
from config import DBNOMICS_API_BASE, DBNOMICS_API_KEY

logger = logging.getLogger(__name__)

REQUEST_DELAY = 0.5  # секунди между заявките (учтивост към public API)


def _parse_period(period: str) -> Optional[pd.Timestamp]:
    """DBnomics period string → Timestamp. Покрива месечно/тримесечно/годишно."""
    p = str(period).strip()
    try:
        if "-Q" in p:  # "2024-Q4" → 2024-12-31 (quarter end, като nbs_manual)
            y, q = p.split("-Q")
            return pd.Period(f"{int(y)}Q{int(q)}", freq="Q").end_time.normalize()
        if len(p) == 7 and p[4] == "-":  # "2025-07" → 2025-07-01
            return pd.Timestamp(p + "-01")
        if len(p) == 4 and p.isdigit():  # "2024" → 2024-12-31
            return pd.Timestamp(f"{p}-12-31")
        ts = pd.to_datetime(p, errors="coerce")
        return None if pd.isna(ts) else ts
    except (ValueError, TypeError):
        return None


class DBnomicsAdapter(BaseAdapter):
    """Генеричен adapter за произволен DBnomics provider/dataset/series."""

    SOURCE_NAME = "dbnomics"

    def __init__(
        self,
        cache_path: str | Path = "data/cache_dbnomics.json",
        base_dir: Optional[Path] = None,
    ):
        super().__init__(cache_path=cache_path, base_dir=base_dir)

    def _fetch_remote(self, series_key: str, source_id: str) -> pd.Series:
        """Fetch единична серия. source_id = 'PROVIDER/DATASET/SERIES_CODE'."""
        parts = source_id.split("/")
        if len(parts) != 3:
            raise RuntimeError(
                f"{series_key}: невалиден dbnomics id '{source_id}' — "
                f"очаквам 'PROVIDER/DATASET/SERIES' (3 части, не {len(parts)})"
            )
        provider, dataset, series = parts
        url = f"{DBNOMICS_API_BASE}/series/{provider}/{dataset}/{series}?observations=1"

        headers = {}
        if DBNOMICS_API_KEY:
            # Резерв за rate-limit; public достъп не го изисква.
            headers["X-API-Key"] = DBNOMICS_API_KEY

        time.sleep(REQUEST_DELAY)

        try:
            resp = requests.get(url, headers=headers, timeout=30)
            resp.raise_for_status()
        except requests.exceptions.HTTPError as e:
            raise RuntimeError(f"HTTP {resp.status_code}: {e}") from e
        except requests.exceptions.Timeout as e:
            raise RuntimeError(f"timed out: {e}") from e
        except requests.exceptions.ConnectionError as e:
            raise RuntimeError(f"Connection reset: {e}") from e

        docs = resp.json().get("series", {}).get("docs", [])
        if not docs:
            logger.warning(f"{series_key} ({source_id}): no docs in DBnomics response")
            return pd.Series(dtype=float)

        doc = docs[0]
        periods = doc.get("period", [])
        values = doc.get("value", [])
        if not periods or not values:
            logger.warning(f"{series_key} ({source_id}): empty periods/values")
            return pd.Series(dtype=float)

        records = {}
        for period, value in zip(periods, values):
            if value is None or str(value) in ("NA", ""):
                continue
            date = _parse_period(period)
            if date is None:
                continue
            try:
                records[date] = float(value)
            except (ValueError, TypeError):
                continue

        if not records:
            logger.warning(f"{series_key} ({source_id}): all values null/NA")
            return pd.Series(dtype=float)

        s = pd.Series(records, dtype=float)
        s.index = pd.DatetimeIndex(s.index)
        s = s.sort_index()
        logger.info(
            f"{series_key} ({source_id}): {len(s)} obs, "
            f"latest={s.index[-1].strftime('%Y-%m-%d')}"
        )
        return s

    def fetch_all_china_series(self, catalog: dict, force: bool = False) -> dict[str, pd.Series]:
        """Fetch всички dbnomics серии от каталога."""
        specs = [
            {"key": key, "source_id": entry["id"],
             "release_schedule": entry.get("release_schedule", "monthly")}
            for key, entry in catalog.items()
            if entry.get("source") == "dbnomics"
        ]
        logger.info(f"DBnomicsAdapter: fetching {len(specs)} series for China")
        return self.fetch_many(specs, force=force)
