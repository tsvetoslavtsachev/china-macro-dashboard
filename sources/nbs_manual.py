"""
sources/nbs_manual.py
=====================
Manual-CSV adapter за НБС (National Bureau of Statistics) тримесечни данни.

⚠ Защо ръчно: НБС няма публично API (data.stats.gov.cn е JS dashboard без
download endpoint). Затова тримесечните серии се сваляат ръчно като CSV и се
commit-ват в ``data/manual/``. Adapter-ът ги парсва директно — файлът е истината,
не мрежа. ``get_snapshot`` чете CSV-то на всяко извикване (евтино, винаги свежо);
``find_stale_specs`` връща [] (file-based → никога auto-stale).

Произвежда:
  CN_GDP_GROWTH_Q   — реален БВП растеж YoY (тримесечен) = index(preceding year=100) − 100
  CN_GDP_DEFLATOR_Q — имплицитен БВП дефлатор YoY (тримесечен) = номинален YoY − реален YoY

Източник файлове (НБС, Quarterly DB, „Current Quarter"):
  data/manual/nbs_quarterly_gdp_indices.csv         — Indices of GDP (preceding year=100)
  data/manual/nbs_quarterly_gdp_current_prices.csv  — GDP в текущи цени (100 млн. юана)

Обновяване: свали нов CSV от НБС → замени двата файла → commit. Adapter-ът сам
ще добави новото тримесечие.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

import pandas as pd

from sources._base import BaseAdapter


# Реда-игли в двата CSV (match по substring, толерантно към trailing spaces)
_REAL_INDEX_ROW = "Indices of Gross Domestic Product (preceding year=100)"
_NOMINAL_LEVEL_ROW = "Gross Domestic Product, Current Quarter (100 million yuan)"
_CURRENT_QUARTER_MARK = "Current Quarter"

_QUARTER_RE = re.compile(r"([1-4])Q\s*(20\d\d)")
_NUM_RE = re.compile(r",\s*(-?\d+\.?\d*)")


def _quarter_to_date(n: int, year: int) -> pd.Timestamp:
    """1Q2026 → 2026-03-31 (тримесечен край)."""
    return pd.Period(f"{year}Q{n}", freq="Q").end_time.normalize()


class NbsManualAdapter(BaseAdapter):
    """Чете committed НБС тримесечни CSV-та. Без мрежа."""

    SOURCE_NAME = "nbs_manual"

    INDICES_FILE = "data/manual/nbs_quarterly_gdp_indices.csv"
    PRICES_FILE = "data/manual/nbs_quarterly_gdp_current_prices.csv"

    def __init__(self, base_dir: Optional[Path] = None):
        # cache_*.json е gitignored (data/cache_*.json) — кешът е вторичен,
        # CSV-то е истината.
        super().__init__(cache_path="data/cache_nbs_manual.json", base_dir=base_dir)
        self._parsed: Optional[dict[str, pd.Series]] = None

    # ─── Parsing ──────────────────────────────────────────────

    def _read_row(self, path: Path, needle: str, current_quarter_only: bool = True):
        """Връща {quarter_label: float} за първия ред, съдържащ needle.

        Файловете имат и „Current Quarter", и „Accumulated" редове за всеки
        индикатор — взимаме Current Quarter (single-quarter четене)."""
        if not path.exists():
            return {}
        lines = path.read_text(encoding="utf-8-sig").splitlines()
        # header с тримесечията
        quarters: list[str] = []
        for ln in lines:
            qs = _QUARTER_RE.findall(ln)
            if len(qs) >= 4:
                quarters = [f"{n}Q{y}" for n, y in qs]
                break
        if not quarters:
            return {}
        for ln in lines:
            if needle in ln and (not current_quarter_only or _CURRENT_QUARTER_MARK in ln):
                vals = [float(v) for v in _NUM_RE.findall(ln)]
                # подравняваме спрямо тримесечията (newest-first и в двете)
                return {q: v for q, v in zip(quarters, vals)}
        return {}

    def _parse_all(self) -> dict[str, pd.Series]:
        if self._parsed is not None:
            return self._parsed

        idx_path = self.base_dir / self.INDICES_FILE
        prc_path = self.base_dir / self.PRICES_FILE

        real_idx = self._read_row(idx_path, _REAL_INDEX_ROW)          # {q: index (100=0%)}
        nom_lvl = self._read_row(prc_path, _NOMINAL_LEVEL_ROW)        # {q: 100 млн. юана}

        out: dict[str, pd.Series] = {}

        # ── CN_GDP_GROWTH_Q: реален YoY = index − 100 ──
        if real_idx:
            growth = {}
            for q, idx in real_idx.items():
                m = _QUARTER_RE.match(q)
                if not m:
                    continue
                growth[_quarter_to_date(int(m.group(1)), int(m.group(2)))] = round(idx - 100.0, 2)
            if growth:
                out["CN_GDP_GROWTH_Q"] = pd.Series(growth).sort_index()

        # ── CN_GDP_DEFLATOR_Q: номинален YoY − реален YoY ──
        # номинален YoY = ниво_t / ниво_{същото тримесечие преди 1 г.} − 1
        if real_idx and nom_lvl:
            deflator = {}
            for q, lvl in nom_lvl.items():
                m = _QUARTER_RE.match(q)
                if not m:
                    continue
                n, y = int(m.group(1)), int(m.group(2))
                prev_q = f"{n}Q{y - 1}"
                if prev_q not in nom_lvl or q not in real_idx:
                    continue
                if nom_lvl[prev_q] == 0:
                    continue
                nom_yoy = (lvl / nom_lvl[prev_q] - 1.0) * 100.0
                real_yoy = real_idx[q] - 100.0
                deflator[_quarter_to_date(n, y)] = round(nom_yoy - real_yoy, 2)
            if deflator:
                out["CN_GDP_DEFLATOR_Q"] = pd.Series(deflator).sort_index()

        self._parsed = out
        return out

    # ─── Adapter interface ────────────────────────────────────

    def _fetch_remote(self, series_key: str, source_id: str) -> pd.Series:
        return self._parse_all().get(series_key, pd.Series(dtype=float))

    def get_snapshot(self, series_keys) -> dict[str, pd.Series]:
        """Директно от CSV — файлът е истината, без TTL кеш."""
        parsed = self._parse_all()
        return {
            k: parsed[k] for k in series_keys
            if k in parsed and not parsed[k].dropna().empty
        }

    def find_stale_specs(self, specs):
        """File-based източник → никога auto-stale (get_snapshot чете директно)."""
        return []
