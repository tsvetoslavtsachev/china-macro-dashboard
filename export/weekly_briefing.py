"""
export/weekly_briefing.py
=========================
HTML weekly briefing renderer за China macro dashboard.

Sections (BG):
  1. Header — заглавие, дата, брой серии
  2. Composite Score — общ macro score + режим
  3. Per-lens blocks — score, режим, key readings, narrative
  4. Data Quality Notes — специфики за китайски данни
  5. Footer — методология

Self-contained HTML: inline CSS, без JS, без CDN.
"""
from __future__ import annotations
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from catalog.series import SERIES_CATALOG


# ─── Labels ──────────────────────────────────────────────────────

LENS_ORDER = ["growth", "inflation", "labor", "credit", "property"]
LENS_LABEL_BG = {
    "growth":    "Растеж и активност",
    "inflation": "Инфлация и цени",
    "labor":     "Пазар на труда",
    "credit":    "Монетарна политика и кредит",
    "property":  "Имоти и търговия",
}
LENS_ICON = {
    "growth": "📈", "inflation": "🔥", "labor": "👷",
    "credit": "🏦", "property": "🏗️",
}

MODULE_WEIGHTS = {
    "growth": 0.30,
    "inflation": 0.20,
    "labor": 0.15,
    "credit": 0.20,
    "property": 0.15,
}

MACRO_REGIMES = [
    (75, "СИЛНА ИКОНОМИКА",    "#00c853"),
    (60, "УМЕРЕН РАСТЕЖ",      "#69f0ae"),
    (45, "СМЕСЕНИ СИГНАЛИ",    "#ffd600"),
    (30, "РЕЦЕСИОНЕН",         "#ff6d00"),
    (0,  "КРИЗА",              "#d50000"),
]


# ─── CSS ─────────────────────────────────────────────────────────

CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
    background: #0d1117; color: #e6edf3;
    line-height: 1.6; font-size: 14px;
}
.container { max-width: 1100px; margin: 0 auto; padding: 24px 16px; }

.header {
    background: linear-gradient(135deg, #1a1f2e 0%, #161b27 100%);
    border: 1px solid #30363d; border-radius: 12px;
    padding: 28px 32px; margin-bottom: 24px;
    display: flex; justify-content: space-between; align-items: center;
}
.header-left h1 { font-size: 26px; font-weight: 700; color: #f0f6fc; }
.header-left h1 .flag { font-size: 30px; margin-right: 8px; }
.header-left .subtitle { color: #8b949e; font-size: 13px; margin-top: 4px; }
.header-right { text-align: right; }
.header-right .date { color: #8b949e; font-size: 13px; }
.header-right .series-count { font-size: 22px; font-weight: 700; color: #58a6ff; margin-top: 4px; }
.header-right .series-label { color: #8b949e; font-size: 11px; }

.composite-card {
    background: #161b27; border: 1px solid #30363d; border-radius: 12px;
    padding: 24px 32px; margin-bottom: 24px;
    display: flex; align-items: center; gap: 32px;
}
.score-circle {
    width: 90px; height: 90px; border-radius: 50%;
    display: flex; flex-direction: column; align-items: center;
    justify-content: center; flex-shrink: 0; border: 3px solid;
}
.score-circle .score-num { font-size: 28px; font-weight: 800; }
.score-circle .score-label { font-size: 10px; color: #8b949e; }
.composite-info h2 { font-size: 18px; font-weight: 600; color: #f0f6fc; }
.composite-info .regime-badge {
    display: inline-block; padding: 4px 14px; border-radius: 20px;
    font-size: 12px; font-weight: 700; margin-top: 8px; letter-spacing: 0.5px;
}
.composite-info .description { color: #8b949e; font-size: 13px; margin-top: 8px; }

.lens-grid {
    display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
    gap: 16px; margin-bottom: 24px;
}
.lens-card {
    background: #161b27; border: 1px solid #30363d; border-radius: 10px;
    padding: 20px;
}
.lens-card-header {
    display: flex; justify-content: space-between; align-items: flex-start;
    margin-bottom: 16px;
}
.lens-title { font-size: 15px; font-weight: 600; color: #f0f6fc; }
.lens-icon { font-size: 20px; }
.lens-score-row { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }
.lens-score-bar-wrap { flex: 1; height: 8px; background: #21262d; border-radius: 4px; overflow: hidden; }
.lens-score-bar { height: 100%; border-radius: 4px; }
.lens-score-num { font-size: 18px; font-weight: 700; min-width: 40px; text-align: right; }
.lens-regime {
    font-size: 11px; font-weight: 600; padding: 2px 10px;
    border-radius: 12px; display: inline-block; margin-bottom: 12px; letter-spacing: 0.3px;
}

.readings-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.readings-table th {
    text-align: left; color: #8b949e; font-weight: 500;
    padding: 4px 6px; border-bottom: 1px solid #21262d;
}
.readings-table td { padding: 5px 6px; border-bottom: 1px solid #161b27; }
.readings-table tr:last-child td { border-bottom: none; }
.val-pos { color: #3fb950; }
.val-neg { color: #f85149; }
.val-neu { color: #e6edf3; }
.pct-bar-wrap { width: 60px; height: 6px; background: #21262d; border-radius: 3px; display: inline-block; vertical-align: middle; }
.pct-bar { height: 100%; border-radius: 3px; }

.narrative { margin-top: 12px; }
.narrative-item {
    font-size: 12px; color: #8b949e; padding: 5px 10px;
    border-left: 2px solid #30363d; margin-bottom: 6px;
    background: #0d1117; border-radius: 0 4px 4px 0;
}
.narrative-item.warn { border-left-color: #d29922; color: #d29922; }

.dq-card {
    background: #161b27; border: 1px solid #d29922; border-radius: 10px;
    padding: 20px; margin-bottom: 24px;
}
.dq-card h3 { color: #d29922; font-size: 14px; margin-bottom: 12px; }
.dq-item { font-size: 12px; color: #8b949e; margin-bottom: 6px; padding-left: 12px; }
.dq-item::before { content: "⚠ "; color: #d29922; }

.footer {
    background: #161b27; border: 1px solid #30363d; border-radius: 10px;
    padding: 16px 20px; color: #8b949e; font-size: 11px;
}
.footer strong { color: #58a6ff; }
"""


# ─── Helpers ─────────────────────────────────────────────────────

def _score_color(score: float) -> str:
    if score >= 65: return "#3fb950"
    if score >= 45: return "#d29922"
    return "#f85149"


def _fmt_val(v, decimals: int = 2) -> str:
    if v is None: return "—"
    try:
        return f"{float(v):.{decimals}f}"
    except Exception:
        return str(v)


def _val_class(v) -> str:
    try:
        f = float(v)
        if f > 0.05: return "val-pos"
        if f < -0.05: return "val-neg"
        return "val-neu"
    except Exception:
        return "val-neu"


def _pct_bar_html(pct: float, color: str) -> str:
    w = max(0, min(100, pct))
    return (
        f'<span class="pct-bar-wrap">'
        f'<span class="pct-bar" style="width:{w:.0f}%;background:{color}"></span>'
        f'</span>'
    )


# ─── Section renderers ───────────────────────────────────────────

def _render_header(today: date, n_series: int) -> str:
    return f"""
<div class="header">
  <div class="header-left">
    <h1><span class="flag">🇨🇳</span> China Macro Dashboard</h1>
    <div class="subtitle">Икономически преглед — седмичен briefing</div>
  </div>
  <div class="header-right">
    <div class="date">{today.strftime('%d %B %Y')}</div>
    <div class="series-count">{n_series}</div>
    <div class="series-label">активни серии</div>
  </div>
</div>
"""


def _render_composite(results: list[dict]) -> str:
    if not results:
        return ""

    weighted = sum(r["composite"] * MODULE_WEIGHTS.get(r["module"], 0) for r in results)
    total_weight = sum(MODULE_WEIGHTS.get(r["module"], 0) for r in results)
    overall = round(weighted / total_weight, 1) if total_weight else 50.0

    regime_label = "—"
    regime_color = "#8b949e"
    for threshold, label, color in MACRO_REGIMES:
        if overall >= threshold:
            regime_label = label
            regime_color = color
            break

    score_color = _score_color(overall)

    bars_html = ""
    for r in results:
        lens = r["module"]
        sc = r["composite"]
        lc = _score_color(sc)
        label = LENS_LABEL_BG.get(lens, lens)
        icon = LENS_ICON.get(lens, "")
        bars_html += f"""
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;">
          <span style="font-size:14px;width:20px">{icon}</span>
          <span style="color:#8b949e;font-size:12px;width:200px">{label}</span>
          <div style="flex:1;height:6px;background:#21262d;border-radius:3px;overflow:hidden">
            <div style="width:{sc:.0f}%;height:100%;background:{lc};border-radius:3px"></div>
          </div>
          <span style="font-size:13px;font-weight:700;color:{lc};min-width:35px;text-align:right">{sc:.1f}</span>
        </div>
        """

    return f"""
<div class="composite-card">
  <div class="score-circle" style="border-color:{score_color}">
    <span class="score-num" style="color:{score_color}">{overall:.1f}</span>
    <span class="score-label">SCORE</span>
  </div>
  <div class="composite-info" style="flex:1">
    <h2>Композитен Macro Score</h2>
    <span class="regime-badge" style="background:{regime_color}22;color:{regime_color};border:1px solid {regime_color}44">{regime_label}</span>
    <div class="description">Претеглен composite от 5 lens-а: растеж (30%), кредит (20%), инфлация (20%), имоти (15%), труд (15%).</div>
  </div>
  <div style="flex:1;padding-left:16px;border-left:1px solid #21262d">
    {bars_html}
  </div>
</div>
"""


def _render_lens_card(result: dict) -> str:
    lens = result["module"]
    label = LENS_LABEL_BG.get(lens, lens)
    icon = LENS_ICON.get(lens, "")
    score = result["composite"]
    regime = result["regime"]
    regime_color = result.get("regime_color", "#8b949e")
    score_color = _score_color(score)

    readings = result.get("key_readings", [])
    rows_html = ""
    for r in readings:
        val = _fmt_val(r.get("value"))
        vc = _val_class(r.get("value"))
        pct = r.get("percentile", 50)
        bar = _pct_bar_html(pct, score_color)
        date_str = r.get("date", "")
        if date_str:
            try:
                date_str = str(date_str)[:10]
            except Exception:
                pass
        lbl = r.get("label", "")[:40]
        rows_html += f"""
        <tr>
          <td style="color:#e6edf3;max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap"
              title="{r.get('label', '')}">{lbl}</td>
          <td class="{vc}" style="text-align:right;font-weight:600">{val}</td>
          <td style="text-align:center">{bar} <span style="color:#8b949e;font-size:11px">{pct:.0f}%</span></td>
          <td style="color:#8b949e;font-size:11px">{date_str}</td>
        </tr>
        """

    narrative_html = ""
    for hint in result.get("narrative", []):
        is_warn = hint.startswith("⚠")
        cls = "narrative-item warn" if is_warn else "narrative-item"
        narrative_html += f'<div class="{cls}">{hint}</div>'

    return f"""
<div class="lens-card">
  <div class="lens-card-header">
    <div><div class="lens-title">{label}</div></div>
    <span class="lens-icon">{icon}</span>
  </div>

  <div class="lens-score-row">
    <div class="lens-score-bar-wrap">
      <div class="lens-score-bar" style="width:{score:.0f}%;background:{score_color}"></div>
    </div>
    <span class="lens-score-num" style="color:{score_color}">{score:.1f}</span>
  </div>

  <span class="lens-regime" style="background:{regime_color}22;color:{regime_color};border:1px solid {regime_color}44">
    {regime}
  </span>

  <table class="readings-table">
    <thead>
      <tr>
        <th>Показател</th>
        <th style="text-align:right">Стойност</th>
        <th style="text-align:center">Percentile</th>
        <th>Дата</th>
      </tr>
    </thead>
    <tbody>{rows_html}</tbody>
  </table>

  {('<div class="narrative">' + narrative_html + '</div>') if narrative_html else ''}
</div>
"""


def _render_data_quality() -> str:
    notes = [
        "Официалната безработица (~5%) не включва ~300 млн. мигрантски работници. Реалната е значително по-висока.",
        "Младежката безработица (16-24 г.) беше спряна за публикуване от НБС юли–декември 2023 след рекорд 21.3%.",
        "GDP данните са годишни (World Bank). Месечни данни за Китай са ограничено достъпни в международни бази.",
        "PPI данни от IMF IFS са налични само до декември 2022. AkShare предоставя по-актуални данни от НБС.",
        "FDI данните показват срив до ~0.1% от GDP (2024) — исторически минимум. Геополитически de-risking.",
        "Цените на жилища (70 града) са от AkShare/НБС. Индексът е с база 100 — конвертиран към YoY %.",
        "GDP дефлаторът е отрицателен от 2023 — широка дефлация. Номиналният GDP расте по-бавно от реалния.",
    ]
    items = "".join(f'<div class="dq-item">{n}</div>' for n in notes)
    return f"""
<div class="dq-card">
  <h3>⚠ Бележки за качеството на данните</h3>
  {items}
</div>
"""


def _render_footer(today: date) -> str:
    return f"""
<div class="footer">
  <strong>China Macro Dashboard</strong> — автоматично генериран briefing.<br>
  Данни: World Bank Indicators API (годишни) · IMF IFS via DBnomics (месечни) · AkShare/НБС (месечни).<br>
  Генериран: {datetime.now().strftime('%Y-%m-%d %H:%M')} UTC · Серии: {len(SERIES_CATALOG)} · Lens-ове: 5.<br>
  <em>Забележка: Китайските официални данни са обект на ревизии и методологични промени. Интерпретирайте с внимание.</em>
</div>
"""


# ─── Main generator ──────────────────────────────────────────────

def generate_weekly_briefing(
    snapshot: dict,
    output_path: str,
    today: Optional[date] = None,
) -> None:
    """Генерира HTML weekly briefing за China macro dashboard."""
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

    n_series = len(snapshot)

    body = (
        _render_header(today, n_series)
        + _render_composite(results)
        + '<div class="lens-grid">'
        + "".join(_render_lens_card(r) for r in results)
        + "</div>"
        + _render_data_quality()
        + _render_footer(today)
    )

    html = f"""<!DOCTYPE html>
<html lang="bg">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>🇨🇳 China Macro Dashboard — {today.strftime('%Y-%m-%d')}</title>
  <style>{CSS}</style>
</head>
<body>
  <div class="container">
    {body}
  </div>
</body>
</html>"""

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
