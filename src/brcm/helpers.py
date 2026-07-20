"""Identifier, ordering, and orientation helpers."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import TypeVar

import numpy as np

from .exceptions import ValidationError

T = TypeVar("T")


def get_id_index(identifiers: Sequence[str], identifier: str, *, matlab_index: bool = False) -> int:
    """Return the unique index; Python is 0-based unless explicitly requested."""

    matches = [index for index, current in enumerate(identifiers) if current == identifier]
    if len(matches) != 1:
        raise ValidationError(f"Expected exactly one occurrence of identifier {identifier!r}")
    return matches[0] + (1 if matlab_index else 0)


def getIdIndex(identifiers: Sequence[str], identifier: str) -> int:
    """Python-indexed compatibility spelling of MATLAB ``getIdIndex``."""

    return get_id_index(identifiers, identifier)


def reshape_vector(values: Iterable[T], mode: str) -> np.ndarray:
    items = list(values)
    array = np.asarray(items, dtype=object)
    if mode == "col":
        return array.reshape((len(items), 1))
    if mode == "row":
        return array.reshape((1, len(items)))
    raise ValidationError("reshape mode must be 'row' or 'col'")


def matlab_unique(values: Iterable[T]) -> list[T]:
    """MATLAB legacy ``unique`` semantics used here: sorted unique values."""

    return sorted(set(values))


def matlab_setdiff(left: Iterable[T], right: Iterable[T]) -> list[T]:
    return sorted(set(left).difference(right))


def matlab_intersect(left: Iterable[T], right: Iterable[T]) -> list[T]:
    return sorted(set(left).intersection(right))

