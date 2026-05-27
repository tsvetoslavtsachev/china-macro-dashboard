"""
sources/worldbank.py
====================
World Bank Indicators API adapter за China macro dashboard.

Endpoint:
  GET https://api.worldbank.org/v2/country/CN/indicator/{indicator}
  ?format=json&per_page=100&mrv=30&date=2000:2025

Специфики за Китай:
  - Всички серии са годишни (annually)
  - Данните за текущата година са предварителни (revision_prone)
  - Lag: ~Q1 следващата година за повечето индикатори
  - Надежден API без authentication
"""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Optional

import pandas as pd
import requests

from sources._base import BaseAdapter

logger = logging.getLogger(__name__)

WB_BASE = "https://api.worldbank.org/v2"
WB_COUNTRY = "CN"
WB_PER_PAGE = 100
WB_MAX_HISTORY_YEARS = 30
WB_REQUEST_DELAY = 0.3  # секунди между заявките (rate limit)


class WorldBankAdapter(BaseAdapter):
    """Adapter за World Bank Indicators API (годишни данни за Китай)."""

    SOURCE_NAME = "worldbank"

    def __init__(
        self,
        cache_path: str | Path = "data/cache_worldbank.json",
        base_dir: Optional[Path] = None,
        history_start: str = "2000",
    ):
        super().__init__(cache_path=cache_path, base_dir=base_dir)
        self.history_start = str(history_start)[:4]  # само годината

    def _fetch_remote(self, series_key: str, source_id: str) -> pd.Series:
        """Fetch единична World Bank серия за Китай.

        source_id е World Bank indicator code, напр. 'NY.GDP.MKTP.KD.ZG'
        """
        url = (
            f"{WB_BASE}/country/{WB_COUNTRY}/indicator/{source_id}"
            f"?format=json&per_page={WB_PER_PAGE}&mrv={WB_MAX_HISTORY_YEARS}"
            f"&date={self.history_start}:2025"
        )

        time.sleep(WB_REQUEST_DELAY)

        try:
            resp = requests.get(url, timeout=20)
            resp.raise_for_status()
        except requests.exceptions.HTTPError as e:
            raise RuntimeError(f"HTTP {resp.status_code}: {e}") from e
        except requests.exceptions.Timeout as e:
            raise RuntimeError(f"timed out: {e}") from e
        except requests.exceptions.ConnectionError as e:
            raise RuntimeError(f"Connection reset: {e}") from e

        data = resp.json()

        # World Bank response: [metadata, [observations]]
        if not isinstance(data, list) or len(data) < 2:
            raise RuntimeError(f"Unexpected response structure for {source_id}")

        observations = data[1]
        if not observations:
            logger.warning(f"{series_key} ({source_id}): no observations returned")
            return pd.Series(dtype=float)

        records = {}
        for obs in observations:
            date_str = obs.get("date")
            value = obs.get("value")
            if date_str and value is not None:
                try:
                    # World Bank дава само годината → конвертираме към 31 декември
                    year = int(date_str)
                    date = pd.Timestamp(f"{year}-12-31")
                    records[date] = float(value)
                except (ValueError, TypeError):
                    continue

        if not records:
            logger.warning(f"{series_key} ({source_id}): all observations null")
            return pd.Series(dtype=float)

        series = pd.Series(records, dtype=float)
        series.index = pd.DatetimeIndex(series.index)
        series = series.sort_index()

        logger.info(
            f"{series_key} ({source_id}): {len(series)} obs, "
            f"latest={series.index[-1].strftime('%Y')}"
        )
        return series

    def fetch_all_china_series(
        self,
        catalog: dict,
        force: bool = False,
    ) -> dict[str, pd.Series]:
        """Fetch всички World Bank серии от каталога.

        catalog: речник от {key: entry} от catalog/series.py
        """
        specs = []
        for key, entry in catalog.items():
            if entry.get("source") != "worldbank":
                continue
            specs.append({
                "key": key,
                "source_id": entry["id"],
                "release_schedule": entry.get("release_schedule", "annually"),
            })

        logger.info(f"WorldBankAdapter: fetching {len(specs)} series for China")
        return self.fetch_many(specs, force=force)
