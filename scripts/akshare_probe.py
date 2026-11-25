# -*- coding: utf-8 -*-
"""ИЛЮ3 Е2 (23.11.2026): пробата преди вдигане на akshare.

Пуска на живо всичките извиквания на akshare в таблото (20 серии на AkShareAdapter и
lpr_frame за lpr.json) под инсталираната версия и печата таблица: серия, минава ли,
последна дата. Изход 0 само при всички минали; иначе 1. Версията в requirements.txt се
вдига само след 20 от 20 под новата версия (в отделна среда).

    python scripts/akshare_probe.py
"""
import os
import sys
import time
import warnings

warnings.filterwarnings("ignore")
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

import akshare as ak  # noqa: E402
from sources.akshare_cn import AkShareAdapter, lpr_frame  # noqa: E402

IDS = ["cpi_yoy", "ppi_yoy", "fdi_actual", "new_house_price", "tsf_flow", "new_loans", "m2_yoy",
       "lpr_1y", "lpr_5y", "pmi_mfg_nbs", "pmi_non_mfg_nbs", "ip_yoy", "retail_yoy", "fai_mom_yoy",
       "exports_usd_yoy", "imports_usd_yoy", "fx_reserves", "pmi_mfg_caixin", "pmi_svcs_caixin", "unemp_surveyed"]


def _try(fn, tries=3):
    err = None
    for _ in range(tries):          # източникът понякога прекъсва отговора
        try:
            return fn(), None
        except Exception as e:  # noqa: BLE001
            err = f"{type(e).__name__}: {e}"[:160]
            time.sleep(3)
    return None, err


def main() -> int:
    ad = AkShareAdapter(cache_path=os.path.join(os.environ.get("TEMP", REPO), "akshare_probe_cache.json"))
    rows = []
    for sid in IDS:
        s, err = _try(lambda: ad._fetch_remote(sid, sid).dropna())
        rows.append((sid, s is not None, str(s.index.max())[:10] if s is not None and len(s) else err))
    df, err = _try(lpr_frame)
    rows.append(("lpr.json (lpr_frame)", df is not None, str(df["TRADE_DATE"].max())[:10] if df is not None else err))
    print(f"akshare {ak.__version__}")
    for sid, ok, info in rows:
        print(f"  {'OK  ' if ok else 'FAIL'} {sid:22} {info}")
    good = sum(ok for _, ok, _ in rows)
    print(f"{good} от {len(rows)}")
    return 0 if good == len(rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
