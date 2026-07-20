"""Continuous thermal RC submodel (kept separate from BuildingModel)."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .primitives import BoundaryCondition


@dataclass
class ThermalModel:
    """Dense continuous model ``dx/dt = A x + Bq q``.

    ``A`` has units s^-1, ``Bq`` K/J, and diagonal ``Xcap`` J/K.  Rows and
    columns follow ``state_identifiers``; Bq columns follow
    ``heat_flux_identifiers``.
    """

    A: np.ndarray
    Bq: np.ndarray
    Xcap: np.ndarray
    state_identifiers: list[str]
    heat_flux_identifiers: list[str]
    boundary_conditions: dict[str, list[BoundaryCondition]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.A = np.asarray(self.A, dtype=float)
        self.Bq = np.asarray(self.Bq, dtype=float)
        self.Xcap = np.asarray(self.Xcap, dtype=float)
        n = len(self.state_identifiers)
        if self.A.shape != (n, n) or self.Bq.shape != (n, n) or self.Xcap.shape != (n, n):
            raise ValueError("Thermal model matrix dimensions do not match identifiers")
        if len(self.heat_flux_identifiers) != n:
            raise ValueError("Heat-flux identifier count does not match Bq columns")

    @property
    def identifiers(self) -> dict[str, list[str]]:
        return {"x": self.state_identifiers, "q": self.heat_flux_identifiers}
