"""
sources/imf_ifs.py
==================
IMF International Financial Statistics (IFS) adapter за China macro dashboard.
Достъп чрез DBnomics API.

Endpoint:
  GET https://api.db.nomics.world/v22/series/IMF/IFS/{series_code}?observations=1

Верифицирани серии за Китай (тествани 2025-05):
  M.CN.PCPI_IX      — CPI Index (месечен)
  M.CN.PPPI_IX      — PPI Index (месечен, данни до 2022)
  M.CN.ENDA_XDC_USD_RATE — CNY/USD exchange rate
  M.CN.FILR_PA      — Lending rate (%)
  M.CN.FIDR_PA      — Deposit rate (%)
  M.CN.FPOLM_PA     — Policy rate (7-day repo, %)

Специфики:
  - Месечна честота за повечето серии
  - PPI данни само до 2022-12 (IMF IFS ограничение)
  - Без authentication
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

DBNOMICS_BASE = "https://api.db.nomics.world/v22"
REQUEST_DELAY = 0.5  # секунди между заявките


class ImfIfsAdapter(BaseAdapter):
    """Adapter за IMF IFS данни за Китай чрез DBnomics."""

    SOURCE_NAME = "imf_ifs"

    def __init__(
        self,
        cache_path: str | Path = "data/cache_imf_ifs.json",
        base_dir: Optional[Path] = None,
    ):
        super().__init__(cache_path=cache_path, base_dir=base_dir)

    def _fetch_remote(self, series_key: str, source_id: str) -> pd.Series:
        """Fetch единична IMF IFS серия от DBnomics.

        source_id е DBnomics series code, напр. 'M.CN.PCPI_IX'
        """
        url = f"{DBNOMICS_BASE}/series/IMF/IFS/{source_id}?observations=1"

        time.sleep(REQUEST_DELAY)

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
        docs = data.get("series", {}).get("docs", [])

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
            try:
                # DBnomics дава "YYYY-MM" формат за месечни данни
                date = pd.Timestamp(period + "-01")
                records[date] = float(value)
            except (ValueError, TypeError):
                continue

        if not records:
            logger.warning(f"{series_key} ({source_id}): all values null/NA")
            return pd.Series(dtype=float)

        series = pd.Series(records, dtype=float)
        series.index = pd.DatetimeIndex(series.index)
        series = series.sort_index()

        logger.info(
            f"{series_key} ({source_id}): {len(series)} obs, "
            f"latest={series.index[-1].strftime('%Y-%m')}"
        )
        return series

    def fetch_all_china_series(
        self,
        catalog: dict,
        force: bool = False,
    ) -> dict[str, pd.Series]:
        """Fetch всички IMF IFS серии от каталога."""
        specs = []
        for key, entry in catalog.items():
            if entry.get("source") != "imf_ifs":
                continue
            specs.append({
                "key": key,
                "source_id": entry["id"],
                "release_schedule": entry.get("release_schedule", "monthly"),
            })

        logger.info(f"ImfIfsAdapter: fetching {len(specs)} series for China")
        return self.fetch_many(specs, force=force)
