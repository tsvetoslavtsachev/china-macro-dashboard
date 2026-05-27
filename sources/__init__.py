"""
sources — Data source adapters за China macro dashboard.

Adapters:
  WorldBankAdapter  — World Bank Indicators API (годишни данни)
  ImfIfsAdapter     — IMF IFS via DBnomics (месечни данни)
  AkShareAdapter    — AkShare Chinese macro data (месечни данни)
"""
from sources._base import BaseAdapter
from sources.worldbank import WorldBankAdapter
from sources.imf_ifs import ImfIfsAdapter
from sources.akshare_cn import AkShareAdapter

__all__ = [
    "BaseAdapter",
    "WorldBankAdapter",
    "ImfIfsAdapter",
    "AkShareAdapter",
]
