# Research Journal — China

Тази директория държи структурирани markdown бележки за наблюдения, хипотези и
изводи от аналитичния workflow върху China dashboard-а.

## Защо е почти празна в публичното repo?

По дизайн. Публичното repo съдържа **рамката** — структура по теми, шаблон за
запис, генератор на индекс. Самите записи са частни research бележки и стоят
извън git (виж `.gitignore`).

Ако форкнеш проекта, твоите `journal/credit/*.md`, `journal/property/*.md` и т.н.
остават на твоята машина.

## Структура

По една поддиректория на тема — огледало на 5-те China лещи + аналитични теми:

- `growth/` — БВП, промишлено производство, retail, FAI, PMI
- `inflation/` — CPI, PPI, GDP дефлатор, дефлация
- `labor/` — заетост, мигрантски работници, младежка безработица
- `credit/` — M2, TSF, LPR, BIS credit-to-GDP, монетарна трансмисия
- `property/` — цени на жилища, имотен сектор, външна търговия
- `analogs/` — находки от historical analog engine-а
- `regime/` — преходи между макро режими
- `methodology/` — рамкови бележки, калибрационни решения (напр. composite re-base)

## Създаване на запис

Копирай `_template.md` или ползвай helper-а:

```python
from scripts._utils import save_journal_entry

save_journal_entry(
    topic="inflation",
    title="PPI рефлация изпреварва CPI",
    body="## Въпрос\n...\n## Извод\n...",
    tags=["ppi", "deflation"],
    status="finding",  # или open_question / hypothesis / decision
)
```

## Индекс

Построй локален индекс (не се commit-ва):

```
python scripts/build_journal_index.py
```

Записва `journal/README.md` — таблица с всички записи, групирани по тема. Този
файл е в `.gitignore`, защото заглавията често носят контекст, който не би
искал публичен.
