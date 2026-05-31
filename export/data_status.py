"""
export/data_status.py
=====================
Прост data status report за China macro dashboard.
Показва кои серии са кешувани и кога.
"""
from __future__ import annotations
from datetime import datetime
from pathlib import Path


def generate_status_report(catalog: dict, adapters: dict) -> None:
    """Принтира status на кешираните серии по adapter."""
    print()
    print("=" * 70)
    print("  CHINA MACRO DASHBOARD — Data Status")
    print("=" * 70)

    total_cached = 0
    total_series = 0

    for source_name, adapter in adapters.items():
        cache = getattr(adapter, "_cache", {})
        n_cached = len(cache)
        total_cached += n_cached

        # Намери серии от каталога за този source
        source_series = [
            (k, v) for k, v in catalog.items()
            if v.get("source") == source_name
        ]
        n_total = len(source_series)
        total_series += n_total

        print(f"\n  [{source_name.upper()}]  {n_cached}/{n_total} серии кешувани")

        for key, meta in source_series:
            # Use adapter method to reconstruct Series от cache entry
            try:
                series = adapter._series_from_cache(key)
            except AttributeError:
                series = None
            if series is not None and not series.empty:
                latest = series.dropna()
                if not latest.empty:
                    last_date = str(latest.index[-1])[:10]
                    n_obs = len(latest)
                    status = "✓"
                else:
                    last_date = "—"
                    n_obs = 0
                    status = "⚠"
            else:
                last_date = "—"
                n_obs = 0
                status = "✗"

            name = meta.get("name_bg", key)[:45]
            print(f"    {status}  {key:<30}  {n_obs:>4} obs  latest: {last_date}  {name}")

    print()
    print(f"  ОБЩО: {total_cached}/{total_series} серии кешувани")
    print("=" * 70)
    print()
