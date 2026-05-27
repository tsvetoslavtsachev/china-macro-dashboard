"""
sources/akshare_cn.py
=====================
AkShare adapter за China macro dashboard.

AkShare е Python библиотека за китайски финансови и икономически данни.
Данните идват от НБС, MOFCOM, CEIC и китайски финансови сайтове.

Верифицирани функции (тествани 2025-05):
  macro_china_cpi()          — CPI (220 obs, месечен, от ~2005)
  macro_china_ppi()          — PPI (244 obs, месечен, от ~2005)
  macro_china_fdi()          — FDI actually used (185 obs, месечен, до 2023)
  macro_china_new_house_price() — 70-city house price index (368 obs, месечен)

Проблеми:
  - Много функции timeout-ват (jin10.com, sina.cn недостъпни от sandbox)
  - Данните са на китайски (колоните са на мандарин)
  - FDI данните имат gaps (NaN за някои месеци)

Стратегия:
  - Само верифицираните функции са имплементирани
  - Всяка функция има signal.alarm timeout (10 сек)
  - При timeout → fallback към кеш
"""
from __future__ import annotations

import logging
import signal
import warnings
from pathlib import Path
from typing import Optional

import pandas as pd

from sources._base import BaseAdapter

logger = logging.getLogger(__name__)

AKSHARE_TIMEOUT_SEC = 15  # timeout за всяка AkShare заявка


def _timeout_handler(signum, frame):
    raise TimeoutError("AkShare request timed out")


class AkShareAdapter(BaseAdapter):
    """Adapter за AkShare китайски макроикономически данни."""

    SOURCE_NAME = "akshare"

    def __init__(
        self,
        cache_path: str | Path = "data/cache_akshare.json",
        base_dir: Optional[Path] = None,
    ):
        super().__init__(cache_path=cache_path, base_dir=base_dir)

    def _fetch_remote(self, series_key: str, source_id: str) -> pd.Series:
        """Dispatch по source_id към конкретния AkShare fetcher."""
        fetchers = {
            "cpi_yoy":        self._fetch_cpi_yoy,
            "ppi_yoy":        self._fetch_ppi_yoy,
            "fdi_actual":     self._fetch_fdi_actual,
            "new_house_price": self._fetch_new_house_price,
        }

        fetcher = fetchers.get(source_id)
        if fetcher is None:
            raise RuntimeError(f"Unknown AkShare source_id: {source_id}")

        # Timeout wrapper
        signal.signal(signal.SIGALRM, _timeout_handler)
        signal.alarm(AKSHARE_TIMEOUT_SEC)
        try:
            result = fetcher()
            signal.alarm(0)
            return result
        except TimeoutError:
            signal.alarm(0)
            raise RuntimeError(f"timed out after {AKSHARE_TIMEOUT_SEC}s")
        except Exception as e:
            signal.alarm(0)
            raise

    # ─── Individual fetchers ──────────────────────────────────

    def _fetch_cpi_yoy(self) -> pd.Series:
        """CPI YoY % — от AkShare macro_china_cpi().

        Колони: 月份, 全国-同比增长 (national YoY % change)
        Формат на дата: '2024年03月份'
        """
        import akshare as ak
        df = ak.macro_china_cpi()

        # Парсваме китайската дата
        dates = []
        for d in df["月份"]:
            # '2024年03月份' → '2024-03'
            d_clean = str(d).replace("年", "-").replace("月份", "")
            parts = d_clean.split("-")
            if len(parts) == 2:
                dates.append(pd.Timestamp(f"{parts[0]}-{parts[1].zfill(2)}-01"))
            else:
                dates.append(pd.NaT)

        values = pd.to_numeric(df["全国-同比增长"], errors="coerce")
        series = pd.Series(values.values, index=dates, dtype=float)
        series = series[series.index.notna()].sort_index()
        return series

    def _fetch_ppi_yoy(self) -> pd.Series:
        """PPI YoY % — от AkShare macro_china_ppi().

        Колони: 月份, 当月同比增长
        """
        import akshare as ak
        df = ak.macro_china_ppi()

        dates = []
        for d in df["月份"]:
            d_clean = str(d).replace("年", "-").replace("月份", "")
            parts = d_clean.split("-")
            if len(parts) == 2:
                dates.append(pd.Timestamp(f"{parts[0]}-{parts[1].zfill(2)}-01"))
            else:
                dates.append(pd.NaT)

        values = pd.to_numeric(df["当月同比增长"], errors="coerce")
        series = pd.Series(values.values, index=dates, dtype=float)
        series = series[series.index.notna()].sort_index()
        return series

    def _fetch_fdi_actual(self) -> pd.Series:
        """FDI actually used YoY % — от AkShare macro_china_fdi().

        Колони: 月份, 当月-同比增长
        """
        import akshare as ak
        df = ak.macro_china_fdi()

        dates = []
        for d in df["月份"]:
            d_clean = str(d).replace("年", "-").replace("月份", "")
            parts = d_clean.split("-")
            if len(parts) == 2:
                dates.append(pd.Timestamp(f"{parts[0]}-{parts[1].zfill(2)}-01"))
            else:
                dates.append(pd.NaT)

        values = pd.to_numeric(df["当月-同比增长"], errors="coerce")
        series = pd.Series(values.values, index=dates, dtype=float)
        series = series[series.index.notna()].dropna().sort_index()
        return series

    def _fetch_new_house_price(self) -> pd.Series:
        """New house price index — 70 cities national average YoY %.

        AkShare macro_china_new_house_price() дава данни по град.
        Агрегираме като средна стойност на YoY % за всички градове.
        """
        import akshare as ak
        df = ak.macro_china_new_house_price()

        # Колони: 日期, 城市, 新建商品住宅价格指数-同比, 新建商品住宅价格指数-环比
        yoy_col = "新建商品住宅价格指数-同比"

        df["日期"] = pd.to_datetime(df["日期"], errors="coerce")
        df[yoy_col] = pd.to_numeric(df[yoy_col], errors="coerce")
        df = df.dropna(subset=["日期", yoy_col])

        # Средна стойност по дата (национален агрегат)
        # AkShare дава индекс с база 100 (100 = flat, 101 = +1% YoY)
        # Конвертираме към реален YoY %: (index - 100)
        national = df.groupby("日期")[yoy_col].mean()
        national = national.sort_index()
        national = national - 100.0  # 101.2 → +1.2% YoY, 99.5 → -0.5% YoY
        return national

    def fetch_all_china_series(
        self,
        catalog: dict,
        force: bool = False,
    ) -> dict[str, pd.Series]:
        """Fetch всички AkShare серии от каталога."""
        specs = []
        for key, entry in catalog.items():
            if entry.get("source") != "akshare":
                continue
            specs.append({
                "key": key,
                "source_id": entry["id"],
                "release_schedule": entry.get("release_schedule", "monthly"),
            })

        logger.info(f"AkShareAdapter: fetching {len(specs)} series for China")
        return self.fetch_many(specs, force=force)
