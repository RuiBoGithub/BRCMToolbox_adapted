"""Small data holders corresponding to MATLAB auxiliary classes."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass(eq=True)
class Identifier:
    x: list[str] = field(default_factory=list)
    q: list[str] = field(default_factory=list)
    u: list[str] = field(default_factory=list)
    v: list[str] = field(default_factory=list)
    y: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)


@dataclass(eq=True)
class Vertex:
    x: float
    y: float
    z: float

    def as_column(self) -> np.ndarray:
        return np.asarray([[self.x], [self.y], [self.z]], dtype=float)

    def vertex2ColumnVec(self) -> np.ndarray:  # MATLAB-compatible alias
        return self.as_column()


@dataclass(eq=True)
class BoundaryCondition:
    identifier_1: str = ""
    identifier_2: str = ""
    value: float = 0.0

