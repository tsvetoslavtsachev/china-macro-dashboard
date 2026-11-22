# -*- coding: utf-8 -*-
"""ИЛЮ3 Е2 (23.11.2026): akshare е закована в requirements.txt.

От 14.11.2026 GitHub теглеше последната akshare (1.20.44, после 1.20.65) и девет серии плюс
LPR падаха мълчаливо при зелени ходове. Версията се вдига нарочно, след
scripts/akshare_probe.py с 20 от 20 под новата версия."""
import re
from pathlib import Path

REQ = Path(__file__).resolve().parents[1] / "requirements.txt"


def test_akshare_is_pinned_to_an_exact_version():
    lines = [x.strip() for x in REQ.read_text(encoding="utf-8").splitlines()
             if x.strip().lower().startswith("akshare")]
    assert len(lines) == 1 and re.fullmatch(r"akshare==\d+\.\d+\.\d+", lines[0]), lines


def test_the_probe_exists_for_raising_it():
    assert (REQ.parent / "scripts" / "akshare_probe.py").exists()
