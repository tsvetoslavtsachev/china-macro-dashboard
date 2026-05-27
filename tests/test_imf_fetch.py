"""
tests/test_imf_fetch.py
========================
Реален fetch тест на IMF IFS adapter за Китай.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import logging
logging.basicConfig(level=logging.INFO, format="%(message)s")

from sources.imf_ifs import ImfIfsAdapter
from catalog.series import series_by_source

def test_imf():
    print("=" * 60)
    print("TEST: ImfIfsAdapter — fetch China series")
    print("=" * 60)

    adapter = ImfIfsAdapter(cache_path="data/test_cache_imf.json")
    imf_series = series_by_source("imf_ifs")
    print(f"IMF IFS series in catalog: {len(imf_series)}")

    specs = [
        {"key": s["_key"], "source_id": s["id"], "release_schedule": s["release_schedule"]}
        for s in imf_series
    ]

    print(f"\nFetching {len(specs)} series...")
    results = adapter.fetch_many(specs, force=True)

    print(f"\nResults:")
    success = 0
    for key, series in results.items():
        if series is not None and not series.empty:
            latest_date = series.index[-1].strftime("%Y-%m")
            latest_val = series.iloc[-1]
            n_obs = len(series)
            print(f"  ✓ {key}: {n_obs} obs, latest={latest_date} ({latest_val:.4f})")
            success += 1
        else:
            print(f"  ✗ {key}: empty")

    print(f"\nSuccess: {success}/{len(specs)}")
    fails = adapter.last_fetch_failures()
    if fails:
        print(f"Failures: {fails}")

    return success > 0


if __name__ == "__main__":
    ok = test_imf()
    sys.exit(0 if ok else 1)
