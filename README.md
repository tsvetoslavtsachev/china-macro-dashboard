# 🇨🇳 China Macro Dashboard

Седмичен икономически briefing за Китай — автоматично генериран от Python.

По подобие на [`us-macro-dashboard`](https://github.com/tsvetoslavtsachev/us-macro-dashboard) и [`eu-macro-dashboard`](https://github.com/tsvetoslavtsachev/eu-macro-dashboard).

---

## Структура

```
china-macro-dashboard/
├── run.py                    # Entry point — всички команди
├── config.py                 # Конфигурация (weights, regimes, paths)
├── catalog/
│   └── series.py             # Декларативен каталог на 25 серии
├── sources/
│   ├── _base.py              # Базов adapter (cache, TTL, fetch)
│   ├── worldbank.py          # World Bank Indicators API (17 серии)
│   ├── imf_ifs.py            # IMF IFS via DBnomics (6 серии)
│   └── akshare_cn.py         # AkShare / НБС (2 серии)
├── modules/
│   ├── growth.py             # Растеж и активност
│   ├── inflation.py          # Инфлация и цени
│   ├── labor.py              # Пазар на труда
│   ├── credit.py             # Монетарна политика и кредит
│   └── property.py           # Имоти и търговия
├── export/
│   ├── weekly_briefing.py    # HTML briefing renderer
│   ├── briefing_context.py   # Markdown context за LLM анализ
│   └── data_status.py        # Data status report
├── output/                   # Генерирани файлове (gitignored)
└── data/                     # Локален cache (gitignored)
```

---

## Команди

```bash
# Модулен summary — lens scores + composite
python run.py --modules

# HTML briefing (отваря в браузъра)
python run.py --briefing

# HTML briefing без браузър
python run.py --briefing --no-browser

# Markdown context за LLM анализ (ChatGPT/Claude)
python run.py --export-context

# Data status — кои серии са кешувани
python run.py --status

# Force-refresh на всички серии
python run.py --modules --refresh

# Smart refresh (само stale серии)
python run.py --refresh-only
```

---

## Данни — 25 серии от 3 источника

| Lens | Серии | Источник | Честота |
|------|-------|----------|---------|
| Растеж | GDP растеж, индустрия, услуги, CAPEX, manufacturing | World Bank | Годишни |
| Инфлация | CPI, PPI, GDP дефлатор | IMF IFS + AkShare | Месечни |
| Труд | Безработица, младежка безработица, participation rate | World Bank | Годишни |
| Кредит | Policy rate, lending rate, deposit rate, M2/GDP, кредит/GDP, CNY/USD | IMF IFS + World Bank | Месечни + Годишни |
| Имоти | Цени на жилища, FDI, текуща сметка, exports, fixed capital | AkShare + World Bank | Месечни + Годишни |

---

## Lens-ове и тегла

| Lens | Тегло |
|------|-------|
| Растеж и активност | 30% |
| Монетарна политика и кредит | 20% |
| Инфлация и цени | 20% |
| Имоти и търговия | 15% |
| Пазар на труда | 15% |

---

## Macro Score Режими

| Score | Режим |
|-------|-------|
| 75–100 | СИЛНА ИКОНОМИКА |
| 60–75 | УМЕРЕН РАСТЕЖ |
| 45–60 | СМЕСЕНИ СИГНАЛИ |
| 30–45 | РЕЦЕСИОНЕН |
| 0–30 | КРИЗА |

---

## Бележки за данните

> **Китайските официални данни изискват внимателна интерпретация.**

- **Официалната безработица** (~5%) не включва ~300 млн. мигрантски работници. Реалната е значително по-висока.
- **Младежката безработица** (16-24 г.) беше спряна от НБС юли–декември 2023 след рекорд 21.3%.
- **GDP данните** са годишни (World Bank). Месечни данни за Китай са ограничено достъпни в международни бази.
- **PPI от IMF IFS** е само до декември 2022. AkShare дава по-актуални данни от НБС.
- **FDI** срина се до ~0.1% от GDP (2024) — геополитически de-risking.
- **GDP дефлаторът** е отрицателен от 2023 — широка дефлация.

---

## Автоматично обновяване

Repo-то е настроено за **седмично обновяване** чрез GitHub Actions (`.github/workflows/weekly_update.yml`).

Workflow-ът:
1. Стартира всеки понеделник в 06:00 UTC
2. Fetch-ва stale серии от всички 3 источника
3. Генерира HTML briefing и Markdown context
4. Commit-ва новите файлове в `output/`

За **ръчно обновяване**: `python run.py --briefing --refresh`

---

## Инсталация

```bash
pip install requests pandas akshare
python run.py --status --refresh  # Първоначален fetch
python run.py --briefing           # Генерирай briefing
```

---

*Данни: World Bank Indicators API · IMF IFS via DBnomics · AkShare/НБС*
