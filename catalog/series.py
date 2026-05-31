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

ALLOWED_SOURCES = {"worldbank", "imf_ifs", "akshare", "external", "pending", "bloomberg_bridge"}
ALLOWED_REGIONS = {"CN", "HK", "GLOBAL"}
ALLOWED_LENSES = {"labor", "growth", "inflation", "credit", "property"}
ALLOWED_TRANSFORMS = {"level", "yoy_pct", "mom_pct", "qoq_pct", "z_score", "first_diff"}
ALLOWED_TAGS = {"non_consensus", "structural", "data_quality_risk"}
ALLOWED_SCHEDULES = {"daily", "weekly", "monthly", "quarterly", "annually"}


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

    # ════════════════════════════════════════════════════════
    # BLOOMBERG BRIDGE — monthly Bloomberg series от vrm-data-archive
    # ════════════════════════════════════════════════════════
    # 17 серии, които съществено разширяват China monthly tracking:
    #   - TSF, new loans, M2 YoY, LPR (PBoC)
    #   - PMI Mfg NBS + Caixin (Mfg/Svcs/Composite)
    #   - IP/Retail/FAI monthly YoY
    #   - Trade: exports/imports/FX reserves/CNH
    #   - CGB 10Y rate
    # Status: source="bloomberg_bridge" — invisible until parquet files exist.

    # ─── credit/money — akshare (PBoC monthly) ────────────
    "CN_TSF_FLOW": {
        "source": "akshare",
        "id": "tsf_flow",
        "region": "CN",
        "name_bg": "Total Social Financing — поток (месечно, CNY 100M)",
        "name_en": "Total Social Financing Flow (monthly increment)",
        "lens": ["credit"],
        "peer_group": "credit_depth",
        "tags": [],
        "transform": "level",
        "is_rate": False,
        "historical_start": "2015-01-01",
        "release_schedule": "monthly",
        "typical_release": "10-15_of_month",
        "revision_prone": False,
        "narrative_hint": "Monthly TSF поток (社会融资规模增量) от PBoC. Leads credit cycle. NOTE: akshare дава flow; за stock YoY ползвай Bloomberg manual fetch.",
    },
    "CN_NEW_LOANS_MOM": {
        "source": "akshare",
        "id": "new_loans",
        "region": "CN",
        "name_bg": "Нови RMB кредити (месечно, CNY 100M)",
        "name_en": "New RMB Loans (monthly, CNY 100M)",
        "lens": ["credit"],
        "peer_group": "credit_depth",
        "tags": [],
        "transform": "level",
        "is_rate": False,
        "historical_start": "2007-01-01",
        "release_schedule": "monthly",
        "typical_release": "10-15_of_month",
        "revision_prone": False,
        "narrative_hint": "TSF подкомпонент. Bank lending pulse — early signal на credit cycle.",
    },
    "CN_M2_YOY": {
        "source": "akshare",
        "id": "m2_yoy",
        "region": "CN",
        "name_bg": "M2 паричен агрегат (месечно YoY %)",
        "name_en": "M2 Money Supply YoY (monthly)",
        "lens": ["credit"],
        "peer_group": "credit_depth",
        "tags": [],
        "transform": "level",
        "is_rate": True,
        "historical_start": "2007-01-01",
        "release_schedule": "monthly",
        "typical_release": "10-15_of_month",
        "revision_prone": False,
        "narrative_hint": "Monthly cadence — допълва annual WB CN_M2_GDP. Главна liquidity мярка.",
    },
    "CN_LPR_1Y": {
        "source": "akshare",
        "id": "lpr_1y",
        "region": "CN",
        "name_bg": "1-годишен Loan Prime Rate (PBoC)",
        "name_en": "1-Year Loan Prime Rate (LPR)",
        "lens": ["credit"],
        "peer_group": "rates",
        "tags": [],
        "transform": "level",
        "is_rate": True,
        "historical_start": "2013-10-25",
        "release_schedule": "monthly",
        "typical_release": "20th_of_month",
        "revision_prone": False,
        "narrative_hint": "Замества benchmark lending rate от 2019. Главен policy signal.",
    },
    "CN_LPR_5Y": {
        "source": "akshare",
        "id": "lpr_5y",
        "region": "CN",
        "name_bg": "5-годишен Loan Prime Rate (mortgage benchmark)",
        "name_en": "5-Year Loan Prime Rate (LPR)",
        "lens": ["credit"],
        "peer_group": "rates",
        "tags": [],
        "transform": "level",
        "is_rate": True,
        "historical_start": "2019-08-20",
        "release_schedule": "monthly",
        "typical_release": "20th_of_month",
        "revision_prone": False,
        "narrative_hint": "Mortgage benchmark. Critical за property sector dynamics.",
    },

    # ─── PMI — akshare (NBS + Caixin Mfg/Svcs); Composite stays Bloomberg
    "CN_PMI_MFG_NBS": {
        "source": "akshare",
        "id": "pmi_mfg_nbs",
        "region": "CN",
        "name_bg": "NBS Manufacturing PMI (official)",
        "name_en": "NBS Manufacturing PMI (Official)",
        "lens": ["growth"],
        "peer_group": "diffusion_indices",
        "tags": [],
        "transform": "level",
        "is_rate": False,
        "historical_start": "2008-01-01",
        "release_schedule": "monthly",
        "typical_release": "last_day_of_month",
        "revision_prone": False,
        "narrative_hint": "Официален NBS. Tilts към large/SOE компании. >50 = expansion.",
    },
    "CN_PMI_NON_MFG_NBS": {
        "source": "akshare",
        "id": "pmi_non_mfg_nbs",
        "region": "CN",
        "name_bg": "NBS Non-Manufacturing PMI (official)",
        "name_en": "NBS Non-Manufacturing PMI (Official)",
        "lens": ["growth"],
        "peer_group": "diffusion_indices",
        "tags": [],
        "transform": "level",
        "is_rate": False,
        "historical_start": "2008-01-01",
        "release_schedule": "monthly",
        "typical_release": "last_day_of_month",
        "revision_prone": False,
        "narrative_hint": "Services + construction PMI от NBS. Bonus series — идва free със mfg fetch.",
    },
    "CN_PMI_MFG_CAIXIN": {
        "source": "akshare",
        "id": "pmi_mfg_caixin",
        "region": "CN",
        "name_bg": "Caixin/Markit Manufacturing PMI",
        "name_en": "Caixin/S&P Global Manufacturing PMI",
        "lens": ["growth"],
        "peer_group": "diffusion_indices",
        "tags": [],
        "transform": "level",
        "is_rate": False,
        "historical_start": "2012-01-01",
        "release_schedule": "monthly",
        "typical_release": "first_business_day",
        "revision_prone": True,
        "narrative_hint": "Caixin/Markit — tilts към SME/private. Divergence vs NBS = SOE/SME split.",
    },
    "CN_PMI_SVCS_CAIXIN": {
        "source": "akshare",
        "id": "pmi_svcs_caixin",
        "region": "CN",
        "name_bg": "Caixin Services PMI",
        "name_en": "Caixin/S&P Global Services PMI",
        "lens": ["growth"],
        "peer_group": "diffusion_indices",
        "tags": [],
        "transform": "level",
        "is_rate": False,
        "historical_start": "2012-04-01",
        "release_schedule": "monthly",
        "typical_release": "third_business_day",
        "revision_prone": True,
        "narrative_hint": "Services сектор — post-COVID structural transition.",
    },
    "CN_PMI_COMPOSITE_CAIXIN": {
        "source": "bloomberg_bridge",
        "id": "CN_PMI_COMPOSITE_CAIXIN",
        "parquet_path": "../vrm-data-archive/parquet/CN_PMI_COMPOSITE_CAIXIN.parquet",
        "license_class": "bloomberg_internal_use",
        "region": "CN",
        "name_bg": "Caixin Composite PMI",
        "name_en": "Caixin/S&P Global Composite PMI",
        "lens": ["growth"],
        "peer_group": "diffusion_indices",
        "tags": [],
        "transform": "level",
        "is_rate": False,
        "historical_start": "2005-11-01",
        "release_schedule": "monthly",
        "typical_release": "third_business_day",
        "revision_prone": True,
        "narrative_hint": "Weighted Mfg+Svcs. Главен composite leading indicator.",
    },

    # ─── activity — akshare (NBS monthly)
    "CN_IP_YOY": {
        "source": "akshare",
        "id": "ip_yoy",
        "region": "CN",
        "name_bg": "Индустриално производство (месечно YoY %)",
        "name_en": "Industrial Production YoY (monthly)",
        "lens": ["growth"],
        "peer_group": "hard_activity",
        "tags": [],
        "transform": "level",
        "is_rate": True,
        "historical_start": "1990-03-01",
        "release_schedule": "monthly",
        "typical_release": "15-20_of_month",
        "revision_prone": False,
        "narrative_hint": "NBS publication. Главна monthly activity мярка. Eliminates Jan/Feb (Chinese New Year).",
    },
    "CN_RETAIL_YOY": {
        "source": "akshare",
        "id": "retail_yoy",
        "region": "CN",
        "name_bg": "Продажби на дребно (месечно YoY %)",
        "name_en": "Retail Sales YoY (monthly)",
        "lens": ["growth"],
        "peer_group": "hard_activity",
        "tags": [],
        "transform": "level",
        "is_rate": True,
        "historical_start": "2008-01-01",
        "release_schedule": "monthly",
        "typical_release": "15-20_of_month",
        "revision_prone": False,
        "narrative_hint": "Consumption pulse. Post-COVID structurally lower than pre-2020.",
    },
    "CN_FAI_MOM_YOY": {
        "source": "akshare",
        "id": "fai_mom_yoy",
        "region": "CN",
        "name_bg": "Fixed Asset Investment — месечен YoY %",
        "name_en": "Fixed Asset Investment Monthly YoY (single-month)",
        "lens": ["property"],
        "peer_group": "investment",
        "tags": [],
        "transform": "level",
        "is_rate": True,
        "historical_start": "2008-01-01",
        "release_schedule": "monthly",
        "typical_release": "15-20_of_month",
        "revision_prone": False,
        "narrative_hint": "Monthly YoY от akshare gdzctz (NBS публикува officially YTD; monthly е по-чист сигнал).",
    },

    # ─── external — akshare (GAC + SAFE monthly)
    "CN_EXPORTS_USD_YOY": {
        "source": "akshare",
        "id": "exports_usd_yoy",
        "region": "CN",
        "name_bg": "Износ USD (месечно YoY %)",
        "name_en": "Exports USD YoY (monthly)",
        "lens": ["property"],
        "peer_group": "trade",
        "tags": [],
        "transform": "level",
        "is_rate": True,
        "historical_start": "1982-02-01",
        "release_schedule": "monthly",
        "typical_release": "first_half_of_month",
        "revision_prone": False,
        "narrative_hint": "China customs data (GAC). Monthly cadence, USD-denominated. Главен external demand pulse.",
    },
    "CN_IMPORTS_USD_YOY": {
        "source": "akshare",
        "id": "imports_usd_yoy",
        "region": "CN",
        "name_bg": "Внос USD (месечно YoY %)",
        "name_en": "Imports USD YoY (monthly)",
        "lens": ["property"],
        "peer_group": "trade",
        "tags": [],
        "transform": "level",
        "is_rate": True,
        "historical_start": "1996-02-01",
        "release_schedule": "monthly",
        "typical_release": "first_half_of_month",
        "revision_prone": False,
        "narrative_hint": "Domestic demand pulse. Commodities-heavy → leading commodity prices.",
    },
    "CN_FX_RESERVES": {
        "source": "akshare",
        "id": "fx_reserves",
        "region": "CN",
        "name_bg": "FX резерви (месечно, USD млрд.)",
        "name_en": "FX Reserves (monthly, USD bn)",
        "lens": ["property"],
        "peer_group": "trade",
        "tags": [],
        "transform": "level",
        "is_rate": False,
        "historical_start": "1978-12-01",
        "release_schedule": "monthly",
        "typical_release": "7th_of_month",
        "revision_prone": False,
        "narrative_hint": "SAFE publication. Capital flow indicator. <3T USD watch threshold.",
    },
    "CN_CNH": {
        "source": "bloomberg_bridge",
        "id": "CN_CNH",
        "parquet_path": "../vrm-data-archive/parquet/CN_CNH.parquet",
        "license_class": "bloomberg_internal_use",
        "region": "HK",
        "name_bg": "CNH — offshore CNY (USDCNH)",
        "name_en": "USDCNH (Offshore CNY)",
        "lens": ["property"],
        "peer_group": "trade",
        "tags": [],
        "transform": "level",
        "is_rate": False,
        "historical_start": "2010-08-23",
        "release_schedule": "daily",
        "typical_release": "daily_close",
        "revision_prone": False,
        "narrative_hint": "Offshore CNY. CNH-CNY spread показва onshore intervention pressure.",
    },

    # ─── rates ────────────────────────────────────────────
    "CN_CGB_10Y": {
        "source": "bloomberg_bridge",
        "id": "CN_CGB_10Y",
        "parquet_path": "../vrm-data-archive/parquet/CN_CGB_10Y.parquet",
        "license_class": "bloomberg_internal_use",
        "region": "CN",
        "name_bg": "10Y China Government Bond yield",
        "name_en": "China 10Y Government Bond Yield (CGB)",
        "lens": ["credit"],
        "peer_group": "rates",
        "tags": [],
        "transform": "level",
        "is_rate": True,
        "historical_start": "2002-01-01",
        "release_schedule": "daily",
        "typical_release": "daily_close",
        "revision_prone": False,
        "narrative_hint": "Sovereign benchmark. CGB-UST 10Y spread = capital flow incentive.",
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
