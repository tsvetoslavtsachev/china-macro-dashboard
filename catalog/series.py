"""
catalog/series.py
=================
Декларативен каталог на икономическите серии за Китай.

Всяка серия е self-contained запис с идентичност, таксономия, обработка,
метаданни и narrative hint. Системата е построена, за да може тук да се
добавят серии, без да се пипа аналитичен код.

Источници:
  worldbank  — World Bank Indicators API (годишни данни, надежден)
  imf_ifs    — IMF International Financial Statistics via DBnomics (месечни)
  akshare    — AkShare Python library (месечни, китайски източници)
  external   — ръчно добавяни / Bloomberg backfill
  pending    — планирани серии, все още не имплементирани
"""
from __future__ import annotations
from typing import Any

# ============================================================
# ALLOWED VALUES (за validation)
# ============================================================

ALLOWED_SOURCES = {"worldbank", "imf_ifs", "akshare", "external", "pending"}
ALLOWED_REGIONS = {"CN", "GLOBAL"}
ALLOWED_LENSES = {"labor", "growth", "inflation", "credit", "property"}
ALLOWED_TRANSFORMS = {"level", "yoy_pct", "mom_pct", "qoq_pct", "z_score", "first_diff"}
ALLOWED_TAGS = {"non_consensus", "structural", "data_quality_risk"}
ALLOWED_SCHEDULES = {"weekly", "monthly", "quarterly", "annually"}


# ============================================================
# SERIES CATALOG
# ============================================================

SERIES_CATALOG: dict[str, dict[str, Any]] = {

    # ───────────────────────────────────────────────────────
    # GROWTH / gdp
    # ───────────────────────────────────────────────────────

    "CN_GDP_GROWTH": {
        "source": "worldbank",
        "id": "NY.GDP.MKTP.KD.ZG",
        "region": "CN",
        "name_bg": "БВП — реален растеж (YoY %)",
        "name_en": "GDP Growth Rate (annual %)",
        "lens": ["growth"],
        "peer_group": "gdp",
        "tags": [],
        "transform": "level",
        "is_rate": True,
        "historical_start": "2000-01-01",
        "release_schedule": "annually",
        "typical_release": "Q1 следващата година",
        "revision_prone": True,
        "narrative_hint": "Официален таргет ~5%. Политически чувствителен. GDP deflator отрицателен → реалният растеж е надценен спрямо номиналния.",
    },
    "CN_INDUSTRY_GROWTH": {
        "source": "worldbank",
        "id": "NV.IND.TOTL.KD.ZG",
        "region": "CN",
        "name_bg": "Индустрия — реален растеж (YoY %)",
        "name_en": "Industry Value Added Growth (annual %)",
        "lens": ["growth"],
        "peer_group": "gdp",
        "tags": [],
        "transform": "level",
        "is_rate": True,
        "historical_start": "2000-01-01",
        "release_schedule": "annually",
        "typical_release": "Q1 следващата година",
        "revision_prone": False,
        "narrative_hint": "По-малко манипулируема от headline GDP. Включва производство, строителство, добив.",
    },
    "CN_SERVICES_GROWTH": {
        "source": "worldbank",
        "id": "NV.SRV.TOTL.KD.ZG",
        "region": "CN",
        "name_bg": "Услуги — реален растеж (YoY %)",
        "name_en": "Services Value Added Growth (annual %)",
        "lens": ["growth"],
        "peer_group": "gdp",
        "tags": [],
        "transform": "level",
        "is_rate": True,
        "historical_start": "2000-01-01",
        "release_schedule": "annually",
        "typical_release": "Q1 следващата година",
        "revision_prone": False,
        "narrative_hint": "Структурен преход от производство към услуги. Ако услугите забавят, цялата икономика е под натиск.",
    },
    "CN_MANUFACTURING_GDP": {
        "source": "worldbank",
        "id": "NV.IND.MANF.ZS",
        "region": "CN",
        "name_bg": "Производство — дял от БВП (%)",
        "name_en": "Manufacturing, Value Added (% of GDP)",
        "lens": ["growth"],
        "peer_group": "gdp",
        "tags": ["structural"],
        "transform": "level",
        "is_rate": False,
        "historical_start": "2000-01-01",
        "release_schedule": "annually",
        "typical_release": "Q1 следващата година",
        "revision_prone": False,
        "narrative_hint": "Намалява структурно (~25% 2024). Китай се опитва да задържи manufacturing base срещу reshoring натиска.",
    },
    "CN_CAPEX_GDP": {
        "source": "worldbank",
        "id": "NE.GDI.TOTL.ZS",
        "region": "CN",
        "name_bg": "Брутно капиталообразуване — дял от БВП (%)",
        "name_en": "Gross Capital Formation (% of GDP)",
        "lens": ["growth"],
        "peer_group": "investment",
        "tags": [],
        "transform": "level",
        "is_rate": False,
        "historical_start": "2000-01-01",
        "release_schedule": "annually",
        "typical_release": "Q1 следващата година",
        "revision_prone": False,
        "narrative_hint": "~40% от GDP — изключително висок за голяма икономика. Намаляването му е неизбежно при rebalancing към потребление.",
    },

    # ───────────────────────────────────────────────────────
    # INFLATION / prices
    # ───────────────────────────────────────────────────────

    "CN_CPI_YOY": {
        "source": "worldbank",
        "id": "FP.CPI.TOTL.ZG",
        "region": "CN",
        "name_bg": "ИПЦ — инфлация (YoY %)",
        "name_en": "CPI Inflation (annual %)",
        "lens": ["inflation"],
        "peer_group": "cpi",
        "tags": [],
        "transform": "level",
        "is_rate": True,
        "historical_start": "2000-01-01",
        "release_schedule": "annually",
        "typical_release": "Q1 следващата година",
        "revision_prone": False,
        "narrative_hint": "Близо до нула (0.22% 2024). Дефлационен риск — Japan-style deflation scenario е реален.",
    },
    "CN_GDP_DEFLATOR": {
        "source": "worldbank",
        "id": "NY.GDP.DEFL.KD.ZG",
        "region": "CN",
        "name_bg": "БВП дефлатор (YoY %)",
        "name_en": "GDP Deflator Growth (annual %)",
        "lens": ["inflation"],
        "peer_group": "cpi",
        "tags": ["non_consensus"],
        "transform": "level",
        "is_rate": True,
        "historical_start": "2000-01-01",
        "release_schedule": "annually",
        "typical_release": "Q1 следващата година",
        "revision_prone": False,
        "narrative_hint": "Отрицателен (-0.71% 2024) → номиналният GDP расте по-бавно от реалния. Широка дефлация в икономиката.",
    },
    "CN_CPI_INDEX": {
        "source": "imf_ifs",
        "id": "M.CN.PCPI_IX",
        "region": "CN",
        "name_bg": "ИПЦ — индекс (месечен)",
        "name_en": "CPI Index (monthly)",
        "lens": ["inflation"],
        "peer_group": "cpi",
        "tags": [],
        "transform": "yoy_pct",
        "is_rate": True,
        "historical_start": "2000-01-01",
        "release_schedule": "monthly",
        "typical_release": "~10-15 дни след края на месеца",
        "revision_prone": False,
        "narrative_hint": "Месечна честота — по-актуален сигнал от годишния WB. YoY transform дава инфлационния тренд.",
    },
    "CN_PPI_INDEX": {
        "source": "imf_ifs",
        "id": "M.CN.PPPI_IX",
        "region": "CN",
        "name_bg": "ИПП — индекс (месечен)",
        "name_en": "PPI Index (monthly)",
        "lens": ["inflation"],
        "peer_group": "ppi",
        "tags": ["non_consensus"],
        "transform": "yoy_pct",
        "is_rate": True,
        "historical_start": "2000-01-01",
        "release_schedule": "monthly",
        "typical_release": "~10-15 дни след края на месеца",
        "revision_prone": False,
        "narrative_hint": "Producer prices — leading indicator за CPI с 2-3 месеца. Отрицателна PPI → дефлационен натиск в производствения сектор.",
    },

    # ───────────────────────────────────────────────────────
    # LABOR / unemployment
    # ───────────────────────────────────────────────────────

    "CN_UNEMPLOYMENT": {
        "source": "worldbank",
        "id": "SL.UEM.TOTL.ZS",
        "region": "CN",
        "name_bg": "Безработица — официална (ILO, %)",
        "name_en": "Unemployment Rate (ILO, %)",
        "lens": ["labor"],
        "peer_group": "unemployment",
        "tags": ["data_quality_risk"],
        "transform": "level",
        "is_rate": False,
        "historical_start": "2000-01-01",
        "release_schedule": "annually",
        "typical_release": "Q1 следващата година",
        "revision_prone": False,
        "narrative_hint": "Официалната 'surveyed urban unemployment rate' (~5%) е широко считана за подценена. Не включва мигрантски работници и неформалния сектор.",
    },
    "CN_YOUTH_UNEMPLOYMENT": {
        "source": "worldbank",
        "id": "SL.UEM.1524.ZS",
        "region": "CN",
        "name_bg": "Младежка безработица (16-24 г., %)",
        "name_en": "Youth Unemployment Rate (15-24, %)",
        "lens": ["labor"],
        "peer_group": "unemployment",
        "tags": ["structural", "non_consensus"],
        "transform": "level",
        "is_rate": False,
        "historical_start": "2000-01-01",
        "release_schedule": "annually",
        "typical_release": "Q1 следващата година",
        "revision_prone": False,
        "narrative_hint": "Рекорд 21.3% юни 2023. НБС спря публикуването за 6 месеца. Структурен проблем — образователна система произвежда повече дипломирани, отколкото пазарът може да абсорбира.",
    },
    "CN_LABOR_PARTICIPATION": {
        "source": "worldbank",
        "id": "SL.TLF.CACT.ZS",
        "region": "CN",
        "name_bg": "Коефициент на участие в работната сила (%)",
        "name_en": "Labor Force Participation Rate (%)",
        "lens": ["labor"],
        "peer_group": "unemployment",
        "tags": ["structural"],
        "transform": "level",
        "is_rate": False,
        "historical_start": "2000-01-01",
        "release_schedule": "annually",
        "typical_release": "Q1 следващата година",
        "revision_prone": False,
        "narrative_hint": "Демографски натиск — стареещо население намалява работната сила. Структурен headwind за растежа.",
    },

    # ───────────────────────────────────────────────────────
    # CREDIT / monetary policy
    # ───────────────────────────────────────────────────────

    "CN_POLICY_RATE": {
        "source": "imf_ifs",
        "id": "M.CN.FPOLM_PA",
        "region": "CN",
        "name_bg": "Политическа лихва — PBoC 7-day repo (%)",
        "name_en": "PBoC Policy Rate (7-day reverse repo, %)",
        "lens": ["credit"],
        "peer_group": "rates",
        "tags": [],
        "transform": "level",
        "is_rate": False,
        "historical_start": "2000-01-01",
        "release_schedule": "monthly",
        "typical_release": "при промяна",
        "revision_prone": False,
        "narrative_hint": "PBoC benchmark rate. Намален до 1.4% (2025). Monetary easing цикъл в ход.",
    },
    "CN_LENDING_RATE": {
        "source": "imf_ifs",
        "id": "M.CN.FILR_PA",
        "region": "CN",
        "name_bg": "Кредитна лихва (%)",
        "name_en": "Lending Rate (%)",
        "lens": ["credit"],
        "peer_group": "rates",
        "tags": [],
        "transform": "level",
        "is_rate": False,
        "historical_start": "2000-01-01",
        "release_schedule": "monthly",
        "typical_release": "месечно",
        "revision_prone": False,
        "narrative_hint": "Реален cost of credit за икономиката. Spread с deposit rate = bank margin. Намаляването му е ключово за credit impulse.",
    },
    "CN_DEPOSIT_RATE": {
        "source": "imf_ifs",
        "id": "M.CN.FIDR_PA",
        "region": "CN",
        "name_bg": "Депозитна лихва (%)",
        "name_en": "Deposit Rate (%)",
        "lens": ["credit"],
        "peer_group": "rates",
        "tags": [],
        "transform": "level",
        "is_rate": False,
        "historical_start": "2000-01-01",
        "release_schedule": "monthly",
        "typical_release": "месечно",
        "revision_prone": False,
        "narrative_hint": "Намалена до 1.5% (2025). Ниски депозитни лихви → домакинствата търсят алтернативи (акции, имоти).",
    },
    "CN_CREDIT_PRIVATE": {
        "source": "worldbank",
        "id": "FS.AST.PRVT.GD.ZS",
        "region": "CN",
        "name_bg": "Кредит към частния сектор (% от БВП)",
        "name_en": "Domestic Credit to Private Sector (% of GDP)",
        "lens": ["credit"],
        "peer_group": "credit_depth",
        "tags": ["non_consensus"],
        "transform": "level",
        "is_rate": False,
        "historical_start": "2000-01-01",
        "release_schedule": "annually",
        "typical_release": "Q1 следващата година",
        "revision_prone": False,
        "narrative_hint": "194% от GDP (2024) — изключително висок. Debt overhang ограничава monetary policy transmission. Кредитният импулс (промяна в новия кредит) е по-важен от нивото.",
    },
    "CN_M2_GDP": {
        "source": "worldbank",
        "id": "FM.LBL.BMNY.GD.ZS",
        "region": "CN",
        "name_bg": "М2 — дял от БВП (%)",
        "name_en": "Broad Money M2 (% of GDP)",
        "lens": ["credit"],
        "peer_group": "credit_depth",
        "tags": [],
        "transform": "level",
        "is_rate": False,
        "historical_start": "2000-01-01",
        "release_schedule": "annually",
        "typical_release": "Q1 следващата година",
        "revision_prone": False,
        "narrative_hint": "227% от GDP (2024) — най-висок в света сред големите икономики. Отразява финансова дълбочина, но и потенциален кредитен риск.",
    },
    "CN_CNY_USD": {
        "source": "imf_ifs",
        "id": "M.CN.ENDA_XDC_USD_RATE",
        "region": "CN",
        "name_bg": "Валутен курс CNY/USD",
        "name_en": "CNY/USD Exchange Rate",
        "lens": ["credit"],
        "peer_group": "currency",
        "tags": [],
        "transform": "level",
        "is_rate": False,
        "historical_start": "2000-01-01",
        "release_schedule": "monthly",
        "typical_release": "месечно",
        "revision_prone": False,
        "narrative_hint": "Управляван флоат. PBoC контролира дневния band. Отслабването на CNY е инструмент за export competitiveness, но предизвиква capital outflows.",
    },

    # ───────────────────────────────────────────────────────
    # PROPERTY & TRADE
    # ───────────────────────────────────────────────────────

    "CN_CURRENT_ACCOUNT": {
        "source": "worldbank",
        "id": "BN.CAB.XOKA.GD.ZS",
        "region": "CN",
        "name_bg": "Текуща сметка — баланс (% от БВП)",
        "name_en": "Current Account Balance (% of GDP)",
        "lens": ["property"],
        "peer_group": "trade",
        "tags": [],
        "transform": "level",
        "is_rate": False,
        "historical_start": "2000-01-01",
        "release_schedule": "annually",
        "typical_release": "Q1 следващата година",
        "revision_prone": False,
        "narrative_hint": "Рекорден излишък 2.26% GDP (2024). Търговски напрежения с US/EU. Exports boom компенсира слабото вътрешно търсене.",
    },
    "CN_EXPORTS_GDP": {
        "source": "worldbank",
        "id": "NE.EXP.GNFS.ZS",
        "region": "CN",
        "name_bg": "Износ — дял от БВП (%)",
        "name_en": "Exports of Goods and Services (% of GDP)",
        "lens": ["property"],
        "peer_group": "trade",
        "tags": [],
        "transform": "level",
        "is_rate": False,
        "historical_start": "2000-01-01",
        "release_schedule": "annually",
        "typical_release": "Q1 следващата година",
        "revision_prone": False,
        "narrative_hint": "20% от GDP. Export-led growth модел. Тарифните войни с US/EU са директна заплаха за тази компонента.",
    },
    "CN_FDI_GDP": {
        "source": "worldbank",
        "id": "BX.KLT.DINV.WD.GD.ZS",
        "region": "CN",
        "name_bg": "ПЧИ — входящи (% от БВП)",
        "name_en": "FDI Inflows (% of GDP)",
        "lens": ["property"],
        "peer_group": "investment",
        "tags": ["structural"],
        "transform": "level",
        "is_rate": False,
        "historical_start": "2000-01-01",
        "release_schedule": "annually",
        "typical_release": "Q1 следващата година",
        "revision_prone": False,
        "narrative_hint": "Срина се до 0.10% GDP (2024) — исторически минимум. Геополитически de-risking от западни компании. Структурна промяна в глобалните вериги на доставки.",
    },
    "CN_FIXED_CAPITAL": {
        "source": "worldbank",
        "id": "NE.GDI.FTOT.ZS",
        "region": "CN",
        "name_bg": "Брутно фиксирано капиталообразуване (% от БВП)",
        "name_en": "Gross Fixed Capital Formation (% of GDP)",
        "lens": ["property"],
        "peer_group": "investment",
        "tags": [],
        "transform": "level",
        "is_rate": False,
        "historical_start": "2000-01-01",
        "release_schedule": "annually",
        "typical_release": "Q1 следващата година",
        "revision_prone": False,
        "narrative_hint": "~40% от GDP. Включва имоти, инфраструктура, оборудване. Намаляването е неизбежно при rebalancing — ключов риск за растежа.",
    },
    "CN_PRIVATE_CAPEX": {
        "source": "worldbank",
        "id": "NE.GDI.FPRV.ZS",
        "region": "CN",
        "name_bg": "Частно фиксирано капиталообразуване (% от БВП)",
        "name_en": "Private Gross Fixed Capital Formation (% of GDP)",
        "lens": ["property"],
        "peer_group": "investment",
        "tags": ["non_consensus"],
        "transform": "level",
        "is_rate": False,
        "historical_start": "2000-01-01",
        "release_schedule": "annually",
        "typical_release": "Q1 следващата година",
        "revision_prone": False,
        "narrative_hint": "Proxy за частния имотен и бизнес инвестиционен цикъл. Намаляването показва загуба на частен инвестиционен апетит.",
    },
    "CN_NEW_HOUSE_PRICE": {
        "source": "akshare",
        "id": "new_house_price",
        "region": "CN",
        "name_bg": "Цени на нови жилища — 70 града (YoY %)",
        "name_en": "New House Price Index (70 cities, YoY %)",
        "lens": ["property"],
        "peer_group": "housing",
        "tags": ["non_consensus"],
        "transform": "level",
        "is_rate": True,
        "historical_start": "2011-01-01",
        "release_schedule": "monthly",
        "typical_release": "~18 дни след края на месеца",
        "revision_prone": False,
        "narrative_hint": "НБС публикува 70-градски индекс. Отрицателен YoY от 2023. Evergrande/Country Garden кризата се отразява директно тук.",
    },
    "CN_FDI_ACTUAL": {
        "source": "akshare",
        "id": "fdi_actual",
        "region": "CN",
        "name_bg": "ПЧИ — реално използвани (месечно, млн. USD)",
        "name_en": "FDI Actually Used (monthly, USD mn)",
        "lens": ["property"],
        "peer_group": "investment",
        "tags": [],
        "transform": "yoy_pct",
        "is_rate": True,
        "historical_start": "2005-01-01",
        "release_schedule": "monthly",
        "typical_release": "~15-20 дни след края на месеца",
        "revision_prone": False,
        "narrative_hint": "По-актуален от годишния WB показател. YoY промяната показва тренда на чуждестранния инвестиционен апетит.",
    },

}


# ============================================================
# HELPERS
# ============================================================

def validate_catalog() -> list[str]:
    """Валидира каталога. Връща списък с грешки."""
    errors = []
    for key, entry in SERIES_CATALOG.items():
        entry["_key"] = key
        for field in ("source", "id", "region", "name_bg", "name_en", "lens",
                      "peer_group", "transform", "historical_start", "release_schedule"):
            if field not in entry:
                errors.append(f"{key}: missing field '{field}'")
        if entry.get("source") not in ALLOWED_SOURCES:
            errors.append(f"{key}: invalid source '{entry.get('source')}'")
        if entry.get("region") not in ALLOWED_REGIONS:
            errors.append(f"{key}: invalid region '{entry.get('region')}'")
        for lens in entry.get("lens", []):
            if lens not in ALLOWED_LENSES:
                errors.append(f"{key}: invalid lens '{lens}'")
        if entry.get("transform") not in ALLOWED_TRANSFORMS:
            errors.append(f"{key}: invalid transform '{entry.get('transform')}'")
        if entry.get("release_schedule") not in ALLOWED_SCHEDULES:
            errors.append(f"{key}: invalid release_schedule '{entry.get('release_schedule')}'")
        for tag in entry.get("tags", []):
            if tag not in ALLOWED_TAGS:
                errors.append(f"{key}: invalid tag '{tag}'")
    return errors


def series_by_source(source: str) -> list[dict]:
    """Връща всички серии от даден источник, с добавен _key."""
    result = []
    for key, entry in SERIES_CATALOG.items():
        if entry.get("source") == source:
            e = dict(entry)
            e["_key"] = key
            result.append(e)
    return result


def series_by_lens(lens: str) -> list[dict]:
    """Връща всички серии от даден lens."""
    result = []
    for key, entry in SERIES_CATALOG.items():
        if lens in entry.get("lens", []):
            e = dict(entry)
            e["_key"] = key
            result.append(e)
    return result
