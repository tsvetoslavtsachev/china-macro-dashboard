"""
export/deep_briefing.py
=======================
China **deep** briefing — подробен research-style анализ зад линк „За подробен
анализ →" от краткия landing (export/weekly_briefing.py).

Симетрия с US/EU deep (us-/eu-macro-dashboard/export/weekly_briefing.py): същата
dark China-family визуална рамка, същите research секции. НО headline-ът е
**China module composite/regime** (config.MODULE_WEIGHTS), НЕ US executive рамка
(labor/growth/inflation/liquidity + stagflation таксономия) — за кохерентност с
landing-а, `run.py --modules`, export_api (C3 manifest) и satellite.

Секции (BG):
  1. Header — флаг, дата, composite circle, KPI броячи, линк към краткия преглед
  2. Регимна диагноза — composite + режим + lens summary таблица (5 China лещи)
  3. Седмична промяна (WoW delta) — regime/cross-lens/breadth/non-consensus движения
  4. Cross-Lens Divergence — 3 China двойки (credit×real, monetary×inflation, external×domestic)
  5. Per-lens блокове × 5 — breadth таблица + вътрешни разминавания + аномалии в лещата
  6. Non-Consensus Highlights — триажирани tagged серии
  7. Top Anomalies — серии с |z|>2
  8. Предстои — честни placeholder-и (исторически аналози · falsifiers · journal)
  9. Бележки за качеството на данните
 10. Footer — методология

Отложено (Фази 3-4, данни-зависимо — НЕ фабрикуваме):
  - Historical analogs (China няма episode база/macro-vector spec)
  - Falsification criteria per China режим (guardrails е US-калибриран)
  - Journal (China няма journal/)

Self-contained HTML: inline CSS, без JS, без CDN, без images.
"""
from __future__ import annotations

import html
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from config import MODULE_WEIGHTS, MACRO_REGIMES
from catalog.series import SERIES_CATALOG
from core.display import change_kind, compute_change, fmt_change, fmt_value
from analysis.breadth import compute_lens_breadth
from analysis.divergence import (
    compute_intra_lens_divergence,
    compute_cross_lens_divergence,
)
from analysis.non_consensus import compute_non_consensus
from analysis.anomaly import compute_anomalies
from analysis.delta import (
    build_state_snapshot,
    compute_delta,
    save_state,
    load_latest_state,
    STATE_DIR_DEFAULT,
)


# ─── Labels (China таксономия) ───────────────────────────────────

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

# China MACRO_REGIMES BG label → english slug (симетрия с export_api / US/EU)
REGIME_KEY_MAP = {
    "ЕКСПАНЗИОНЕН": "expansionary",
    "ЗДРАВ": "healthy",
    "СМЕСЕН": "mixed",
    "ВЛОШАВАЩ СЕ": "deteriorating",
    "РЕЦЕСИОНЕН": "recessionary",
}

DIRECTION_LABEL_BG = {
    "expanding": "разширяване",
    "contracting": "свиване",
    "mixed": "смесено",
    "insufficient_data": "недостатъчно данни",
}

STATE_LABEL_BG = {
    "both_up": "↑↑ и двете нагоре",
    "both_down": "↓↓ и двете надолу",
    "a_up_b_down": "↑↓ A нагоре / B надолу",
    "a_down_b_up": "↓↑ A надолу / B нагоре",
    "transition": "⇄ преход",
    "insufficient_data": "недостатъчно данни",
}


# ─── China regime snapshot (заменя US executive за headline + WoW state) ──

@dataclass
class ChinaRegimeSnapshot:
    """Лек regime snapshot за China deep — захранва headline-а И WoW delta
    (analysis.delta.build_state_snapshot чете as_of/regime_label/regime_label_bg).

    Headline-ът е претегленият module composite (config.MODULE_WEIGHTS), НЕ
    US executive класификация. Така deep, landing, export_api и satellite са
    кохерентни (всички ползват config.MODULE_WEIGHTS)."""
    as_of: Optional[str]
    composite: float
    regime_label: str          # english slug (recessionary/...)
    regime_label_bg: str       # BG label (РЕЦЕСИОНЕН/...)
    regime_color: str
    lens_rows: list = field(default_factory=list)
    narrative_bg: str = ""


# ============================================================
# COMPOSITE / REGIME (config.MODULE_WEIGHTS — authoritative)
# ============================================================

def _overall_composite(results: list[dict]) -> float:
    weighted = sum(r["composite"] * MODULE_WEIGHTS.get(r["module"], 0) for r in results)
    total_w = sum(MODULE_WEIGHTS.get(r["module"], 0) for r in results)
    return round(weighted / total_w, 1) if total_w else 50.0


def _overall_regime(overall: float) -> tuple[str, str, str]:
    """(regime_label_bg, regime_key, color) по MACRO_REGIMES праговете."""
    for threshold, label, color in MACRO_REGIMES:
        if overall >= threshold:
            return label, REGIME_KEY_MAP.get(label, label), color
    return "—", "unknown", "#8b949e"


def _score_color(score: float) -> str:
    if score is None or score != score:
        return "#8b949e"
    if score >= 65:
        return "#3fb950"
    if score >= 45:
        return "#d29922"
    return "#f85149"


# ============================================================
# HELPERS
# ============================================================

def _fmt_breadth(v) -> str:
    if v is None:
        return "—"
    try:
        if v != v:  # NaN
            return "—"
    except TypeError:
        return "—"
    return f"{v:.0%}"


def _arrow(direction: str) -> str:
    return ("<span class='arrow up'>↑</span>" if direction == "up"
            else "<span class='arrow down'>↓</span>")


def _state_class(state: str) -> str:
    return {
        "both_up": "state-up-up",
        "both_down": "state-dn-dn",
        "a_up_b_down": "state-mixed",
        "a_down_b_up": "state-mixed",
        "transition": "state-trans",
        "insufficient_data": "state-ins",
    }.get(state, "state-trans")


def _direction_class(direction: str) -> str:
    return {
        "expanding": "dir-up",
        "contracting": "dir-dn",
        "mixed": "dir-mix",
        "insufficient_data": "dir-ins",
    }.get(direction, "dir-mix")


def _code(series_key: str) -> str:
    """Сериен код с native title tooltip (name_bg). Без dead-линкове — China
    няма explorer.html."""
    meta = SERIES_CATALOG.get(series_key, {})
    name = meta.get("name_bg") or series_key
    return f'<code class="series-code" title="{html.escape(name)}">{html.escape(series_key)}</code>'


def _delta_sign_class(delta_pp: float) -> str:
    if delta_pp > 0:
        return "up"
    if delta_pp < 0:
        return "down"
    return "flat"


def _fmt_pp(delta_pp: float) -> str:
    return f"{delta_pp * 100:+.1f}pp"


def _pick_as_of(lens_reports, cross_report, anomaly_report) -> Optional[str]:
    candidates = []
    for r in lens_reports.values():
        if r.as_of:
            candidates.append(r.as_of)
    if cross_report.as_of:
        candidates.append(cross_report.as_of)
    if anomaly_report.as_of:
        candidates.append(anomaly_report.as_of)
    return max(candidates) if candidates else None


# ============================================================
# SECTION RENDERERS
# ============================================================

def _render_header(today, as_of, snapshot, nc_report, anomaly_report, regime_snap) -> str:
    n_series = len(snapshot)
    n_high = sum(1 for r in nc_report.highlights if r.signal_strength == "high")
    n_medium = sum(1 for r in nc_report.highlights if r.signal_strength == "medium")
    n_anom = anomaly_report.total_flagged

    color = _score_color(regime_snap.composite)
    score_str = "—" if regime_snap.composite != regime_snap.composite else f"{regime_snap.composite:.1f}"

    return f"""
<header class="brief-header">
  <div class="brief-title">
    <a class="brief-backlink" href="index.html">← Кратък преглед</a>
    <h1><span class="flag">🇨🇳</span> China Macro — Подробен анализ</h1>
    <div class="brief-subtitle">Генериран {today.isoformat()} · Данни към {html.escape(as_of or '—')}</div>
  </div>
  <div class="brief-header-right">
    <div class="score-circle" style="border-color:{color}">
      <span class="score-num" style="color:{color}">{score_str}</span>
      <span class="score-label">SCORE</span>
    </div>
    <div class="brief-kpis">
      <div class="kpi"><div class="kpi-n">{n_series}</div><div class="kpi-l">серии</div></div>
      <div class="kpi"><div class="kpi-n">{n_anom}</div><div class="kpi-l">аномалии |z|>2</div></div>
      <div class="kpi"><div class="kpi-n">{n_high}</div><div class="kpi-l">non-consensus HIGH</div></div>
      <div class="kpi"><div class="kpi-n">{n_medium}</div><div class="kpi-l">non-consensus MEDIUM</div></div>
    </div>
  </div>
</header>
"""


def _render_regime_headline(regime_snap, results, anomaly_report) -> str:
    """Регимна диагноза — China composite/regime + lens summary таблица.

    Заменя US executive: headline-ът е претегленият module composite, лещите
    показват module score + module regime (по-смислено за China от breadth-only)."""
    color = regime_snap.regime_color
    regime_bg = html.escape(regime_snap.regime_label_bg)

    by_module = {r["module"]: r for r in results}

    rows_html = []
    for lens in LENS_ORDER:
        r = by_module.get(lens)
        if r is None:
            continue
        label = LENS_LABEL_BG.get(lens, lens)
        icon = LENS_ICON.get(lens, "")
        score = r.get("composite")
        score_str = f"{score:.1f}" if isinstance(score, (int, float)) else "—"
        sc_color = _score_color(score if isinstance(score, (int, float)) else float("nan"))
        mod_regime = html.escape(str(r.get("regime", "—")))
        lens_anoms = anomaly_report.by_lens.get(lens, [])
        ne_count = sum(1 for a in lens_anoms if a.is_new_extreme)
        ne_badge = f"<span class='ne-inline'>{ne_count} NEW</span>" if ne_count else ""
        rows_html.append(f"""
<tr>
  <td class="pg-name">{icon} {html.escape(label)}</td>
  <td class="num" style="color:{sc_color};font-weight:600">{score_str}</td>
  <td>{mod_regime}</td>
  <td class="num">{len(lens_anoms)} {ne_badge}</td>
</tr>
""")

    return f"""
<section class="brief-section exec-section">
  <h2>Регимна диагноза</h2>
  <div class="exec-headline">
    <div class="regime-badge" style="background:{color}22;color:{color};border-color:{color}66">
      <div class="regime-label">Композитен режим</div>
      <div class="regime-val">{regime_bg}</div>
      <div class="regime-driver">composite {regime_snap.composite:.1f}/100</div>
    </div>
    <div class="exec-narrative">{html.escape(regime_snap.narrative_bg)}</div>
  </div>
  <div class="exec-grid-single">
    <table class="regime-table">
      <thead><tr>
        <th>Тема</th><th>Score</th><th>Режим</th><th>Аномалии</th>
      </tr></thead>
      <tbody>{"".join(rows_html)}</tbody>
    </table>
  </div>
  <p class="exec-weights-note muted">
    Композитът е претеглен по China-калибрираните тегла: растеж 30% · кредит 25% ·
    имоти 20% · инфлация 15% · труд 10%. Идентичен с <code>run.py --modules</code>,
    <code>export_api</code> (manifest) и satellite.
  </p>
</section>
"""


def _render_delta(delta) -> str:
    if delta.prev_generated_on is None:
        return """
<section class="brief-section delta-section">
  <h2>Седмична промяна</h2>
  <p class="muted">Няма референтен snapshot — това е първият генериран подробен briefing (или няма предишно състояние в <code>data/state/</code>).</p>
</section>
"""
    if not delta.has_content:
        return f"""
<section class="brief-section delta-section">
  <h2>Седмична промяна <span class="delta-since">(спрямо {html.escape(delta.prev_generated_on)})</span></h2>
  <p class="muted">Без съществени промени от предишния подробен briefing.</p>
</section>
"""

    parts: list[str] = []

    if delta.regime_change:
        from_lbl, to_lbl = delta.regime_change
        parts.append(f"""
<div class="delta-regime">
  <span class="delta-label">Смяна на режим:</span>
  <span class="delta-arrow">{html.escape(from_lbl)} → <strong>{html.escape(to_lbl)}</strong></span>
</div>
""")

    if delta.cross_lens_changes:
        from catalog.cross_lens_pairs import CROSS_LENS_PAIRS
        pair_lookup = {p["id"]: p for p in CROSS_LENS_PAIRS}
        rows = []
        for c in delta.cross_lens_changes:
            pair_meta = pair_lookup.get(c.pair_id, {})
            pair_name = pair_meta.get("name_bg", c.pair_id)
            from_lbl = STATE_LABEL_BG.get(c.from_state, c.from_state)
            to_lbl = STATE_LABEL_BG.get(c.to_state, c.to_state)
            new_interp = (pair_meta.get("interpretations") or {}).get(c.to_state, "")
            interp_html = (
                f" <em class='delta-interp'>— {html.escape(new_interp)}</em>"
                if new_interp and new_interp != "—" else ""
            )
            rows.append(
                f"<li><strong>{html.escape(pair_name)}</strong>: "
                f"<span class='state-from'>{html.escape(from_lbl)}</span> → "
                f"<strong class='state-to'>{html.escape(to_lbl)}</strong>{interp_html}</li>"
            )
        parts.append(
            f"<div class='delta-block'><h4>Cross-lens преходи</h4><ul>{''.join(rows)}</ul></div>"
        )

    if delta.breadth_moves:
        rows = "".join(
            f"<li><strong>{html.escape(m.lens)}/{html.escape(m.peer_group)}</strong>: "
            f"{m.from_value:.0%} → {m.to_value:.0%} "
            f"<span class='delta-pp {_delta_sign_class(m.delta_pp)}'>{_fmt_pp(m.delta_pp)}</span></li>"
            for m in delta.breadth_moves[:8]
        )
        more = (f"<div class='muted'>…+{len(delta.breadth_moves) - 8} още</div>"
                if len(delta.breadth_moves) > 8 else "")
        parts.append(f"<div class='delta-block'><h4>Breadth движения (≥10pp)</h4><ul>{rows}</ul>{more}</div>")

    if delta.new_high_nc or delta.vanished_high_nc:
        subs = []
        if delta.new_high_nc:
            keys = " ".join(_code(k) for k in delta.new_high_nc)
            subs.append(f"<div><span class='delta-tag new'>NEW HIGH</span> {keys}</div>")
        if delta.vanished_high_nc:
            keys = " ".join(f"<code class='ref-vanished'>{html.escape(k)}</code>" for k in delta.vanished_high_nc)
            subs.append(f"<div><span class='delta-tag gone'>GONE</span> {keys}</div>")
        parts.append(f"<div class='delta-block'><h4>Non-consensus HIGH</h4>{''.join(subs)}</div>")

    if delta.new_extremes_surfaced or delta.new_extremes_resolved:
        subs = []
        if delta.new_extremes_surfaced:
            keys = " ".join(_code(k) for k in delta.new_extremes_surfaced)
            subs.append(f"<div><span class='delta-tag new'>NEW екстремум</span> {keys}</div>")
        if delta.new_extremes_resolved:
            keys = " ".join(f"<code class='ref-vanished'>{html.escape(k)}</code>" for k in delta.new_extremes_resolved)
            subs.append(f"<div><span class='delta-tag gone'>RESOLVED</span> {keys}</div>")
        parts.append(f"<div class='delta-block'><h4>Екстремуми</h4>{''.join(subs)}</div>")

    return f"""
<section class="brief-section delta-section">
  <h2>Седмична промяна <span class="delta-since">(спрямо {html.escape(delta.prev_generated_on)})</span></h2>
  {"".join(parts)}
</section>
"""


def _render_cross_lens(cross_report) -> str:
    pair_rows = []
    for p in cross_report.pairs:
        state_cls = _state_class(p.state)
        state_label = STATE_LABEL_BG.get(p.state, p.state)
        pair_rows.append(f"""
<div class="pair-card">
  <div class="pair-head">
    <span class="pair-state {state_cls}">{html.escape(state_label)}</span>
    <h3>{html.escape(p.name_bg)}</h3>
  </div>
  <div class="pair-question">{html.escape(p.question_bg)}</div>
  <div class="pair-grid">
    <div class="pair-slot">
      <div class="pair-slot-label">A · {html.escape(p.slot_a_label)}</div>
      <div class="pair-slot-val">{_fmt_breadth(p.breadth_a)}</div>
      <div class="pair-slot-n">n={p.n_a_available}</div>
    </div>
    <div class="pair-slot">
      <div class="pair-slot-label">B · {html.escape(p.slot_b_label)}</div>
      <div class="pair-slot-val">{_fmt_breadth(p.breadth_b)}</div>
      <div class="pair-slot-n">n={p.n_b_available}</div>
    </div>
  </div>
  <div class="pair-interp">{html.escape(p.interpretation)}</div>
</div>
""")
    return f"""
<section class="brief-section">
  <h2>Cross-Lens Divergence</h2>
  <div class="pair-wrap">{"".join(pair_rows)}</div>
</section>
"""


def _render_lens_block(lens, breadth_report, intra_report, anomaly_report) -> str:
    label = LENS_LABEL_BG.get(lens, lens)
    icon = LENS_ICON.get(lens, "")

    breadth_rows = []
    for pg in breadth_report.peer_groups:
        bp_str = _fmt_breadth(pg.breadth_positive)
        be_str = _fmt_breadth(pg.breadth_extreme)
        dir_cls = _direction_class(pg.direction)
        dir_label = DIRECTION_LABEL_BG.get(pg.direction, pg.direction)
        extreme_marks = " ".join(_code(k) for k in pg.extreme_members[:4])
        breadth_rows.append(f"""
<tr>
  <td class="pg-name">{html.escape(pg.name)}</td>
  <td class="num">{bp_str}</td>
  <td class="num">{be_str}</td>
  <td class="num">{pg.n_available}/{pg.n_members}</td>
  <td><span class="dir-badge {dir_cls}">{html.escape(dir_label)}</span></td>
  <td class="extremes">{extreme_marks}</td>
</tr>
""")
    breadth_table = f"""
<table class="breadth-table">
  <thead><tr>
    <th>Peer group</th><th>breadth ↑</th><th>breadth |z|>2</th>
    <th>данни</th><th>посока</th><th>екстремни членове</th>
  </tr></thead>
  <tbody>{"".join(breadth_rows)}</tbody>
</table>
"""

    if intra_report.divergences:
        div_rows = "".join(
            f"<li><strong>{html.escape(d.group_a)}</strong> ({d.breadth_a:.0%}) "
            f"vs <strong>{html.escape(d.group_b)}</strong> ({d.breadth_b:.0%}) "
            f"<span class='diff'>Δ {d.diff:+.0%}</span></li>"
            for d in intra_report.divergences[:5]
        )
        div_block = f"<div class='intra-div'><h4>Вътрешни разминавания</h4><ul>{div_rows}</ul></div>"
    else:
        div_block = "<div class='intra-div muted'>Няма notable вътрешни разминавания.</div>"

    lens_anoms = anomaly_report.by_lens.get(lens, [])[:5]
    if lens_anoms:
        anom_rows = "".join(
            f"<li>{_arrow(a.direction)} {_code(a.series_key)} "
            f"<span class='z'>z={a.z_score:+.2f}</span>"
            f"{'  <span class=ne>NEW ' + a.new_extreme_direction.upper() + '</span>' if a.is_new_extreme and a.new_extreme_direction else ''}"
            f"<span class='pg'>· {html.escape(a.peer_group)}</span></li>"
            for a in lens_anoms
        )
        anom_block = f"<div class='lens-anoms'><h4>Аномалии в лещата</h4><ol>{anom_rows}</ol></div>"
    else:
        anom_block = "<div class='lens-anoms muted'>Няма аномалии в тази леща.</div>"

    return f"""
<section class="brief-section lens-block" data-lens="{html.escape(lens)}">
  <h2>{icon} {html.escape(label)}</h2>
  {breadth_table}
  <div class="lens-grid">
    {div_block}
    {anom_block}
  </div>
</section>
"""


def _render_non_consensus(nc_report) -> str:
    if not nc_report.highlights:
        return """
<section class="brief-section">
  <h2>Non-Consensus Highlights</h2>
  <p class="muted">Нито една tagged серия не е с high/medium сигнал в момента.</p>
</section>
"""
    rows = []
    for r in nc_report.highlights:
        tag_spans = " ".join(
            f"<span class='tag tag-{html.escape(t)}'>{html.escape(t)}</span>" for t in r.tags
        )
        z_str = f"{r.z_score:+.2f}" if r.z_score == r.z_score else "—"
        peer_str = f"{r.peer_breadth:.0%}" if r.peer_breadth == r.peer_breadth else "—"
        rows.append(f"""
<tr class="sig-{html.escape(r.signal_strength)}">
  <td><span class="sig-badge sig-{html.escape(r.signal_strength)}">{html.escape(r.signal_strength.upper())}</span></td>
  <td>{_code(r.series_key)}</td>
  <td>{html.escape(r.series_name_bg)}</td>
  <td class="num">{z_str}</td>
  <td class="num">{peer_str}</td>
  <td>{html.escape(r.peer_direction)}</td>
  <td>{'✓' if r.deviates_from_peers else ''}</td>
  <td>{tag_spans}</td>
</tr>
""")
    return f"""
<section class="brief-section">
  <h2>Non-Consensus Highlights</h2>
  <table class="nc-table">
    <thead><tr>
      <th>сила</th><th>серия</th><th>име</th><th>z</th><th>peer breadth</th>
      <th>peer посока</th><th>дев.?</th><th>тагове</th>
    </tr></thead>
    <tbody>{"".join(rows)}</tbody>
  </table>
</section>
"""


def _render_anomalies_feed(anomaly_report, snapshot) -> str:
    if not anomaly_report.top:
        return """
<section class="brief-section">
  <h2>Top Anomalies</h2>
  <p class="muted">Няма серии с |z|>2 в момента.</p>
</section>
"""
    rows = []
    for i, a in enumerate(anomaly_report.top, 1):
        new_ext = (f"<span class='ne'>NEW {a.new_extreme_direction.upper()}</span>"
                   if a.is_new_extreme and a.new_extreme_direction else "")
        meta = SERIES_CATALOG.get(a.series_key, {})
        kind = change_kind(a.series_key, meta)
        value_cell = fmt_value(a.last_value, digits=2 if kind == "absolute" else 3)

        delta_cell = "—"
        if snapshot is not None:
            s = snapshot.get(a.series_key)
            if s is not None and not s.empty and len(s.dropna()) >= 2:
                try:
                    delta_series = compute_change(s, kind, periods=1)
                    delta_cell = fmt_change(delta_series.iloc[-1], kind)
                except Exception:
                    pass

        rows.append(f"""
<tr>
  <td class="rank">{i}</td>
  <td>{_arrow(a.direction)}</td>
  <td>{_code(a.series_key)}</td>
  <td>{html.escape(a.series_name_bg)}</td>
  <td class="num">{value_cell}</td>
  <td class="num">{delta_cell}</td>
  <td class="num">{a.z_score:+.2f}</td>
  <td>{new_ext}</td>
  <td>{" / ".join(html.escape(l) for l in a.lens)}</td>
  <td>{html.escape(a.peer_group)}</td>
</tr>
""")
    return f"""
<section class="brief-section">
  <h2>Top Anomalies ({len(anomaly_report.top)}/{anomaly_report.total_flagged})</h2>
  <table class="anom-table">
    <thead><tr>
      <th>#</th><th></th><th>серия</th><th>име</th>
      <th>стойност</th><th>Δ</th><th>z</th>
      <th>екстремум</th><th>lens</th><th>peer group</th>
    </tr></thead>
    <tbody>{"".join(rows)}</tbody>
  </table>
</section>
"""


def _render_deferred() -> str:
    """Честни placeholder-и за данни-зависимите секции (Фази 3-4). НЕ фабрикуваме
    празни US-копирани секции (falsifiers с US режими, analogs с None)."""
    items = [
        ("Исторически аналози",
         "Съпоставка на текущото състояние с минали епизоди (macro-vector + episode "
         "матрица). Изисква China-специфична historical база — китайската история е "
         "по-къса и по-рядко наблюдавана, затова този слой се изгражда отделно."),
        ("Falsification criteria",
         "Какво конкретно би обезсилило текущата регимна диагноза, per China режим "
         "(recessionary/deteriorating/mixed/healthy/expansionary). Изисква авторски "
         "прагове, калибрирани за китайските серии — не наследяваме US праговете "
         "(Sahm rule, ICSA, T10Y2Y, HY OAS), които China няма."),
        ("Свързани бележки (journal)",
         "Връзки към аналитичен journal по теми и режими. China dashboard все още "
         "няма journal слой."),
    ]
    cards = "".join(
        f"""
<div class="soon-card">
  <div class="soon-head"><span class="soon-badge">предстои</span><h3>{html.escape(t)}</h3></div>
  <p>{html.escape(desc)}</p>
</div>
""" for t, desc in items
    )
    return f"""
<section class="brief-section">
  <h2>Предстои</h2>
  <div class="soon-wrap">{cards}</div>
</section>
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
        "Cross-Lens Divergence, breadth и Top Anomalies стъпват предимно на месечни серии (PMI, лихви, търговия, кредит). Годишните серии (БВП, безработица) се обновяват веднъж годишно — посоката им се движи по-бавно.",
        "Z-score за аномалиите е изчислен върху цялата налична история на серията (full-sample). |z|>2 = екстремно четене спрямо собствената история. peer_group с <2 налични серии не дава breadth.",
    ]
    items = "".join(f'<div class="dq-item">{html.escape(n)}</div>' for n in notes)
    return f"""
<section class="brief-section">
  <div class="dq-card">
    <h3>⚠ Бележки за качеството на данните</h3>
    {items}
  </div>
</section>
"""


def _render_footer(as_of, today) -> str:
    return f"""
<footer class="brief-footer">
  <details class="methodology" open>
    <summary><strong>Методология — как да четеш този анализ</strong></summary>

    <h4>Композитен режим</h4>
    <p class="muted">
      Претеглен composite от 5-те лещи по China-калибрираните тегла (растеж 30% ·
      кредит 25% · имоти 20% · инфлация 15% · труд 10%). Режимът се определя от
      праговете в <code>config.MACRO_REGIMES</code>. Идентичен с
      <code>run.py --modules</code> и AI слоя (<code>manifest.json</code>).
    </p>

    <h4>Breadth (% положителна момент)</h4>
    <p class="muted">
      Процент от сериите в peer group с положителен 1-периоден momentum.
      <code>breadth &gt; 60%</code> → „разширяване" · <code>&lt; 40%</code> →
      „свиване" · между → „смесено" · &lt;2 серии с данни → „недостатъчно данни".
      За малки peer groups (2-3 серии) 1 flip = голяма pp промяна — не е грешка.
    </p>

    <h4>Z-score &amp; аномалии</h4>
    <p class="muted">
      Стандартизирана отдалеченост от историческата средна (full-sample).
      <code>|z|&gt;2</code> — флаг за екстремна стойност. „NEW" екстремум = нов
      max/min за lookback прозореца.
    </p>

    <h4>Cross-Lens Divergence — China двойки</h4>
    <p class="muted">
      Три икономически тези, специфични за Китай: <strong>Кредит × Реален сектор</strong>
      (debt-deflation / liquidity trap) · <strong>Монетарно × Инфлация</strong>
      (policy trap, Japan-style) · <strong>Външно × Вътрешно търсене</strong>
      (export-dependence / rebalancing). Всяка съпоставя breadth между два slot-а.
    </p>

    <h4>Седмична промяна (WoW)</h4>
    <p class="muted">
      Сравнение с подробен briefing snapshot от <strong>≥5 дни назад</strong>.
      Snapshot-овете се пазят в <code>data/state/briefing_YYYY-MM-DD.json</code>.
    </p>
  </details>

  <p class="muted brief-meta">
    Всички изчисления са детерминистични — няма LLM нарация. Китайските официални
    данни са обект на ревизии и методологични промени; интерпретирайте с внимание.
    As_of: {html.escape(as_of or '—')} · Генериран: {today.isoformat()} · Серии: {len(SERIES_CATALOG)} · Лещи: 5.
  </p>
</footer>
"""


# ============================================================
# PUBLIC API
# ============================================================

def generate_deep_briefing(
    snapshot: dict[str, pd.Series],
    output_path: str,
    top_anomalies_n: int = 10,
    today: Optional[date] = None,
    state_dir: Optional[str] = STATE_DIR_DEFAULT,
    persist_state: bool = True,
) -> str:
    """Генерира China deep briefing HTML; връща абсолютния path.

    Args:
        snapshot: {series_key → pd.Series}.
        output_path: path/име за HTML файла.
        top_anomalies_n: брой top anomalies.
        today: override за тестове.
        state_dir: директория за WoW state snapshots. None → WoW delta се пропуска.
        persist_state: дали да записва текущия state за бъдещо сравнение.
    """
    import importlib

    if today is None:
        today = date.today()

    # ── Модули (5-те лещи) ──
    results = []
    for lens in LENS_ORDER:
        try:
            mod = importlib.import_module(f"modules.{lens}")
            results.append(mod.run(snapshot))
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Module {lens} failed: {e}")

    overall = _overall_composite(results)
    regime_bg, regime_key, regime_color = _overall_regime(overall)

    # ── Аналитични слоеве ──
    lens_reports = {lens: compute_lens_breadth(lens, snapshot) for lens in LENS_ORDER}
    intra_reports = {lens: compute_intra_lens_divergence(lens, snapshot) for lens in LENS_ORDER}
    cross_report = compute_cross_lens_divergence(snapshot)
    nc_report = compute_non_consensus(snapshot)
    anomaly_report = compute_anomalies(snapshot, z_threshold=2.0, top_n=top_anomalies_n)

    as_of = _pick_as_of(lens_reports, cross_report, anomaly_report)

    # ── Регимен narrative (детерминистичен, фактологичен) ──
    narrative = _build_narrative(overall, regime_bg, results, anomaly_report, cross_report)

    regime_snap = ChinaRegimeSnapshot(
        as_of=as_of,
        composite=overall,
        regime_label=regime_key,
        regime_label_bg=regime_bg,
        regime_color=regime_color,
        narrative_bg=narrative,
    )

    # ── WoW delta ──
    current_state = build_state_snapshot(
        regime_snap, cross_report, lens_reports, anomaly_report, nc_report,
        generated_on=today,
    )
    prev_state = None
    if state_dir is not None:
        try:
            prev_state = load_latest_state(state_dir=state_dir, before=today, min_age_days=5)
        except Exception:
            prev_state = None
    delta = compute_delta(current_state, prev_state)

    # ── Render ──
    sections = [
        _render_header(today, as_of, snapshot, nc_report, anomaly_report, regime_snap),
        _render_regime_headline(regime_snap, results, anomaly_report),
        _render_delta(delta),
        _render_cross_lens(cross_report),
    ]
    for lens in LENS_ORDER:
        sections.append(_render_lens_block(
            lens, lens_reports[lens], intra_reports[lens], anomaly_report,
        ))
    sections.append(_render_non_consensus(nc_report))
    sections.append(_render_anomalies_feed(anomaly_report, snapshot))
    sections.append(_render_deferred())
    sections.append(_render_data_quality())
    sections.append(_render_footer(as_of, today))

    body = "\n".join(sections)
    full_html = _skeleton(title=f"China Macro — Подробен анализ {today.isoformat()}", body=body)

    out = Path(output_path).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(full_html, encoding="utf-8")

    if persist_state and state_dir is not None:
        try:
            save_state(current_state, state_dir=state_dir)
        except Exception:
            pass

    return str(out)


def _build_narrative(overall, regime_bg, results, anomaly_report, cross_report) -> str:
    """Детерминистичен factual narrative — без invented causal claims."""
    parts = [f"Претеглен композитен macro score {overall:.1f}/100 → режим „{regime_bg}“."]

    scored = [r for r in results if isinstance(r.get("composite"), (int, float))]
    if scored:
        weakest = min(scored, key=lambda r: r["composite"])
        strongest = max(scored, key=lambda r: r["composite"])
        wl = LENS_LABEL_BG.get(weakest["module"], weakest["module"])
        sl = LENS_LABEL_BG.get(strongest["module"], strongest["module"])
        parts.append(
            f"Най-слаба тема: {wl} ({weakest['composite']:.1f} — {weakest.get('regime', '')}); "
            f"най-силна: {sl} ({strongest['composite']:.1f})."
        )

    active = [p for p in cross_report.pairs if p.state not in ("transition", "insufficient_data")]
    if active:
        labels = "; ".join(f"{p.name_bg} → {STATE_LABEL_BG.get(p.state, p.state)}" for p in active[:3])
        parts.append(f"Активни cross-lens сигнали: {labels}.")
    else:
        parts.append("Cross-lens двойките са в преход — няма ясно изразен сигнал.")

    if anomaly_report.total_flagged:
        parts.append(f"{anomaly_report.total_flagged} серии с |z|>2 (екстремни четения).")

    return " ".join(parts)


# ============================================================
# HTML SKELETON + CSS
# ============================================================

def _skeleton(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="bg">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{html.escape(title)}</title>
<style>{_CSS}</style>
</head>
<body>
<main class="brief-main">
{body}
</main>
</body>
</html>"""


_CSS = """
* { box-sizing: border-box; }
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
  margin: 0; padding: 0; background: #0d1117; color: #e6edf3; line-height: 1.5;
}
.brief-main { max-width: 1100px; margin: 0 auto; padding: 28px 24px 60px; }

/* Header */
.brief-header {
  display: flex; justify-content: space-between; align-items: center;
  background: linear-gradient(135deg, #1a1f2e 0%, #161b27 100%);
  border: 1px solid #30363d; border-radius: 12px;
  padding: 24px 28px; margin-bottom: 24px; flex-wrap: wrap; gap: 20px;
}
.brief-backlink { color: #58a6ff; font-size: 12.5px; text-decoration: none; display: inline-block; margin-bottom: 8px; }
.brief-backlink:hover { text-decoration: underline; }
.brief-title h1 { margin: 0; font-size: 26px; font-weight: 700; color: #f0f6fc; }
.brief-title h1 .flag { font-size: 30px; margin-right: 8px; }
.brief-subtitle { color: #8b949e; font-size: 13px; margin-top: 4px; }
.brief-header-right { display: flex; align-items: center; gap: 20px; flex-wrap: wrap; }
.score-circle {
  width: 84px; height: 84px; border-radius: 50%;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  flex-shrink: 0; border: 3px solid;
}
.score-circle .score-num { font-size: 26px; font-weight: 800; line-height: 1; }
.score-circle .score-label { font-size: 10px; color: #8b949e; margin-top: 3px; }
.brief-kpis { display: flex; gap: 14px; flex-wrap: wrap; }
.kpi { background: #0d1117; border: 1px solid #30363d; border-radius: 6px; padding: 8px 14px; text-align: center; min-width: 84px; }
.kpi-n { font-size: 22px; font-weight: 600; color: #58a6ff; }
.kpi-l { font-size: 10.5px; color: #8b949e; text-transform: uppercase; letter-spacing: 0.5px; }

/* Sections */
.brief-section { margin-bottom: 36px; }
.brief-section h2 {
  font-size: 17px; text-transform: uppercase; letter-spacing: 1px;
  color: #f0f6fc; border-bottom: 1px solid #30363d; padding-bottom: 6px; margin: 0 0 14px;
}
.brief-section h4 { font-size: 12.5px; text-transform: uppercase; color: #8b949e; letter-spacing: 0.7px; margin: 0 0 8px; }
.muted { color: #8b949e; font-style: italic; font-size: 13px; }

/* Regime headline (China composite) */
.exec-section { background: #161b27; border: 1px solid #30363d; border-radius: 8px; padding: 18px 20px; }
.exec-section h2 { margin-top: 0; }
.exec-headline { display: grid; grid-template-columns: minmax(180px, 260px) 1fr; gap: 18px; align-items: start; margin-bottom: 14px; }
.regime-badge { padding: 12px 14px; border-radius: 6px; text-align: center; border: 1px solid; }
.regime-badge .regime-label { font-size: 10.5px; text-transform: uppercase; letter-spacing: 0.6px; opacity: 0.75; }
.regime-badge .regime-val { font-size: 18px; font-weight: 700; margin: 4px 0 6px; line-height: 1.25; }
.regime-badge .regime-driver { font-size: 10.5px; opacity: 0.7; font-family: monospace; }
.exec-narrative { background: #0d1117; border-left: 3px solid #30363d; padding: 10px 14px; font-size: 14px; line-height: 1.55; color: #c9d1d9; }
.exec-grid-single { margin-top: 4px; }
.exec-weights-note { margin: 12px 0 0; font-size: 11.5px; }
.regime-table { width: 100%; border-collapse: collapse; font-size: 13px; background: #161b27; }
.regime-table th, .regime-table td { padding: 7px 10px; text-align: left; border-bottom: 1px solid #21262d; }
.regime-table th { background: #21262d; color: #8b949e; font-weight: 500; font-size: 11.5px; text-transform: uppercase; letter-spacing: 0.5px; }
.ne-inline { display: inline-block; background: #d2992222; color: #d29922; font-size: 10px; padding: 1px 5px; border-radius: 3px; font-weight: 600; margin-left: 4px; font-family: monospace; }
@media (max-width: 760px) { .exec-headline { grid-template-columns: 1fr; } }

/* Week-over-Week delta */
.delta-section { background: #161b27; border: 1px solid #30363d; border-radius: 8px; padding: 14px 18px; }
.delta-section h2 { margin-top: 0; }
.delta-section .delta-since { font-size: 12px; color: #8b949e; text-transform: none; letter-spacing: 0; font-weight: normal; }
.delta-regime { background: #d2992222; border: 1px solid #d2992244; color: #d29922; padding: 10px 14px; border-radius: 6px; margin-bottom: 12px; font-size: 14px; }
.delta-regime .delta-label { font-weight: 600; margin-right: 8px; }
.delta-regime .delta-arrow { font-family: monospace; }
.delta-block { margin: 10px 0; }
.delta-block ul { margin: 0; padding-left: 18px; font-size: 13px; }
.delta-block li { margin-bottom: 3px; }
.delta-interp { color: #8b949e; }
.state-from { color: #8b949e; font-family: monospace; }
.state-to { font-family: monospace; color: #e6edf3; }
.delta-pp { font-family: monospace; margin-left: 6px; font-weight: 600; padding: 0 4px; border-radius: 3px; }
.delta-pp.up { background: #3fb95022; color: #3fb950; }
.delta-pp.down { background: #f8514922; color: #f85149; }
.delta-pp.flat { color: #8b949e; }
.delta-tag { display: inline-block; font-size: 10.5px; padding: 1px 7px; border-radius: 3px; font-weight: 600; margin-right: 4px; }
.delta-tag.new { background: #58a6ff22; color: #58a6ff; }
.delta-tag.gone { background: #8b949e22; color: #8b949e; }
.ref-vanished { background: #21262d; color: #8b949e; text-decoration: line-through; font-family: monospace; font-size: 12.5px; padding: 1px 5px; border-radius: 3px; }

/* Cross-lens pairs */
.pair-wrap { display: grid; grid-template-columns: repeat(auto-fit, minmax(330px, 1fr)); gap: 14px; }
.pair-card { background: #161b27; border: 1px solid #30363d; border-radius: 8px; padding: 14px 16px; }
.pair-head { display: flex; align-items: center; gap: 10px; margin-bottom: 6px; }
.pair-head h3 { margin: 0; font-size: 14.5px; font-weight: 600; color: #f0f6fc; }
.pair-state { font-size: 10.5px; padding: 3px 8px; border-radius: 4px; font-weight: 600; white-space: nowrap; }
.state-up-up { background: #3fb95022; color: #3fb950; }
.state-dn-dn { background: #f8514922; color: #f85149; }
.state-mixed { background: #d2992222; color: #d29922; }
.state-trans { background: #8b949e22; color: #8b949e; }
.state-ins   { background: #8b949e22; color: #6e7681; }
.pair-question { font-size: 12.5px; color: #8b949e; font-style: italic; margin-bottom: 10px; }
.pair-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 10px; }
.pair-slot { background: #0d1117; border: 1px solid #21262d; border-radius: 5px; padding: 8px 10px; }
.pair-slot-label { font-size: 11px; color: #8b949e; text-transform: uppercase; letter-spacing: 0.5px; }
.pair-slot-val { font-family: 'Consolas', 'Monaco', monospace; font-size: 18px; font-weight: 600; margin-top: 4px; color: #e6edf3; }
.pair-slot-n { font-size: 10.5px; color: #8b949e; }
.pair-interp { background: #0d1117; border-left: 3px solid #30363d; padding: 8px 12px; font-size: 13px; color: #c9d1d9; }

/* Lens blocks + tables */
.lens-block h2 { color: #f0f6fc; }
.breadth-table, .nc-table, .anom-table { width: 100%; border-collapse: collapse; background: #161b27; border: 1px solid #30363d; font-size: 13px; margin-bottom: 14px; }
.breadth-table th, .breadth-table td, .nc-table th, .nc-table td, .anom-table th, .anom-table td { padding: 7px 10px; text-align: left; border-bottom: 1px solid #21262d; vertical-align: middle; }
.breadth-table th, .nc-table th, .anom-table th { background: #21262d; color: #8b949e; font-weight: 500; font-size: 11.5px; text-transform: uppercase; letter-spacing: 0.5px; }
.num { font-family: 'Consolas', 'Monaco', monospace; text-align: right; }
.pg-name { font-weight: 500; }
.dir-badge { font-size: 11px; padding: 2px 8px; border-radius: 3px; font-weight: 500; }
.dir-up  { background: #3fb95022; color: #3fb950; }
.dir-dn  { background: #f8514922; color: #f85149; }
.dir-mix { background: #d2992222; color: #d29922; }
.dir-ins { background: #8b949e22; color: #8b949e; }
.extremes { max-width: 260px; }
.lens-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.lens-grid > div { background: #161b27; border: 1px solid #30363d; border-radius: 6px; padding: 12px 14px; }
.lens-grid ul, .lens-grid ol { margin: 0; padding-left: 18px; }
.lens-grid li { font-size: 13px; margin-bottom: 4px; }
.diff { color: #8b949e; font-family: monospace; margin-left: 6px; }
@media (max-width: 760px) { .lens-grid { grid-template-columns: 1fr; } }

/* Non-consensus */
.sig-badge { display: inline-block; font-size: 10.5px; padding: 2px 7px; border-radius: 3px; font-weight: 600; }
.sig-high   { background: #f8514922; color: #f85149; }
.sig-medium { background: #d2992222; color: #d29922; }
.sig-low    { background: #8b949e22; color: #8b949e; }
tr.sig-high { background: #f8514911; }
.tag { display: inline-block; font-size: 10.5px; padding: 1px 6px; border-radius: 3px; margin-right: 3px; background: #58a6ff22; color: #58a6ff; font-family: monospace; }
.tag-structural { background: #3fb95022; color: #3fb950; }
.tag-data_quality_risk { background: #d2992222; color: #d29922; }

/* Anomalies */
.rank { color: #8b949e; font-family: monospace; }
.arrow { font-family: monospace; font-weight: 600; }
.arrow.up { color: #3fb950; }
.arrow.down { color: #f85149; }
.ne { display: inline-block; background: #d2992222; color: #d29922; font-size: 10.5px; padding: 1px 6px; border-radius: 3px; font-weight: 600; margin-left: 4px; font-family: monospace; }
.z { font-family: monospace; color: #8b949e; margin: 0 6px; }
.pg { color: #8b949e; font-size: 12px; margin-left: 4px; }
.series-code { font-family: 'Consolas', 'Monaco', monospace; background: #21262d; color: #c9d1d9; padding: 1px 5px; border-radius: 3px; font-size: 12px; cursor: help; }

/* "Предстои" placeholders */
.soon-wrap { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 14px; }
.soon-card { background: #161b27; border: 1px dashed #30363d; border-radius: 8px; padding: 14px 16px; }
.soon-head { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; }
.soon-head h3 { margin: 0; font-size: 14px; font-weight: 600; color: #8b949e; }
.soon-badge { font-size: 10px; text-transform: uppercase; letter-spacing: 0.5px; font-weight: 700; color: #d29922; background: #d2992222; border: 1px solid #d2992244; padding: 2px 8px; border-radius: 10px; }
.soon-card p { font-size: 12.5px; color: #8b949e; line-height: 1.5; margin: 0; }

/* Data quality */
.dq-card { background: #161b27; border: 1px solid #d29922; border-radius: 10px; padding: 20px; }
.dq-card h3 { color: #d29922; font-size: 14px; margin-bottom: 12px; }
.dq-item { font-size: 12px; color: #8b949e; margin-bottom: 6px; padding-left: 12px; }
.dq-item::before { content: "⚠ "; color: #d29922; }

code { font-family: 'Consolas', 'Monaco', monospace; background: #21262d; color: #c9d1d9; padding: 1px 5px; border-radius: 3px; font-size: 12.5px; }
.brief-footer { border-top: 1px solid #30363d; padding-top: 16px; margin-top: 30px; font-size: 12px; color: #8b949e; }
.brief-footer p { margin: 6px 0; }
.brief-footer h4 { font-size: 12.5px; text-transform: uppercase; color: #8b949e; letter-spacing: 0.7px; margin: 10px 0 6px; }
.methodology summary { cursor: pointer; color: #58a6ff; }
"""
