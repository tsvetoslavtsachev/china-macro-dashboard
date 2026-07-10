"""
catalog/polarity.py  (China)
============================
Централен полярностен каталог за China lens health scoring — ЕДИНЕН източник
на истина (огледало на us/eu catalog/polarity.py структурата).

O3 Вълна 1 (КОКПИТ, 2026-07-10): преди това полярността живееше като per-серия
`invert:bool` в петте modules/*.py + тих fallback invert=False в
export_api.SERIES_META / build_series_data. Този fallback веднъж вече мис-скорира
(S7 CN-1: рекордно нисък ипотечен LPR четеше „17.6 РЕЦЕСИОНЕН" вместо easing ~82).
Централизацията форсира ИЗРИЧНО решение и затваря тихия fallback: scoring-ът чете
polarity_for(), не per-серия invert. Per-серия invert остава в модулните SERIES
само като кръстосано-проверена анотация (test_polarity_catalog пинва равенството).

Типове (CN е ЛИНЕЙНА — без U-форма; знакът е достатъчен):
  +1  → нагоре = по-здраво (растеж, PMI, заетост, участие, износ, кредитен импулс)
  -1  → нагоре = по-зле (безработица, лихви/LPR, дълг/БВП overhang)

ВАЖНО — инфлационната леща (U-vs-линейна разлика ОСТАВА, тя е ДИЗАЙН):
  CN инфлацията се скорира ЛИНЕЙНО чрез абсолютни котви (_score_inflation /
  _deflator_anchor в modules/inflation.py), защото рискът за Китай е ДЕФЛАЦИЯ, не
  отклонение от 2% в двете посоки (US/EU U-форма). Затова инфлационните серии тук
  са +1 (линейно), а лещата носи изричен етикет „несравнима между региони по
  дизайн" (REGION_INCOMPARABLE_LENSES / INFLATION_COMPARABILITY_NOTE). Каноничният
  етикет пътува до macro_state.json (export_api), за да не се сравни наивно с US/EU.
"""
from __future__ import annotations

# Инфлационната леща е несравнима между региони ПО ДИЗАЙН (CN линейна vs US/EU U-форма).
REGION_INCOMPARABLE_LENSES = {"inflation"}
INFLATION_COMPARABILITY_NOTE = (
    "несравнима между региони по дизайн — CN линейна дефлационна леща "
    "(абсолютни котви) vs US/EU U-форма около 2%"
)

# ── Централен полярностен вектор (per серия) ─────────────────────────────────
POLARITY: dict[str, int] = {
    # GROWTH — нагоре = по-здраво
    "CN_GDP_GROWTH": +1, "CN_INDUSTRY_GROWTH": +1, "CN_SERVICES_GROWTH": +1,
    "CN_CAPEX_GDP": +1, "CN_MANUFACTURING_GDP": +1, "CN_RETAIL_YOY": +1,
    "CN_PMI_MFG_NBS": +1, "CN_PMI_NON_MFG_NBS": +1, "CN_PMI_COMPOSITE_CAIXIN": +1,
    "CN_GDP_GROWTH_Q": +1, "CN_IP_YOY_NBS": +1,

    # CREDIT — лихви/LPR/дълг-overhang: нагоре = по-зле (-1); ликвидност/поток/курс: +1
    "CN_POLICY_RATE": -1, "CN_LENDING_RATE": -1, "CN_DEPOSIT_RATE": -1,
    "CN_CREDIT_PRIVATE": -1, "CN_LPR_1Y": -1, "CN_LPR_5Y": -1, "CN_BIS_CREDIT_GDP": -1,
    "CN_M2_GDP": +1, "CN_CNY_USD": +1, "CN_M2_YOY": +1, "CN_TSF_FLOW": +1,

    # INFLATION — линейно (+1); финалният score идва от абсолютни котви в модула (виж горе)
    "CN_CPI_YOY": +1, "CN_GDP_DEFLATOR": +1, "CN_CPI_INDEX": +1, "CN_PPI_INDEX": +1,
    "CN_CPI_YOY_AK": +1, "CN_PPI_YOY": +1, "CN_GDP_DEFLATOR_Q": +1,

    # LABOR — безработица -1, участие +1
    "CN_UNEMPLOYMENT": -1, "CN_YOUTH_UNEMPLOYMENT": -1, "CN_LABOR_PARTICIPATION": +1,

    # PROPERTY & TRADE — нагоре = по-здраво
    "CN_CURRENT_ACCOUNT": +1, "CN_EXPORTS_GDP": +1, "CN_FDI_GDP": +1,
    "CN_FIXED_CAPITAL": +1, "CN_PRIVATE_CAPEX": +1, "CN_NEW_HOUSE_PRICE": +1,
    "CN_FDI_ACTUAL": +1, "CN_BIS_PROPERTY_YOY": +1, "CN_FAI_MOM_YOY": +1,
}


def polarity_for(key: str) -> int:
    """Полярност (+1/-1) за CN серия.

    Default +1 (нагоре=здраво) за непознати — консервативно и ИДЕНТИЧНО на стария
    invert=False fallback, но вече централизирано. Всички модулни серии са изрично
    каталогизирани (покрито от test_polarity_catalog completeness/consistency)."""
    return POLARITY.get(key, +1)


def invert_for(key: str) -> bool:
    """Back-compat: полярността като invert bool (-1 ⇒ invert=True)."""
    return polarity_for(key) == -1
