"""
sources — Data source adapters за China macro dashboard.

Adapters:
  WorldBankAdapter  — World Bank Indicators API (годишни данни)
  ImfIfsAdapter     — IMF IFS via DBnomics (месечни данни)
  AkShareAdapter    — AkShare Chinese macro data (месечни данни)
  FredCsvAdapter    — FRED публичен CSV (курс, BIS, REER, междубанков)
  ChinaDataLiveAdapter — chinadata.live (месечни, втори източник и кръстосани проверки)
"""
from sources._base import BaseAdapter
from sources.worldbank import WorldBankAdapter
from sources.imf_ifs import ImfIfsAdapter
from sources.akshare_cn import AkShareAdapter
from sources.chinadata_live import ChinaDataLiveAdapter
from sources.fred_csv import FredCsvAdapter

__all__ = [
    "BaseAdapter",
    "WorldBankAdapter",
    "ImfIfsAdapter",
    "AkShareAdapter",
    "ChinaDataLiveAdapter",
    "FredCsvAdapter",
]
