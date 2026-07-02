"""
china_macro_dashboard — Configuration
======================================
Единственото място, където пипаш настройки за China версията.

Разлики от US/EU:
- Три источника: World Bank (годишни), IMF IFS (месечни), AkShare (месечни)
- HISTORY_START е 2000 (след WTO accession 2001; данните от 1990 са по-ненадеждни)
- MODULE_WEIGHTS прекалибрирани за China реалност:
    growth доминира (explicit GDP target политика)
    credit #2 (China Credit Impulse е глобален leading indicator)
    property #3 (системен риск — ~25-30% от GDP)
    inflation по-малко (дефлационен, не инфлационен риск)
    labor по-малко (официалните данни са ненадеждни)
- Briefing-ът е на български
"""
import os

# ─── API endpoints (без автентикация) ────────────────────────────────────────
WORLDBANK_API_BASE = "https://api.worldbank.org/v2"
DBNOMICS_API_BASE = "https://api.db.nomics.world/v22"
# Опционален DBnomics ключ. Public v22 API е ОТВОРЕН (работи без ключ) — ключът
# е за по-висок rate-limit под тежко натоварване. Идва от .env (gitignored) или
# env var (CI секрет). None = не се изпраща (използваме отворения достъп).
DBNOMICS_API_KEY = os.environ.get("DBNOMICS_API_KEY")

# Optional .env override
_DOTENV = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(_DOTENV):
    with open(_DOTENV, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            value = value.strip().strip('"').strip("'")
            if key.strip() == "WORLDBANK_API_BASE":
                WORLDBANK_API_BASE = value
            elif key.strip() == "DBNOMICS_API_BASE":
                DBNOMICS_API_BASE = value
            elif key.strip() == "DBNOMICS_API_KEY":
                DBNOMICS_API_KEY = value


# ─── Кеш (адаптивен TTL по release schedule) ─────────────────────────────────
CACHE_TTL_HOURS_DEFAULT = 12
CACHE_TTL_DAYS_BY_SCHEDULE = {
    "weekly":     3,
    "monthly":   10,
    "quarterly": 30,
    "annually":  90,
}


# ─── Исторически прозорци ────────────────────────────────────────────────────
# Китай влезе в СТО декември 2001; данните преди 2000 са по-ненадеждни
HISTORY_START = "2000-01-01"
ANALOG_HISTORY_START = "2000-01-01"


# ─── Модулни тегла за Composite Macro Score (China-калибрирани) ──────────────
# Reasoning:
#   - growth 0.30    — Китай има explicit GDP таргет (~5%); всичко е подчинено
#   - credit 0.25    — China Credit Impulse е доказан глобален leading indicator
#   - property 0.20  — имотният сектор е ~25-30% от GDP; системен риск
#   - inflation 0.15 — дефлационен риск, не инфлационен (GDP deflator < 0)
#   - labor 0.10     — официалните данни са ненадеждни; youth unemployment е proxy
MODULE_WEIGHTS = {
    "growth":   0.30,
    "credit":   0.25,
    "property": 0.20,
    "inflation": 0.15,
    "labor":    0.10,
}


# ─── Macro режими (composite score → label, BG) ──────────────────────────────
MACRO_REGIMES = [
    (80, "ЕКСПАНЗИОНЕН",   "#00c853"),
    (65, "ЗДРАВ",          "#69f0ae"),
    (50, "СМЕСЕН",         "#ffd600"),
    (35, "ВЛОШАВАЩ СЕ",    "#ff6d00"),
    (0,  "РЕЦЕСИОНЕН",     "#d50000"),
]

# REVIEW-03 т.0.8 (P3-fix-A): под за брой backed лещи, преди композитът да е
# смислен headline. При <3/5 backed лещи, reweight формулата долу би дала
# число, съставено от 1-2 лещи, представено под етикета "Композитен Macro
# Score" — availability flip (demo: labor-only 18.6 → "РЕЦЕСИОНЕН"), не сигнал.
MIN_BACKED_LENSES = 3


def overall_composite(results: list) -> float | None:
    """Претеглен composite само върху лещи с НЕ-None composite (reweight).

    Леща без нито една композитна серия връща composite=None (modules._composite),
    за да не влачи фалшиво 50 в headline-а при (cache-miss ∩ akshare outage) — audit #9.
    Изключва се ЕДНОВРЕМЕННО от сумата И от теглата (reweight върху backed лещи).
    Единен източник за всички артефакти (export_api / briefing_context / deep /
    weekly / run) — да не дрейфа headline-ът между тях.

    REVIEW-03 т.0.8 (P3-fix-A): под MIN_BACKED_LENSES (3/5) backed лещи →
    None (недостатъчно за headline), вместо reweight върху 1-2 лещи.
    Старият `total_w == 0 → 50.0` клон е недостижим по спец сега (MIN_BACKED_
    LENSES гейтът хваща 0-backed случая по-рано с None) — заменен изрично,
    не изтрит тихо.
    """
    backed = [r for r in results if r.get("composite") is not None]
    if len(backed) < MIN_BACKED_LENSES:
        return None
    total_w = sum(MODULE_WEIGHTS.get(r["module"], 0) for r in backed)
    if not total_w:
        return None
    weighted = sum(r["composite"] * MODULE_WEIGHTS.get(r["module"], 0) for r in backed)
    return round(weighted / total_w, 1)


# ─── Изходна папка ───────────────────────────────────────────────────────────
OUTPUT_DIR = "output"
