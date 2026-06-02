"""
china_macro_dashboard — Entry Point
=====================================
Workflow-и:

    python run.py --status              # Data Status Screen
    python run.py --modules             # Модулен summary (lens scores)
    python run.py --refresh-only        # Refresh данни без briefing
    python run.py --briefing            # Weekly Briefing (HTML)
    python run.py --export-context      # Markdown context за LLM анализ

Глобални опции:
    --refresh        Force-fetch всички серии преди генериране
    --no-browser     Не отваря HTML в браузъра (CI / headless)

Три источника:
    worldbank  — World Bank Indicators API (годишни данни, 20 серии)
    imf_ifs    — IMF IFS via DBnomics (месечни: CPI, PPI, лихви, CNY)
    akshare    — AkShare (месечни: CPI, PPI, FDI, house prices)
"""
import argparse
import sys
import logging
import webbrowser
from pathlib import Path
from datetime import datetime

# Windows: гарантираме UTF-8 stdout/stderr за да не падне на кирилица
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))

logging.basicConfig(level=logging.INFO, format="%(message)s")

from config import MODULE_WEIGHTS, MACRO_REGIMES, OUTPUT_DIR


# ─── Adapter factory ─────────────────────────────────────────────────────────

def _build_adapters() -> dict:
    from sources.worldbank import WorldBankAdapter
    from sources.imf_ifs import ImfIfsAdapter
    from sources.akshare_cn import AkShareAdapter
    from sources.nbs_manual import NbsManualAdapter
    from sources.dbnomics import DBnomicsAdapter
    return {
        "worldbank":  WorldBankAdapter(),
        "imf_ifs":    ImfIfsAdapter(),
        "akshare":    AkShareAdapter(),
        "dbnomics":   DBnomicsAdapter(),   # генеричен provider/dataset/series (BIS, NBS, …)
        "nbs_manual": NbsManualAdapter(),  # ръчни НБС тримесечни CSV (GDP/deflator) — няма API
        # NOTE: bloomberg_bridge е специален — чете parquet, не има fetch_many
        # interface. Snapshot building го handler-ва отделно в _build_snapshot.
    }


def _build_snapshot(adapters: dict, force: bool = False) -> dict:
    """Сглобява {series_key: pd.Series} от всички adapter-и + bloomberg_bridge parquet."""
    from catalog.series import series_by_source, SERIES_CATALOG

    snapshot: dict = {}
    for source_name, adapter in adapters.items():
        specs = [
            {"key": s["_key"], "source_id": s["id"], "release_schedule": s["release_schedule"]}
            for s in series_by_source(source_name)
        ]
        if force:
            results = adapter.fetch_many(specs, force=True)
        else:
            results = adapter.get_snapshot([s["key"] for s in specs])
        snapshot.update(results)

    # Bloomberg bridge — чете parquet от vrm-data-archive (read-only)
    try:
        from sources.bloomberg_bridge_adapter import BloombergBridgeAdapter
        bridge = BloombergBridgeAdapter()
        bridge_snap = bridge.get_snapshot(SERIES_CATALOG)
        snapshot.update(bridge_snap)
    except Exception as e:
        import logging
        logging.warning(f"Bloomberg bridge snapshot failed: {e}")

    return snapshot


def _auto_refresh_stale(adapters: dict, verbose: bool = True) -> int:
    """Smart auto-refresh: fetch-ва само stale серии (TTL изтекъл)."""
    from catalog.series import series_by_source

    total_stale = 0
    total_specs = 0
    for source_name, adapter in adapters.items():
        all_specs = [
            {"key": s["_key"], "source_id": s["id"], "release_schedule": s["release_schedule"]}
            for s in series_by_source(source_name)
        ]
        total_specs += len(all_specs)
        stale_specs = adapter.find_stale_specs(all_specs)
        if stale_specs:
            total_stale += len(stale_specs)
            if verbose:
                print(f"   {source_name}: {len(stale_specs)}/{len(all_specs)} stale — fetching...")
            adapter.fetch_many(stale_specs, force=False)
            adapter.save_cache()
            fails = adapter.last_fetch_failures()
            if fails and verbose:
                print(f"   ⚠ {source_name}: {len(fails)} failed — {', '.join(fails[:5])}")

    if verbose:
        n_fresh = total_specs - total_stale
        if total_stale == 0:
            print(f"📦 Cache: {n_fresh}/{total_specs} fresh — всичко up-to-date.")
        else:
            print(f"📦 Cache: {n_fresh}/{total_specs} fresh; {total_stale} stale — auto-refresh complete.")
    return total_stale


# ─── Commands ────────────────────────────────────────────────────────────────

def cmd_status(args) -> int:
    """Data Status Screen — показва кои серии са кешувани и кога."""
    from catalog.series import SERIES_CATALOG, series_by_source
    from export.data_status import generate_status_report

    print(f"🇨🇳 China Macro Dashboard — Data Status")
    print(f"📊 Catalog: {len(SERIES_CATALOG)} series")

    adapters = _build_adapters()

    if args.refresh:
        print("\n🔄 --refresh: fetching all catalog series...")
        for source_name, adapter in adapters.items():
            specs = [
                {"key": s["_key"], "source_id": s["id"], "release_schedule": s["release_schedule"]}
                for s in series_by_source(source_name)
            ]
            if specs:
                print(f"   {source_name}: fetching {len(specs)} series...")
                adapter.fetch_many(specs, force=True)
                fails = adapter.last_fetch_failures()
                if fails:
                    print(f"   ⚠ {source_name}: {len(fails)} failed: {', '.join(fails)}")

    generate_status_report(SERIES_CATALOG, adapters)
    return 0


def cmd_modules(args) -> int:
    """Модулен summary — оценява всеки lens и показва composite score."""
    import modules.growth as growth_mod
    import modules.inflation as inflation_mod
    import modules.labor as labor_mod
    import modules.credit as credit_mod
    import modules.property as property_mod

    adapters = _build_adapters()

    if args.refresh:
        print("🔄 --refresh: force fetch на всички серии...")
        from catalog.series import series_by_source
        for source_name, adapter in adapters.items():
            specs = [
                {"key": s["_key"], "source_id": s["id"], "release_schedule": s["release_schedule"]}
                for s in series_by_source(source_name)
            ]
            if specs:
                adapter.fetch_many(specs, force=True)
    else:
        _auto_refresh_stale(adapters, verbose=True)

    snapshot = _build_snapshot(adapters, force=False)

    if not snapshot:
        print("⚠ Snapshot е празен. Стартирай `python run.py --status --refresh` първо.")
        return 1

    print(f"\n🇨🇳 China Macro Dashboard — Модулен Summary")
    print(f"📦 Snapshot: {len(snapshot)} серии заредени\n")

    modules_to_run = [
        ("growth",    growth_mod),
        ("inflation", inflation_mod),
        ("labor",     labor_mod),
        ("credit",    credit_mod),
        ("property",  property_mod),
    ]

    results: list[dict] = []
    for name, mod in modules_to_run:
        try:
            result = mod.run(snapshot)
        except Exception as e:
            print(f"  ❌ {name}: грешка — {e}")
            import traceback
            traceback.print_exc()
            continue
        results.append(result)
        score = result["composite"]
        regime = result["regime"]
        n_indic = len(result.get("indicators", {}))
        print(f"  {result['icon']} {result['label']:35}  score={score:5.1f}  {regime:30}  ({n_indic} серии)")

        # Narrative hints
        for hint in result.get("narrative", []):
            print(f"       → {hint}")

    if results:
        weighted = sum(
            r["composite"] * MODULE_WEIGHTS.get(r["module"], 0)
            for r in results
        )
        total_weight = sum(MODULE_WEIGHTS.get(r["module"], 0) for r in results)
        overall = round(weighted / total_weight, 1) if total_weight else 50.0
        print()
        print(f"  📊 Композитен Macro Score: {overall:.1f}")

        # Режим
        for threshold, label, color in MACRO_REGIMES:
            if overall >= threshold:
                print(f"  🏷️  Режим: {label}")
                break

    return 0


def cmd_refresh_only(args) -> int:
    """Pure data refresh без HTML output."""
    adapters = _build_adapters()

    if args.refresh:
        print("🔄 --refresh-only --refresh: force fetch на всички серии...")
        from catalog.series import series_by_source
        for source_name, adapter in adapters.items():
            specs = [
                {"key": s["_key"], "source_id": s["id"], "release_schedule": s["release_schedule"]}
                for s in series_by_source(source_name)
            ]
            print(f"   {source_name}: fetching {len(specs)} series...")
            adapter.fetch_many(specs, force=True)
            adapter.save_cache()
            fails = adapter.last_fetch_failures()
            if fails:
                print(f"   ⚠ {source_name}: {len(fails)} failed: {', '.join(fails)}")
        print("✓ Force refresh complete.")
    else:
        print("🔄 --refresh-only: smart refresh на stale серии...")
        n_stale = _auto_refresh_stale(adapters, verbose=True)
        if n_stale == 0:
            print("✓ Никаква серия не е stale; cache е up-to-date.")
        else:
            print(f"✓ Smart refresh complete ({n_stale} stale серии fetch-нати).")
    return 0


def cmd_briefing(args) -> int:
    """Weekly Briefing — генерира HTML briefing."""
    from export.weekly_briefing import generate_weekly_briefing

    adapters = _build_adapters()

    if not args.refresh:
        _auto_refresh_stale(adapters, verbose=True)

    snapshot = _build_snapshot(adapters, force=args.refresh)

    if not snapshot:
        print("⚠ Snapshot е празен. Стартирай `python run.py --status --refresh` първо.")
        return 1

    print(f"\n📦 Snapshot: {len(snapshot)} серии заредени")

    output_path = f"{OUTPUT_DIR}/briefing_{datetime.now().strftime('%Y-%m-%d')}.html"
    print(f"📝 Генериране на HTML → {output_path}")

    generate_weekly_briefing(
        snapshot=snapshot,
        output_path=output_path,
    )

    print(f"✓ Briefing готов: {output_path}")
    if not args.no_browser:
        try:
            webbrowser.open(f"file://{Path(output_path).resolve()}")
        except Exception:
            pass
    return 0


def cmd_deep(args) -> int:
    """Deep Briefing — генерира подробния research-style HTML (зад линк от landing-а)."""
    from export.deep_briefing import generate_deep_briefing

    adapters = _build_adapters()

    if not args.refresh:
        _auto_refresh_stale(adapters, verbose=True)

    snapshot = _build_snapshot(adapters, force=args.refresh)

    if not snapshot:
        print("⚠ Snapshot е празен. Стартирай `python run.py --status --refresh` първо.")
        return 1

    print(f"\n📦 Snapshot: {len(snapshot)} серии заредени")

    output_path = f"{OUTPUT_DIR}/briefing_deep_{datetime.now().strftime('%Y-%m-%d')}.html"
    print(f"📝 Генериране на подробен HTML → {output_path}")

    generate_deep_briefing(
        snapshot=snapshot,
        output_path=output_path,
    )

    print(f"✓ Подробен briefing готов: {output_path}")
    if not args.no_browser:
        try:
            webbrowser.open(f"file://{Path(output_path).resolve()}")
        except Exception:
            pass
    return 0


def cmd_export_context(args) -> int:
    """Markdown context export за LLM анализ."""
    from export.briefing_context import generate_briefing_context
    from datetime import date

    adapters = _build_adapters()

    if not args.refresh:
        _auto_refresh_stale(adapters, verbose=True)

    snapshot = _build_snapshot(adapters, force=args.refresh)

    if not snapshot:
        print("⚠ Snapshot е празен. Стартирай `python run.py --status --refresh` първо.")
        return 1

    print(f"\n📦 Snapshot: {len(snapshot)} серии заредени")

    today = date.today()
    output_path = f"{OUTPUT_DIR}/briefing_context_{today.isoformat()}.md"
    print(f"📝 Генериране на context markdown → {output_path}")

    generate_briefing_context(
        snapshot=snapshot,
        output_path=output_path,
        today=today,
    )

    print(f"✓ Context готов: {output_path}")
    return 0


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="China Macro Dashboard — седмичен briefing на български.",
    )
    parser.add_argument("--status", action="store_true",
                        help="Data Status Screen")
    parser.add_argument("--modules", action="store_true",
                        help="Modules summary — growth/inflation/labor/credit/property")
    parser.add_argument("--refresh-only", action="store_true",
                        help="Refresh данни без briefing")
    parser.add_argument("--briefing", action="store_true",
                        help="Weekly Briefing (HTML) — кратък landing")
    parser.add_argument("--deep", action="store_true",
                        help="Deep Briefing (HTML) — подробен research-style анализ")
    parser.add_argument("--export-context", action="store_true",
                        help="Markdown context export за LLM анализ")
    parser.add_argument("--refresh", action="store_true",
                        help="Force-fetch всички серии преди генериране")
    parser.add_argument("--no-browser", action="store_true",
                        help="Не отваря HTML в браузъра")
    args = parser.parse_args()

    # Гарантираме output директория
    Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)

    if args.status:
        return cmd_status(args)
    elif args.modules:
        return cmd_modules(args)
    elif getattr(args, "refresh_only", False):
        return cmd_refresh_only(args)
    elif args.briefing:
        return cmd_briefing(args)
    elif args.deep:
        return cmd_deep(args)
    elif getattr(args, "export_context", False):
        return cmd_export_context(args)
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
