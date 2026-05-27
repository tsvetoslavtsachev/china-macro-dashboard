"""
tests/test_worldbank_fetch.py
==============================
Реален fetch тест на World Bank adapter за Китай.
Проверява дали данните се изтеглят и кешират правилно.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import logging
logging.basicConfig(level=logging.INFO, format="%(message)s")

from sources.worldbank import WorldBankAdapter
from catalog.series import SERIES_CATALOG, series_by_source

def test_worldbank():
    print("=" * 60)
    print("TEST: WorldBankAdapter — fetch China series")
    print("=" * 60)

    adapter = WorldBankAdapter(
        cache_path="data/test_cache_wb.json",
    )

    # Вземаме само World Bank серии
    wb_series = series_by_source("worldbank")
    print(f"World Bank series in catalog: {len(wb_series)}")

    # Fetch само 5 серии за тест (за да не чакаме дълго)
    test_series = wb_series[:5]
    specs = [
        {"key": s["_key"], "source_id": s["id"], "release_schedule": s["release_schedule"]}
        for s in test_series
    ]

    print(f"\nFetching {len(specs)} series...")
    results = adapter.fetch_many(specs, force=True)

    print(f"\nResults:")
    success = 0
    for key, series in results.items():
        if series is not None and not series.empty:
            latest_date = series.index[-1].strftime("%Y")
            latest_val = series.iloc[-1]
            n_obs = len(series)
            print(f"  ✓ {key}: {n_obs} obs, latest={latest_date} ({latest_val:.2f})")
            success += 1
        else:
            print(f"  ✗ {key}: empty")

    print(f"\nSuccess: {success}/{len(specs)}")
    fails = adapter.last_fetch_failures()
    if fails:
        print(f"Failures: {fails}")

    return success == len(specs)


if __name__ == "__main__":
    ok = test_worldbank()
    sys.exit(0 if ok else 1)
