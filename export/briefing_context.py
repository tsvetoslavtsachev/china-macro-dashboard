"""
export/briefing_context.py
==========================
Markdown context export за LLM анализ на China macro dashboard.
"""
from __future__ import annotations
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from catalog.series import SERIES_CATALOG
# Единствен източник на тегла/режими — config.py. По-рано briefing_context държеше
# СОБСТВЕНИ (различни) MODULE_WEIGHTS/MACRO_REGIMES, заради което context.md и
# macro_state.json/deep.html казваха РАЗЛИЧЕН режим за същите данни (audit #8).
from config import MODULE_WEIGHTS, MACRO_REGIMES, overall_composite


def _get_regime(score: float) -> str:
    # MACRO_REGIMES в config са 3-element (threshold, label, color) → разопаковаме *_.
    for threshold, label, *_ in MACRO_REGIMES:
        if score >= threshold:
            return label
    return "НЕИЗВЕСТЕН"


def generate_briefing_context(
    snapshot: dict,
    output_path: str,
    today: Optional[date] = None,
    **kwargs,
) -> None:
    """Генерира Markdown context за LLM анализ."""
    import modules.growth as growth_mod
    import modules.inflation as inflation_mod
    import modules.labor as labor_mod
    import modules.credit as credit_mod
    import modules.property as property_mod

    if today is None:
        today = date.today()

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
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Module {name} failed: {e}")

    overall = overall_composite(results)   # config: None-safe reweight върху backed лещи (#9)
    regime = _get_regime(overall)

    lines = []
    lines.append(f"# 🇨🇳 China Macro Dashboard — Context за LLM анализ")
    lines.append(f"**Дата:** {today.strftime('%d %B %Y')}  ")
    lines.append(f"**Генериран:** {datetime.now().strftime('%Y-%m-%d %H:%M')} UTC  ")
    lines.append(f"**Серии:** {len(snapshot)}  ")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(f"## Композитен Macro Score: {overall:.1f} / 100")
    lines.append(f"**Режим:** {regime}")
    lines.append("")
    lines.append("| Lens | Score | Режим |")
    lines.append("|------|-------|-------|")
    for r in results:
        lines.append(f"| {r.get('label', r['module'])} | {r['composite']:.1f} | {r['regime']} |")
    lines.append("")
    lines.append("---")
    lines.append("")

    for r in results:
        lines.append(f"## {r.get('icon', '')} {r.get('label', r['module'])}")
        lines.append(f"**Score:** {r['composite']:.1f}  **Режим:** {r['regime']}")
        lines.append("")

        readings = r.get("key_readings", [])
        if readings:
            lines.append("### Ключови показатели")
            lines.append("")
            lines.append("| Показател | Стойност | Percentile | Дата |")
            lines.append("|-----------|----------|------------|------|")
            for rd in readings:
                val = rd.get("value")
                val_str = f"{float(val):.2f}" if val is not None else "—"
                pct = rd.get("percentile", 50)
                date_str = str(rd.get("date", ""))[:10]
                lines.append(f"| {rd.get('label', '')} | {val_str} | {pct:.0f}% | {date_str} |")
            lines.append("")

        narrative = r.get("narrative", [])
        if narrative:
            lines.append("### Анализ")
            lines.append("")
            for hint in narrative:
                lines.append(f"- {hint}")
            lines.append("")

        lines.append("---")
        lines.append("")

    lines.append("## ⚠ Бележки за качеството на данните")
    lines.append("")
    lines.append("- Официалната безработица (~5%) не включва ~300 млн. мигрантски работници.")
    lines.append("- Младежката безработица беше спряна от НБС юли–декември 2023 след рекорд 21.3%.")
    lines.append("- GDP данните са годишни (World Bank). Месечни данни са ограничено достъпни.")
    lines.append("- PPI от IMF IFS е само до декември 2022. AkShare дава по-актуални данни.")
    lines.append("- FDI срина се до ~0.1% от GDP (2024) — геополитически de-risking.")
    lines.append("- GDP дефлаторът е отрицателен от 2023 — широка дефлация.")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("*Данни: World Bank Indicators API · IMF IFS via DBnomics · AkShare/НБС*")

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
