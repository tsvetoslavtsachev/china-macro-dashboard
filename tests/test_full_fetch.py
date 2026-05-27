"""
tests/test_full_fetch.py
=========================
Пълен fetch на всички серии + модулен тест.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import logging
logging.basicConfig(level=logging.INFO, format="%(message)s")

from sources.worldbank import WorldBankAdapter
from sources.imf_ifs import ImfIfsAdapter
from catalog.series import SERIES_CATALOG, series_by_source

print("=" * 65)
print("FULL FETCH TEST — China Macro Dashboard")
print("=" * 65)

# World Bank
print("\n[1/3] WorldBankAdapter — 17 series...")
wb_adapter = WorldBankAdapter()
wb_specs = [
    {"key": s["_key"], "source_id": s["id"], "release_schedule": s["release_schedule"]}
    for s in series_by_source("worldbank")
]
wb_results = wb_adapter.fetch_many(wb_specs, force=True)
wb_ok = sum(1 for v in wb_results.values() if v is not None and not v.empty)
print(f"  ✓ {wb_ok}/{len(wb_specs)} series fetched")
wb_fails = wb_adapter.last_fetch_failures()
if wb_fails:
    print(f"  ✗ Failures: {wb_fails}")

# IMF IFS
print("\n[2/3] ImfIfsAdapter — 6 series...")
imf_adapter = ImfIfsAdapter()
imf_specs = [
    {"key": s["_key"], "source_id": s["id"], "release_schedule": s["release_schedule"]}
    for s in series_by_source("imf_ifs")
]
imf_results = imf_adapter.fetch_many(imf_specs, force=True)
imf_ok = sum(1 for v in imf_results.values() if v is not None and not v.empty)
print(f"  ✓ {imf_ok}/{len(imf_specs)} series fetched")
imf_fails = imf_adapter.last_fetch_failures()
if imf_fails:
    print(f"  ✗ Failures: {imf_fails}")

# AkShare (само CPI и PPI)
print("\n[3/3] AkShareAdapter — 2 series (CPI, PPI)...")
from sources.akshare_cn import AkShareAdapter
ak_adapter = AkShareAdapter()
ak_specs = [
    {"key": s["_key"], "source_id": s["id"], "release_schedule": s["release_schedule"]}
    for s in series_by_source("akshare")
]
ak_results = ak_adapter.fetch_many(ak_specs, force=True)
ak_ok = sum(1 for v in ak_results.values() if v is not None and not v.empty)
print(f"  ✓ {ak_ok}/{len(ak_specs)} series fetched")
ak_fails = ak_adapter.last_fetch_failures()
if ak_fails:
    print(f"  ✗ Failures: {ak_fails}")

# Build snapshot
snapshot = {}
snapshot.update(wb_results)
snapshot.update(imf_results)
snapshot.update(ak_results)
print(f"\n📦 Total snapshot: {len(snapshot)} series")

# Module tests
print("\n" + "=" * 65)
print("MODULE TESTS")
print("=" * 65)

import modules.growth as growth_mod
import modules.inflation as inflation_mod
import modules.labor as labor_mod
import modules.credit as credit_mod
import modules.property as property_mod

from config import MODULE_WEIGHTS, MACRO_REGIMES

modules_to_run = [
    ("growth",    growth_mod),
    ("inflation", inflation_mod),
    ("labor",     labor_mod),
    ("credit",    credit_mod),
    ("property",  property_mod),
]

results = []
for name, mod in modules_to_run:
    try:
        result = mod.run(snapshot)
        results.append(result)
        score = result["composite"]
        regime = result["regime"]
        n_indic = len(result.get("indicators", {}))
        print(f"\n  {result['icon']} {result['label']}")
        print(f"     Score: {score:.1f}  |  Режим: {regime}  |  Серии: {n_indic}")
        for hint in result.get("narrative", []):
            print(f"     → {hint}")
    except Exception as e:
        print(f"  ❌ {name}: грешка — {e}")
        import traceback
        traceback.print_exc()

# Composite
if results:
    weighted = sum(r["composite"] * MODULE_WEIGHTS.get(r["module"], 0) for r in results)
    total_weight = sum(MODULE_WEIGHTS.get(r["module"], 0) for r in results)
    overall = round(weighted / total_weight, 1) if total_weight else 50.0
    print(f"\n{'=' * 65}")
    print(f"  📊 Композитен Macro Score: {overall:.1f}")
    for threshold, label, color in MACRO_REGIMES:
        if overall >= threshold:
            print(f"  🏷️  Режим: {label}")
            break
