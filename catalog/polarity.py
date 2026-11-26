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
    "CN_MANUFACTURING_GDP": +1, "CN_RETAIL_YOY": +1,
    "CN_PMI_MFG_NBS": +1, "CN_PMI_NON_MFG_NBS": +1, "CN_PMI_COMPOSITE_CAIXIN": +1,
    "CN_GDP_GROWTH_Q": +1,
    # ПРОЛЕТР4: IP растеж и частните PMI — нагоре = по-здраво
    "CN_IP_YOY": +1, "CN_PMI_MFG_CAIXIN": +1, "CN_PMI_SVCS_CAIXIN": +1,

    # CREDIT — лихви/LPR/дълг-overhang: нагоре = по-зле (-1); ликвидност/поток/курс: +1
    "CN_LPR_1Y": -1, "CN_LPR_5Y": -1, "CN_BIS_CREDIT_GDP": -1,
    "CN_CNY_USD": +1, "CN_M2_YOY": +1, "CN_TSF_FLOW": +1,
    # ПРОЛЕТР4: по-бърз растеж на запаса на TSF = по-силен кредитен импулс
    "CN_TSF_STOCK_YOY": +1,
    # ПРОЛЕТР4 (състав 26.11): нови кредитни серии и лихви. Новите заеми +1 (поток, като TSF);
    # доходността на 10г ДЦК и 3М междубанковият процент са лихви: нагоре = по-зле (-1), като LPR.
    "CN_NEW_LOANS_MOM": +1, "CN_CGB_10Y": -1, "CN_INTERBANK_3M": -1,

    # INFLATION — линейно (+1); финалният score идва от абсолютни котви в модула (виж горе)
    "CN_CPI_YOY": +1, "CN_GDP_DEFLATOR": +1,
    "CN_CPI_YOY_AK": +1, "CN_PPI_YOY": +1, "CN_GDP_DEFLATOR_Q": +1,

    # LABOR — безработица -1, участие +1
    "CN_UNEMPLOYMENT": -1, "CN_YOUTH_UNEMPLOYMENT": -1, "CN_LABOR_PARTICIPATION": +1,
    # ПРОЛЕТР4: месечни серии; безработица нагоре = по-зле
    "CN_UNEMP_SURVEYED": -1, "CN_YOUTH_UNEMP_M": -1,

    # PROPERTY & TRADE — нагоре = по-здраво
    "CN_CURRENT_ACCOUNT": +1, "CN_EXPORTS_GDP": +1, "CN_FDI_GDP": +1,
    "CN_NEW_HOUSE_PRICE": +1,
    "CN_BIS_PROPERTY_YOY": +1, "CN_FAI_MOM_YOY": +1,
    # ПРОЛЕТР4: износ/внос (YoY) и имотни инвестиции/продажби (YTD YoY): нагоре = по-здраво
    "CN_EXPORTS_USD_YOY": +1, "CN_IMPORTS_USD_YOY": +1,
    "CN_RE_INVEST_YOY": +1, "CN_PROPERTY_SALES_YOY": +1,

    # EXTERNAL (нова 6-а леща). REER нагоре = по-скъп юан = по-слаба конкурентност → -1
    # (като EA_REER в EU каталога); резервите +1; износ/внос/текуща сметка +1 (вече горе).
    "CN_REER": -1, "CN_FX_RESERVES": +1,

    # ПРОЛЕТР4, втората вълна (26.11.2026, КТ-1/КТ-2; посоките чакат потвърждение от Ц.):
    # базисната инфлация +1 като общия ИПЦ (рискът е дефлацията); доверие, заетост и доходи +1;
    # спредът -1 (по-широк = повече страх); бюджетът (само за показване) +1.
    "CN_CORE_CPI_YOY": +1, "CN_CONS_CONF": +1, "CN_PMI_EMPLOYMENT": +1, "CN_DISP_INCOME_YOY": +1,
    "CN_CORP_SPREAD_3Y": -1, "CN_FISCAL_REV_YOY": +1, "CN_FISCAL_EXP_YOY": +1,
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
