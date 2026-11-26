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
  fred_csv   — FRED публичен CSV без ключ (курс, BIS кредит/имоти, REER, 3М междубанков)
  chinadata_live — chinadata.live (месечни, независим препубликатор; втори източник + кръстосани проверки)
  external   — ръчно добавяни / Bloomberg backfill
  pending    — планирани серии, все още не имплементирани
"""
from __future__ import annotations
from typing import Any

# ============================================================
# ALLOWED VALUES (за validation)
# ============================================================

ALLOWED_SOURCES = {"worldbank", "imf_ifs", "akshare", "external", "pending", "bloomberg_bridge", "nbs_manual", "dbnomics", "chinadata_live", "fred_csv"}
ALLOWED_REGIONS = {"CN", "HK", "GLOBAL"}
# ПРОЛЕТР4 (26.11.2026, реш. Ц. КТ-2): лещите с оценка и лещите само за показване (бюджетът),
# както в САЩ и еврозоната. Лещите за показване нямат модул и не влизат в оценката.
SCORED_LENSES = {"labor", "growth", "inflation", "credit", "property", "external"}
DISPLAY_ONLY_LENSES = {"fiscal"}
ALLOWED_LENSES = SCORED_LENSES | DISPLAY_ONLY_LENSES
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
    "CN_GDP_GROWTH_Q": {
        "source": "nbs_manual",
        "id": "NBS_GDP_INDEX_CURRENT_QUARTER",
        "region": "CN",
        "name_bg": "БВП — реален растеж (тримесечен, YoY %)",
        "name_en": "Real GDP growth (quarterly YoY)",
        "lens": ["growth"],
        "peer_group": "gdp_quarterly",
        "tags": [],
        "transform": "level",
        "is_rate": True,
        "historical_start": "2021-01-01",
        "release_schedule": "quarterly",
        "typical_release": "~3 седмици след тримесечието (НБС)",
        "revision_prone": True,
        "narrative_hint": "НБС тримесечен реален БВП (index preceding year=100 − 100). Ръчен CSV — НБС няма API. Policy-pinned ~5%; почти не мърда.",
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
    "CN_GDP_DEFLATOR_Q": {
        "source": "nbs_manual",
        "id": "NBS_GDP_DEFLATOR_CURRENT_QUARTER_DERIVED",
        "region": "CN",
        "name_bg": "БВП дефлатор (тримесечен, YoY %)",
        "name_en": "GDP deflator (quarterly YoY, derived)",
        "lens": ["inflation"],
        "peer_group": "deflator_quarterly",
        "tags": [],
        "transform": "level",
        "is_rate": True,
        "historical_start": "2022-01-01",
        "release_schedule": "quarterly",
        "typical_release": "~3 седмици след тримесечието (НБС)",
        "revision_prone": True,
        "narrative_hint": "Имплицитен дефлатор = номинален YoY − реален YoY (от НБС тримесечни данни). Отрицателен 12 поредни тримесечия (2Q2023–1Q2026) → debt-deflation. Ключов falsifier сигнал за recessionary режима.",
    },
    "CN_CPI_YOY_AK": {
        "source": "akshare",
        "id": "cpi_yoy",
        "region": "CN",
        "name_bg": "ИПЦ — инфлация (месечен YoY %, NBS)",
        "name_en": "CPI YoY (monthly, NBS via akshare)",
        "lens": ["inflation"],
        "peer_group": "cpi",
        "tags": [],
        "transform": "level",
        "is_rate": True,
        "historical_start": "2000-01-01",
        "release_schedule": "monthly",
        "typical_release": "~10 дни след края на месеца",
        "revision_prone": False,
        "narrative_hint": "Свеж месечен CPI YoY от НБС (akshare) — заменя застоялия IMF CN_CPI_INDEX (2025-07). Рефлира към +1.2% (2026-04) от −0.3% (2025-09) → потребителската дефлация отслабва. Дълга история за percentile.",
    },
    "CN_PPI_YOY": {
        "source": "akshare",
        "id": "ppi_yoy",
        "region": "CN",
        "name_bg": "ИПП — производствени цени (месечен, YoY %)",
        "name_en": "PPI YoY (monthly)",
        "lens": ["inflation"],
        "peer_group": "ppi",
        "tags": ["non_consensus"],
        "transform": "level",
        "is_rate": True,
        "historical_start": "2000-01-01",
        "release_schedule": "monthly",
        "typical_release": "~10-15 дни след края на месеца",
        "revision_prone": False,
        "narrative_hint": "Свеж месечен PPI YoY от НБС (akshare) — замества мъртвия IMF/IFS PPI (замръзнал 2022-12). Отрицателен от 2022 → дефлация в производствения сектор. Дълга история за percentile.",
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

    "CN_BIS_CREDIT_GDP": {
        "source": "fred_csv",
        "id": "QCNPAM770A@qend",
        "region": "CN",
        "name_bg": "Кредит към частния нефинансов сектор (% от БВП, BIS)",
        "name_en": "Credit to Private Non-Financial Sector (% of GDP, BIS)",
        "lens": ["credit"],
        "peer_group": "credit_depth",
        "tags": ["non_consensus"],
        "transform": "level",
        "is_rate": False,
        "historical_start": "2000-01-01",
        "release_schedule": "quarterly",
        "typical_release": "~1.5 г. лаг (BIS, през FRED)",
        "revision_prone": True,
        "narrative_hint": "BIS канонична серия за credit-to-GDP (тримесечна, през FRED QCNPAM770A). По-свежа и стандартна от годишния WB CN_CREDIT_PRIVATE. Базата за China Credit Impulse. Висок дял = debt overhang → invert.",
    },
    "CN_CNY_USD": {
        "source": "fred_csv",
        "id": "DEXCHUS",
        "region": "CN",
        "name_bg": "Валутен курс CNY/USD (юана за 1 долар, дневен)",
        "name_en": "CNY/USD Exchange Rate",
        "lens": ["external"],
        "peer_group": "currency",
        "tags": [],
        "transform": "level",
        "is_rate": False,
        "historical_start": "2000-01-01",
        "release_schedule": "daily",
        "typical_release": "дневно (FRED DEXCHUS, Fed H.10)",
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
        "lens": ["external"],
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
    "CN_BIS_PROPERTY_YOY": {
        "source": "fred_csv",
        "id": "QCNN628BIS@qend@yoy",
        "region": "CN",
        "name_bg": "Жилищни имотни цени (YoY %, BIS номинал)",
        "name_en": "Residential Property Prices YoY (BIS nominal)",
        "lens": ["property"],
        "peer_group": "housing",
        "tags": ["non_consensus"],
        "transform": "level",
        "is_rate": True,
        "historical_start": "2000-01-01",
        "release_schedule": "quarterly",
        "typical_release": "~1 тримесечие лаг (BIS, през FRED)",
        "revision_prone": True,
        "narrative_hint": "BIS жилищни имотни цени YoY (тримесечно; изчислен от номиналния индекс QCNN628BIS на FRED спрямо същото тримесечие година по-рано). По-широко покритие (вкл. вторичен пазар) и по-дълга чиста история от 70-градския akshare индекс. Дълбока имотна дефлация.",
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
        "narrative_hint": "Monthly TSF поток (社会融资规模增量) от PBoC. Leads credit cycle. NOTE: akshare дава flow; запасът YoY е отделната серия CN_TSF_STOCK_YOY. Източникът в akshare стои на 2026-04; опашката от 2026-05 се дописва от chinadata.live china-tsf-flow само докато двата реда съвпадат в припокриването в рамките на 1% (виж series_data meta.splice).",
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
        "historical_start": "2014-04-01",
        "release_schedule": "monthly",
        "typical_release": "first_business_day",
        "revision_prone": True,
        "narrative_hint": "Caixin/Markit — tilts към SME/private. Divergence vs NBS = SOE/SME split. От 2026-11 данните идват от macro_china_pmi_manufacturing_cx (akshare 1.20.70); частният PMI на S&P Global за Китай е сменял името на спонсора (Caixin -> RatingDog) - непроверено, затова името в каталога остава.",
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
        "historical_start": "2014-04-01",
        "release_schedule": "monthly",
        "typical_release": "third_business_day",
        "revision_prone": True,
        "narrative_hint": "Services сектор — post-COVID structural transition.",
    },
    "CN_PMI_COMPOSITE_CAIXIN": {
        "source": "bloomberg_bridge",
        "id": "CN_PMI_COMPOSITE_CAIXIN",
        "parquet_path": "../../markets/vrm-data-archive/parquet/CN_PMI_COMPOSITE_CAIXIN.parquet",
        "license_class": "source_public",
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
        "narrative_hint": "Частен Services PMI (Caixin/S&P Global). От 2026-11 данните идват от macro_china_pmi_services_cx (akshare 1.20.70); смяната на спонсора на PMI (Caixin -> RatingDog) е непроверена, затова името остава.",
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
        "narrative_hint": "NBS publication. Главна monthly activity мярка. От 2026-11 идва от macro_china_industrial_value_added (akshare 1.20.70), датиран по отчетния месец (старата jin10 серия беше по месеца на публикуване, с един месец по-късно). Кръстосана проверка с chinadata.live china-industrial-output (допуск 0.15).",
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
        "lens": ["external"],
        "peer_group": "trade",
        "tags": [],
        "transform": "level",
        "is_rate": True,
        "historical_start": "1982-02-01",
        "release_schedule": "monthly",
        "typical_release": "first_half_of_month",
        "revision_prone": False,
        "narrative_hint": "China customs data (GAC). Monthly cadence, USD-denominated. Главен external demand pulse. От 2026-11 идва от macro_china_customs_trade (akshare 1.20.70), по отчетния месец. Кръстосана проверка с темп, изведен от нивата в chinadata.live china-trade-monthly (допуск 1.0 пр.п.).",
    },
    "CN_IMPORTS_USD_YOY": {
        "source": "akshare",
        "id": "imports_usd_yoy",
        "region": "CN",
        "name_bg": "Внос USD (месечно YoY %)",
        "name_en": "Imports USD YoY (monthly)",
        "lens": ["external"],
        "peer_group": "trade",
        "tags": [],
        "transform": "level",
        "is_rate": True,
        "historical_start": "1996-02-01",
        "release_schedule": "monthly",
        "typical_release": "first_half_of_month",
        "revision_prone": False,
        "narrative_hint": "Domestic demand pulse. Commodities-heavy → leading commodity prices. От 2026-11 идва от macro_china_customs_trade (akshare 1.20.70), по отчетния месец. БЕЗ кръстосана проверка: нивата на вноса в chinadata.live не съвпадат с akshare и не се смесват.",
    },
    "CN_FX_RESERVES": {
        "source": "akshare",
        "id": "fx_reserves",
        "region": "CN",
        "name_bg": "FX резерви (месечно, USD млрд.)",
        "name_en": "FX Reserves (monthly, USD bn)",
        "lens": ["external"],
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

    # ─── rates ────────────────────────────────────────────
    "CN_CGB_10Y": {
        "source": "akshare",
        "id": "cgb_10y",
        "bridge_fallback_parquet": "../../markets/vrm-data-archive/parquet/CN_CGB_10Y.parquet",
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
        "typical_release": "дневно (ChinaBond, крива на държавните облигации)",
        "revision_prone": False,
        "narrative_hint": "Sovereign benchmark. CGB-UST 10Y spread = capital flow incentive.",
    },


    # ─── ПРОЛЕТР4 (25.11.2026): месечен труд, кредит и имоти, живи данни ───
    "CN_UNEMP_SURVEYED": {
        "source": "akshare",
        "id": "unemp_surveyed",
        "region": "CN",
        "name_bg": "Безработица — градска анкетна, национална (месечно, %)",
        "name_en": "Urban Surveyed Unemployment Rate, national (monthly, %)",
        "lens": ["labor"],
        "peer_group": "unemployment",
        "tags": [],
        "transform": "level",
        "is_rate": True,
        "historical_start": "2018-01-01",
        "release_schedule": "monthly",
        "typical_release": "15-20_of_month",
        "revision_prone": False,
        "narrative_hint": "НБС, национален градски анкетен процент (全国城镇调查失业率) чрез akshare; кръстосана проверка с chinadata.live china-unemployment (допуск 0.1 пр.п.). Тясна лента около 5%, затова малки движения носят голям z; анкетата е смятана за подценена.",
    },
    "CN_YOUTH_UNEMP_M": {
        "source": "chinadata_live",
        "id": "china-youth-unemployment",
        "region": "CN",
        "name_bg": "Младежка безработица 16-24 г. без студенти (месечно, %)",
        "name_en": "Youth Surveyed Unemployment 16-24 excl. students (monthly, %)",
        "lens": ["labor"],
        "peer_group": "unemployment",
        "tags": ["structural", "non_consensus"],
        "transform": "level",
        "is_rate": True,
        "historical_start": "2024-01-01",
        "release_schedule": "monthly",
        "typical_release": "17-20_of_month",
        "revision_prone": False,
        "narrative_hint": "НБС (чрез chinadata.live, независим препубликатор; единственият източник тук, без втора проверка). Нова методология от декември 2023 (без студенти), история от 2024-01; сезонно висока през лятото (юли-август).",
    },
    "CN_TSF_STOCK_YOY": {
        "source": "chinadata_live",
        "id": "china-tsf-stock-yoy",
        "region": "CN",
        "name_bg": "TSF — запас, годишен темп (месечно, %)",
        "name_en": "Total Social Financing stock YoY (monthly, %)",
        "lens": ["credit"],
        "peer_group": "credit_depth",
        "tags": [],
        "transform": "level",
        "is_rate": True,
        "historical_start": "2025-09-01",
        "release_schedule": "monthly",
        "typical_release": "10-15_of_month",
        "revision_prone": False,
        "narrative_hint": "НБК (чрез chinadata.live). Растеж на запаса на общото социално финансиране; история само от 2025-09, затова percentile/z са на къс прозорец и носят малко тежест. Допълва потока CN_TSF_FLOW.",
    },
    "CN_RE_INVEST_YOY": {
        "source": "chinadata_live",
        "id": "china-real-estate-investment-yoy",
        "region": "CN",
        "name_bg": "Инвестиции в имоти — натрупани от началото на годината (YoY %)",
        "name_en": "Real Estate Development Investment YoY (cumulative YTD, %)",
        "lens": ["property"],
        "peer_group": "investment",
        "tags": [],
        "transform": "level",
        "is_rate": True,
        "historical_start": "2007-02-01",
        "release_schedule": "monthly",
        "typical_release": "15-20_of_month",
        "revision_prone": False,
        "narrative_hint": "НБС (чрез chinadata.live). ВНИМАНИЕ: това е темп от началото на годината (YTD), не месечен; през годината се изглажда и се нулира всеки януари/февруари. Дълбок и устойчив спад.",
    },
    "CN_PROPERTY_SALES_YOY": {
        "source": "chinadata_live",
        "id": "china-property-sales-area@cum_yoy",
        "region": "CN",
        "name_bg": "Продажби на жилища (площ) — YTD спрямо година по-рано (%)",
        "name_en": "New Commercial Property Sales Area YTD vs same period last year (%)",
        "lens": ["property"],
        "peer_group": "housing",
        "tags": [],
        "transform": "level",
        "is_rate": True,
        "historical_start": "2019-02-01",
        "release_schedule": "monthly",
        "typical_release": "15-20_of_month",
        "revision_prone": False,
        "narrative_hint": "ИЗЧИСЛЕНО от кумулативните YTD нива на НБС в chinadata.live (няма официален готов темп там): стойност за месеца делено на същия месец година по-рано. Основата не е ревизирана, затова може да се различава от официалния сравним темп на НБС. YTD, не месечен.",
    },

    # ─── ПРОЛЕТР4 (подобрение на състава, 26.11.2026): външна леща и нови серии през FRED ───
    "CN_REER": {
        "source": "fred_csv",
        "id": "RBCNBIS",
        "region": "CN",
        "name_bg": "Реален ефективен курс на юана (индекс, BIS)",
        "name_en": "China Real Broad Effective Exchange Rate (BIS)",
        "lens": ["external"],
        "peer_group": "currency",
        "tags": [],
        "transform": "level",
        "is_rate": False,
        "historical_start": "2000-01-01",
        "release_schedule": "monthly",
        "typical_release": "месечно (BIS, през FRED RBCNBIS)",
        "revision_prone": True,
        "narrative_hint": "Реален ефективен курс спрямо широка кошница партньори (2020=100). Нагоре = по-скъп юан = по-слаба ценова конкурентност на износа.",
    },
    "CN_INTERBANK_3M": {
        "source": "fred_csv",
        "id": "IR3TIB01CNM156N",
        "region": "CN",
        "name_bg": "3-месечен междубанков лихвен процент (%)",
        "name_en": "China 3-Month Interbank Rate (%)",
        "lens": ["credit"],
        "peer_group": "rates",
        "tags": [],
        "transform": "level",
        "is_rate": True,
        "historical_start": "2002-01-01",
        "release_schedule": "monthly",
        "typical_release": "месечно (OECD MEI, през FRED IR3TIB01CNM156N)",
        "revision_prone": False,
        "narrative_hint": "Цената на краткосрочната междубанкова ликвидност. По-ниска = по-евтини пари (easing), по-висока = затягане.",
    },
    # ── ПРОЛЕТР4, втората вълна (26.11.2026, реш. Ц. КТ-1 и КТ-2 „Да, приемам ги.“) ──
    "CN_CORE_CPI_YOY": {
        "source": "akshare",
        "id": "core_cpi_yoy",
        "region": "CN",
        "name_bg": "Базисна инфлация, без храни и енергия (г/г, %)",
        "name_en": "China Core CPI ex Food and Energy (YoY %)",
        "lens": ["inflation"],
        "peer_group": "cpi",
        "tags": [],
        "transform": "level",
        "is_rate": True,
        "historical_start": "2021-01-01",
        "release_schedule": "monthly",
        "typical_release": "месечно (NBS, през akshare macro_china_nbs_nation)",
        "revision_prone": False,
        "narrative_hint": "Цените без храните и енергията. Ниско и падащо значи слабо търсене и дефлационен натиск. Историята в NBS е от 2021 (кошницата 2021-2025 и 2026-).",
    },
    "CN_CONS_CONF": {
        "source": "akshare",
        "id": "consumer_confidence",
        "region": "CN",
        "name_bg": "Доверие на потребителите (индекс)",
        "name_en": "China Consumer Confidence Index",
        "lens": ["growth"],
        "peer_group": "sentiment",
        "tags": [],
        "transform": "level",
        "is_rate": False,
        "historical_start": "2007-01-01",
        "release_schedule": "monthly",
        "typical_release": "месечно (NBS, през eastmoney)",
        "revision_prone": False,
        "narrative_hint": "Анкетата на NBS. Над 100 е оптимизъм; след 2022 стои ниско, затова се чете спрямо собствената норма.",
    },
    "CN_PMI_EMPLOYMENT": {
        "source": "chinadata_live",
        "id": "china-pmi-employment",
        "region": "CN",
        "name_bg": "PMI на индустрията: заетост (индекс)",
        "name_en": "China Manufacturing PMI: Employment",
        "lens": ["labor"],
        "peer_group": "employment",
        "tags": [],
        "transform": "level",
        "is_rate": False,
        "historical_start": "2005-01-01",
        "release_schedule": "monthly",
        "typical_release": "месечно (NBS, през chinadata.live)",
        "revision_prone": False,
        "narrative_hint": "Подиндексът за заетостта в PMI на NBS. Над 50 фабриките наемат, под 50 съкращават. Месечна мярка за заетост Китай не публикува.",
    },
    "CN_DISP_INCOME_YOY": {
        "source": "akshare",
        "id": "disp_income_cum_yoy",
        "region": "CN",
        "name_bg": "Разполагаем доход на човек (натрупан от началото на годината, г/г, %)",
        "name_en": "China Per-Capita Disposable Income (YTD YoY %)",
        "lens": ["labor"],
        "peer_group": "wages",
        "tags": [],
        "transform": "level",
        "is_rate": True,
        "historical_start": "2013-01-01",
        "release_schedule": "quarterly",
        "typical_release": "тримесечно, с БВП (NBS, през akshare macro_china_nbs_nation)",
        "revision_prone": False,
        "narrative_hint": "Официалният натрупан ръст на доходите на домакинствата (NBS). Месечни заплати Китай не дава; заплатната част е в същата таблица на NBS.",
    },
    "CN_CORP_SPREAD_3Y": {
        "source": "akshare",
        "id": "aaa_spread_3y",
        "region": "CN",
        "name_bg": "Кредитен спред: AAA бележки минус ДЦК, 3 г. (б.т.)",
        "name_en": "China AAA MTN minus CGB Spread, 3Y (bp)",
        "lens": ["credit"],
        "peer_group": "spreads",
        "tags": [],
        "transform": "level",
        "is_rate": True,
        "historical_start": "2016-01-01",
        "release_schedule": "daily",
        "typical_release": "дневно (ChinaBond, през akshare bond_china_yield)",
        "revision_prone": False,
        "narrative_hint": "Колко повече плащат добрите фирми от държавата за заем за 3 години. Разширяване значи страх на пазара.",
    },
    "CN_FISCAL_REV_YOY": {
        "source": "akshare",
        "id": "fiscal_revenue_cum_yoy",
        "region": "CN",
        "name_bg": "Бюджетни приходи (натрупани, г/г, %)",
        "name_en": "China General Public Budget Revenue (YTD YoY %)",
        "lens": ["fiscal"],
        "peer_group": "budget",
        "tags": [],
        "transform": "level",
        "is_rate": True,
        "historical_start": "2008-01-01",
        "release_schedule": "monthly",
        "typical_release": "месечно (МФ, през eastmoney)",
        "revision_prone": False,
        "narrative_hint": "Приходите на общия бюджет от началото на годината спрямо година по-рано. Само за показване.",
    },
    "CN_FISCAL_EXP_YOY": {
        "source": "chinadata_live",
        "id": "china-fiscal-expenditure@cum_yoy",
        "region": "CN",
        "name_bg": "Бюджетни разходи (натрупани, г/г, %)",
        "name_en": "China General Public Budget Expenditure (YTD YoY %)",
        "lens": ["fiscal"],
        "peer_group": "budget",
        "tags": [],
        "transform": "level",
        "is_rate": True,
        "historical_start": "2018-01-01",
        "release_schedule": "monthly",
        "typical_release": "месечно (МФ, през chinadata.live)",
        "revision_prone": False,
        "narrative_hint": "Разходите на общия бюджет от началото на годината спрямо година по-рано, смятани от натрупаните нива. Само за показване.",
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


def series_by_tag(tag: str) -> list[dict]:
    """Връща всички серии, носещи даден tag (non_consensus/structural/...), с _key."""
    result = []
    for key, entry in SERIES_CATALOG.items():
        if tag in entry.get("tags", []):
            e = dict(entry)
            e["_key"] = key
            result.append(e)
    return result


def series_by_peer_group(peer_group: str) -> list[dict]:
    """Връща всички серии от даден peer_group, с добавен _key."""
    result = []
    for key, entry in SERIES_CATALOG.items():
        if entry.get("peer_group") == peer_group:
            e = dict(entry)
            e["_key"] = key
            result.append(e)
    return result
