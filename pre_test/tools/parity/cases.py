"""Shared case-name resolution for operational parity tools."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


PRE_TEST = Path(__file__).resolve().parents[2]
REPOSITORY_ROOT = PRE_TEST.parent


@dataclass(frozen=True)
class ParityCase:
    name: str
    idf: Path
    output: Path


def resolve_case(case_name: str) -> ParityCase:
    """Resolve a safe case name to its single source IDF and output root."""

    if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]*", case_name):
        raise ValueError(f"Invalid parity case name: {case_name!r}")
    idf = (PRE_TEST / "tests" / "fixtures" / "energyplus" / f"{case_name}.idf").resolve()
    output = (PRE_TEST / "outputs" / "parity" / case_name).resolve()
    if not idf.is_file():
        raise FileNotFoundError(f"Parity case IDF does not exist: {idf}")
    return ParityCase(case_name, idf, output)
