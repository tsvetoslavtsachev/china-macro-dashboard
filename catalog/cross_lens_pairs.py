"""
catalog/cross_lens_pairs.py
===========================
Декларативен config на China-специфични cross-lens divergence pairs.

Всяка pair е икономическа теза, проверявана чрез съпоставка на breadth между
два "slot"-а. Всеки slot е колекция от peer_groups, по избор с invert (ако ↓ на
peer_group трябва да се чете като ↑ на темата — напр. падащи лихви = разхлабване).

Структура (идентична на US/EU — analysis/divergence.py я консумира):
  id, name_bg, question_bg, narrative
  slot_a / slot_b: {lens, peer_groups, invert, label}
  interpretations: {both_up, both_down, a_up_b_down, a_down_b_up, transition}

China-специфика (вместо US labor/inflation фокус):
  1. Кредит × Реален сектор  → debt-deflation / liquidity trap
  2. Монетарна × Инфлация    → policy trap (разхлабване в дефлация)
  3. Външно × Вътрешно търсене → export-dependence / rebalancing

⚠ Данни caveat: China peer_groups смесват годишни (World Bank, latest ~2024) и
месечни (akshare/PBoC) серии. Pairs-ите умишлено стъпват на ПРЕДИМНО МЕСЕЧНИ,
свежи peer_groups (rates, credit_depth, trade, hard_activity, cpi). housing има
само 1 серия → влиза като peer_group, но breadth-ът се пропуска докато не станат
≥2 (auto-включва се при разширяване на каталога).
"""
from __future__ import annotations


CROSS_LENS_PAIRS: list[dict] = [
    # ═══════════════════════════════════════════════════════
    # 1. Кредит × Реален сектор — debt-deflation / liquidity trap
    # ═══════════════════════════════════════════════════════
    {
        "id": "credit_real_economy",
        "name_bg": "Кредитна експанзия × Реален сектор",
        "question_bg": "Превръща ли се кредитът в реална инвестиция, или ликвидността засяда (debt-deflation)?",
        "narrative": (
            "Нормално нов кредит (TSF, нови заеми, M2) захранва инвестиции и имоти. "
            "Ако кредитът се разширява, но реалната инвестиция се свива — ликвидността "
            "не достига икономиката (Fisher debt-deflation / balance-sheet recession): "
            "домакинства и фирми гасят дълг вместо да инвестират."
        ),
        "slot_a": {
            "lens": "credit",
            "peer_groups": ["credit_depth"],
            "invert": {},
            "label": "Кредитна експанзия",
        },
        "slot_b": {
            "lens": "property",
            "peer_groups": ["housing", "investment"],
            "invert": {},
            "label": "Имоти и инвестиции",
        },
        "interpretations": {
            "both_up": "Кредитът се трансформира в реална инвестиция — здрав credit impulse, трансмисията работи.",
            "both_down": "Синхронно свиване — и кредит, и реален сектор се свиват. Deleveraging recession.",
            "a_up_b_down": "Debt-deflation сигнал — кредитът се разширява, но инвестициите се свиват. Liquidity trap: ликвидността не достига реалната икономика (balance-sheet deleveraging).",
            "a_down_b_up": "Реален сектор изпреварва кредита — инвестиции растат без нов кредит (вътрешно финансиране / fiscal импулс).",
            "transition": "Преход — кредит и реален сектор не са ясно aligned; чакай следващ TSF/FAI print.",
        },
    },

    # ═══════════════════════════════════════════════════════
    # 2. Монетарна политика × Инфлация — policy trap
    # ═══════════════════════════════════════════════════════
    {
        "id": "monetary_inflation_trap",
        "name_bg": "Монетарно разхлабване × Инфлация",
        "question_bg": "Води ли разхлабването на PBoC до инфлация, или политиката бута в дефлация (policy trap)?",
        "narrative": (
            "Падащи лихви (policy rate, LPR, lending) = разхлабване. Нормално → инфлацията "
            "се покачва. Ако PBoC разхлабва агресивно, но инфлацията пада / е в дефлация — "
            "монетарната трансмисия е счупена (Japan-style liquidity trap): при balance-sheet "
            "deleveraging по-ниските лихви не вдигат цените."
        ),
        "slot_a": {
            "lens": "credit",
            "peer_groups": ["rates"],
            "invert": {"rates": True},  # падащи лихви = разхлабване (↑ на темата)
            "label": "Монетарно разхлабване",
        },
        "slot_b": {
            "lens": "inflation",
            "peer_groups": ["cpi"],
            "invert": {},
            "label": "Инфлация",
        },
        "interpretations": {
            "both_up": "Разхлабване + покачваща се инфлация — нормална monetary transmission; политиката работи.",
            "both_down": "Затягане + дезинфлация — рестриктивна политика хапе (нетипично за текущия Китай).",
            "a_up_b_down": "Policy trap — PBoC разхлабва, но инфлацията пада/е в дефлация. Трансмисията е счупена (Japan-style): по-ниските лихви не вдигат цените при deleveraging.",
            "a_down_b_up": "Затягане при покачваща се инфлация — PBoC зад кривата (рядко за Китай в момента).",
            "transition": "Преход — посоките на политиката и инфлацията не са ясно aligned.",
        },
    },

    # ═══════════════════════════════════════════════════════
    # 3. Външно търсене × Вътрешна активност — export-dependence
    # ═══════════════════════════════════════════════════════
    {
        "id": "external_domestic_balance",
        "name_bg": "Външно търсене × Вътрешна активност",
        "question_bg": "Балансиран ли е растежът, или Китай зависи от износа при слабо вътрешно търсене?",
        "narrative": (
            "Износ/внос/FX резерви = външно търсене. Индустриално производство + продажби "
            "на дребно = вътрешна активност. Ако износът носи растежа, докато вътрешното "
            "търсене е слабо — небалансирано възстановяване, уязвимо на тарифи и външни шокове. "
            "Целта на политиката е обратното (rebalancing към потребление)."
        ),
        "slot_a": {
            "lens": "property",
            "peer_groups": ["trade"],
            "invert": {},
            "label": "Външно търсене",
        },
        "slot_b": {
            "lens": "growth",
            "peer_groups": ["hard_activity"],
            "invert": {},
            "label": "Вътрешна активност",
        },
        "interpretations": {
            "both_up": "Балансиран растеж — и износ, и вътрешно търсене се разширяват.",
            "both_down": "Синхронно свиване — и външно, и вътрешно търсене отслабват. Broad-based забавяне.",
            "a_up_b_down": "Export-dependence — износът носи растежа, докато вътрешното търсене е слабо. Небалансирано възстановяване, уязвимо на тарифи/външни шокове.",
            "a_down_b_up": "Вътрешно-водено — вътрешното търсене изпреварва износа (rebalancing към потребление; целта на политиката).",
            "transition": "Преход — външно и вътрешно търсене не са ясно aligned.",
        },
    },
]


# ============================================================
# VALIDATION (идентична логика на US/EU)
# ============================================================

REQUIRED_PAIR_FIELDS = frozenset({
    "id", "name_bg", "question_bg", "narrative",
    "slot_a", "slot_b", "interpretations",
})

REQUIRED_SLOT_FIELDS = frozenset({"lens", "peer_groups", "invert", "label"})

REQUIRED_INTERPRETATION_STATES = frozenset({
    "both_up", "both_down", "a_up_b_down", "a_down_b_up", "transition",
})


def validate_pairs(pairs: list[dict] = None) -> list[str]:
    """Валидира config-а. Връща списък с грешки (празен ако всичко OK)."""
    if pairs is None:
        pairs = CROSS_LENS_PAIRS

    errors: list[str] = []
    seen_ids: set[str] = set()

    for i, pair in enumerate(pairs):
        prefix = f"pair[{i}]"
        missing = REQUIRED_PAIR_FIELDS - set(pair.keys())
        if missing:
            errors.append(f"{prefix}: missing fields {missing}")
            continue

        pid = pair["id"]
        if pid in seen_ids:
            errors.append(f"{prefix}: duplicate id '{pid}'")
        seen_ids.add(pid)

        for slot_name in ("slot_a", "slot_b"):
            slot = pair[slot_name]
            missing_slot = REQUIRED_SLOT_FIELDS - set(slot.keys())
            if missing_slot:
                errors.append(f"{prefix}.{slot_name}: missing fields {missing_slot}")

        interp_states = set(pair["interpretations"].keys())
        missing_interp = REQUIRED_INTERPRETATION_STATES - interp_states
        if missing_interp:
            errors.append(f"{prefix}.interpretations: missing states {missing_interp}")

    return errors
