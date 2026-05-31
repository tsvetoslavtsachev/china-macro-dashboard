"""
sources/akshare_cn.py
=====================
AkShare adapter за China macro dashboard.

AkShare е Python библиотека за китайски финансови и икономически данни.
Данните идват от НБС, MOFCOM, CEIC и китайски финансови сайтове.

Верифицирани функции (тествани 2026-05-31, akshare 1.18.64):
  macro_china_cpi                — CPI (220 obs, месечен)
  macro_china_ppi                — PPI (244 obs, месечен)
  macro_china_fdi                — FDI actually used
  macro_china_new_house_price    — 70-city house price index
  macro_china_shrzgm             — TSF flow (132 obs от 2015-01)
  macro_china_new_financial_credit — New RMB loans (220 obs)
  macro_china_money_supply       — M0/M1/M2 (220 obs)
  macro_china_lpr                — Loan Prime Rate 1Y/5Y (1572 rows, mostly NaN pre-2013)
  macro_china_pmi                — NBS Mfg + Non-Mfg PMI (221 obs)
  macro_china_industrial_production_yoy — IP YoY (413 obs от 1990)
  macro_china_consumer_goods_retail — Retail Sales (205 obs)
  macro_china_gdzctz             — FAI (201 obs)
  macro_china_exports_yoy        — Exports USD YoY (542 obs от 1982)
  macro_china_imports_yoy        — Imports USD YoY (381 obs)
  macro_china_foreign_exchange_gold — FX reserves (415 obs от 1978)
  macro_china_cx_pmi_yearly      — Caixin Mfg PMI (219 obs от 2012)
  macro_china_cx_services_pmi_yearly — Caixin Services PMI (166 obs от 2012)

ВНИМАНИЕ:
  - signal.SIGALRM не съществува на Windows → използваме threading.Timer вместо
  - Akshare има вътрешен requests timeout, обикновено достатъчен
  - При timeout/network fail → BaseAdapter._fetch_with_retry прави retry
"""
from __future__ import annotations

import logging
import warnings
from pathlib import Path
from typing import Optional

import pandas as pd

from sources._base import BaseAdapter

logger = logging.getLogger(__name__)


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
            # Existing (Phase 1)
            "cpi_yoy":         self._fetch_cpi_yoy,
            "ppi_yoy":         self._fetch_ppi_yoy,
            "fdi_actual":      self._fetch_fdi_actual,
            "new_house_price": self._fetch_new_house_price,
            # New (Phase EU.B — Bloomberg → akshare migration)
            "tsf_flow":            self._fetch_tsf_flow,
            "new_loans":           self._fetch_new_loans,
            "m2_yoy":              self._fetch_m2_yoy,
            "lpr_1y":              self._fetch_lpr_1y,
            "lpr_5y":              self._fetch_lpr_5y,
            "pmi_mfg_nbs":         self._fetch_pmi_mfg_nbs,
            "pmi_non_mfg_nbs":     self._fetch_pmi_non_mfg_nbs,
            "ip_yoy":              self._fetch_ip_yoy,
            "retail_yoy":          self._fetch_retail_yoy,
            "fai_mom_yoy":         self._fetch_fai_mom_yoy,
            "exports_usd_yoy":     self._fetch_exports_yoy,
            "imports_usd_yoy":     self._fetch_imports_yoy,
            "fx_reserves":         self._fetch_fx_reserves,
            "pmi_mfg_caixin":      self._fetch_pmi_mfg_caixin,
            "pmi_svcs_caixin":     self._fetch_pmi_svcs_caixin,
        }

        fetcher = fetchers.get(source_id)
        if fetcher is None:
            raise RuntimeError(
                f"Unknown AkShare source_id: '{source_id}'. "
                f"Available: {sorted(fetchers.keys())}"
            )
        warnings.filterwarnings("ignore")
        return fetcher()

    # ════════════════════════════════════════════════════════
    # HELPERS
    # ════════════════════════════════════════════════════════

    @staticmethod
    def _parse_chinese_month(d) -> Optional[pd.Timestamp]:
        """Парсва различни date формати от akshare:
            '2026年04月份'      — стандартен NBS format
            '201501' / 201501  — YYYYMM (TSF shrzgm)
            '1978.12'          — YYYY.MM (FX reserves)
            '2026-04-01'       — ISO date
        Returns None ако нищо не пасне.
        """
        if d is None or (isinstance(d, float) and pd.isna(d)):
            return None
        s = str(d).strip()
        # Format 1: Chinese-style "2026年04月份"
        if "年" in s and "月" in s:
            try:
                clean = s.replace("年", "-").replace("月份", "").replace("月", "")
                parts = clean.split("-")
                if len(parts) == 2:
                    return pd.Timestamp(f"{parts[0]}-{parts[1].zfill(2)}-01")
            except Exception:
                pass
        # Format 2: YYYYMM (length 6, all digits)
        if len(s) == 6 and s.isdigit():
            try:
                return pd.Timestamp(f"{s[:4]}-{s[4:]}-01")
            except Exception:
                pass
        # Format 3: YYYY.MM
        if "." in s and len(s.split(".")) == 2:
            try:
                y, m = s.split(".")
                return pd.Timestamp(f"{y}-{m.zfill(2)}-01")
            except Exception:
                pass
        # Format 4: ISO date fallback via pandas
        try:
            ts = pd.to_datetime(s, errors="coerce")
            if not pd.isna(ts):
                return ts
        except Exception:
            pass
        return None

    @staticmethod
    def _to_series_from_chinese_month(df, month_col: str, value_col: str) -> pd.Series:
        """Helper: DataFrame с Chinese-format month + value col → sorted pd.Series."""
        dates = [AkShareAdapter._parse_chinese_month(d) for d in df[month_col]]
        values = pd.to_numeric(df[value_col], errors="coerce")
        s = pd.Series(values.values, index=dates, dtype=float)
        s = s[s.index.notna()].dropna().sort_index()
        return s

    @staticmethod
    def _to_series_from_iso_date(df, date_col: str, value_col: str) -> pd.Series:
        """Helper: DataFrame с ISO date + value col → sorted pd.Series."""
        dates = pd.to_datetime(df[date_col], errors="coerce")
        values = pd.to_numeric(df[value_col], errors="coerce")
        s = pd.Series(values.values, index=dates, dtype=float)
        s = s[s.index.notna()].dropna().sort_index()
        return s

    # ════════════════════════════════════════════════════════
    # EXISTING FETCHERS (Phase 1)
    # ════════════════════════════════════════════════════════

    def _fetch_cpi_yoy(self) -> pd.Series:
        import akshare as ak
        df = ak.macro_china_cpi()
        return self._to_series_from_chinese_month(df, "月份", "全国-同比增长")

    def _fetch_ppi_yoy(self) -> pd.Series:
        import akshare as ak
        df = ak.macro_china_ppi()
        return self._to_series_from_chinese_month(df, "月份", "当月同比增长")

    def _fetch_fdi_actual(self) -> pd.Series:
        import akshare as ak
        df = ak.macro_china_fdi()
        return self._to_series_from_chinese_month(df, "月份", "当月-同比增长")

    def _fetch_new_house_price(self) -> pd.Series:
        """70-city avg YoY %; converted from index (100=flat) to delta."""
        import akshare as ak
        df = ak.macro_china_new_house_price()
        yoy_col = "新建商品住宅价格指数-同比"
        df["日期"] = pd.to_datetime(df["日期"], errors="coerce")
        df[yoy_col] = pd.to_numeric(df[yoy_col], errors="coerce")
        df = df.dropna(subset=["日期", yoy_col])
        national = df.groupby("日期")[yoy_col].mean().sort_index() - 100.0
        return national

    # ════════════════════════════════════════════════════════
    # NEW FETCHERS (Phase EU.B — Bloomberg migration)
    # ════════════════════════════════════════════════════════

    def _fetch_tsf_flow(self) -> pd.Series:
        """TSF flow (社会融资规模增量, monthly CNY billions).

        Note: Bloomberg даваше STOCK YoY %; akshare дава FLOW absolute.
        Различни сигнали но same family — flow leads stock-cycle.
        """
        import akshare as ak
        df = ak.macro_china_shrzgm()
        return self._to_series_from_chinese_month(df, "月份", "社会融资规模增量")

    def _fetch_new_loans(self) -> pd.Series:
        """Monthly new RMB loans (当月 column)."""
        import akshare as ak
        df = ak.macro_china_new_financial_credit()
        return self._to_series_from_chinese_month(df, "月份", "当月")

    def _fetch_m2_yoy(self) -> pd.Series:
        """M2 YoY %."""
        import akshare as ak
        df = ak.macro_china_money_supply()
        return self._to_series_from_chinese_month(df, "月份", "货币和准货币(M2)-同比增长")

    def _fetch_lpr_1y(self) -> pd.Series:
        """1Y LPR (TRADE_DATE, LPR1Y cols). Pre-2013 имат NaN — dropна се."""
        import akshare as ak
        df = ak.macro_china_lpr()
        return self._to_series_from_iso_date(df, "TRADE_DATE", "LPR1Y")

    def _fetch_lpr_5y(self) -> pd.Series:
        """5Y LPR. Series започва Aug 2019."""
        import akshare as ak
        df = ak.macro_china_lpr()
        return self._to_series_from_iso_date(df, "TRADE_DATE", "LPR5Y")

    def _fetch_pmi_mfg_nbs(self) -> pd.Series:
        """Official NBS Manufacturing PMI."""
        import akshare as ak
        df = ak.macro_china_pmi()
        return self._to_series_from_chinese_month(df, "月份", "制造业-指数")

    def _fetch_pmi_non_mfg_nbs(self) -> pd.Series:
        """Official NBS Non-Manufacturing PMI (bonus — comes free with pmi function)."""
        import akshare as ak
        df = ak.macro_china_pmi()
        return self._to_series_from_chinese_month(df, "月份", "非制造业-指数")

    def _fetch_ip_yoy(self) -> pd.Series:
        """Industrial Production YoY % (规模以上工业增加值, monthly)."""
        import akshare as ak
        df = ak.macro_china_industrial_production_yoy()
        return self._to_series_from_iso_date(df, "日期", "今值")

    def _fetch_retail_yoy(self) -> pd.Series:
        """Retail sales single-month YoY %."""
        import akshare as ak
        df = ak.macro_china_consumer_goods_retail()
        return self._to_series_from_chinese_month(df, "月份", "同比增长")

    def _fetch_fai_mom_yoy(self) -> pd.Series:
        """Fixed Asset Investment single-month YoY %.

        Note: akshare gdzctz дава monthly YoY ('同比增长' col). NBS официално
        публикува YTD YoY ('自年初累计' за value, YTD YoY е derived). За
        consistency с NBS press release използвай YTD ако трябва — но monthly
        YoY е по-чист сигнал за регимна детекция.
        """
        import akshare as ak
        df = ak.macro_china_gdzctz()
        return self._to_series_from_chinese_month(df, "月份", "同比增长")

    def _fetch_exports_yoy(self) -> pd.Series:
        """Exports USD YoY % (中国以美元计算出口年率)."""
        import akshare as ak
        df = ak.macro_china_exports_yoy()
        return self._to_series_from_iso_date(df, "日期", "今值")

    def _fetch_imports_yoy(self) -> pd.Series:
        """Imports USD YoY %."""
        import akshare as ak
        df = ak.macro_china_imports_yoy()
        return self._to_series_from_iso_date(df, "日期", "今值")

    def _fetch_fx_reserves(self) -> pd.Series:
        """FX reserves (USD billions).

        Akshare 国家外汇储备 е в USD 100M (亿). Делим на 10 за да match-нем
        Bloomberg конвенцията (USD billions ≈ 3,500 за China днес).
        """
        import akshare as ak
        df = ak.macro_china_foreign_exchange_gold()
        s = self._to_series_from_chinese_month(df, "统计时间", "国家外汇储备")
        return s / 10.0

    def _fetch_pmi_mfg_caixin(self) -> pd.Series:
        """Caixin Manufacturing PMI (财新制造业PMI终值)."""
        import akshare as ak
        df = ak.macro_china_cx_pmi_yearly()
        # 日期 е release date; снап към first-of-month за consistency с други PMI
        s = self._to_series_from_iso_date(df, "日期", "今值")
        # Snap release date → reporting month (release е обикн. 1st bus day of next month)
        s.index = s.index.to_period("M").to_timestamp() - pd.offsets.MonthBegin(1)
        return s.groupby(s.index).last().sort_index()

    def _fetch_pmi_svcs_caixin(self) -> pd.Series:
        """Caixin Services PMI."""
        import akshare as ak
        df = ak.macro_china_cx_services_pmi_yearly()
        s = self._to_series_from_iso_date(df, "日期", "今值")
        s.index = s.index.to_period("M").to_timestamp() - pd.offsets.MonthBegin(1)
        return s.groupby(s.index).last().sort_index()

    # ════════════════════════════════════════════════════════
    # BATCH HELPER
    # ════════════════════════════════════════════════════════

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
