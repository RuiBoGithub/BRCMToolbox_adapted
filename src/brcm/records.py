"""Thermal-model input records corresponding to MATLAB value classes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

import numpy as np

from .constants import Constants, matlab_number
from .exceptions import ValidationError
from .geometry import polygon_area_3d, polygon_normal, vertices_matrix
from .primitives import Vertex
from .validation import (
    check_free_description,
    check_identifier,
    check_identifier_adjacent,
    check_special_identifier,
    check_value,
    check_zone_group,
    require_positive,
)


def _text(value: str | float | int) -> str:
    return matlab_number(value) if isinstance(value, (float, int)) and not isinstance(value, bool) else str(value)


@dataclass(eq=True)
class Zone:
    KEY: ClassVar[str] = "Z"
    identifier: str
    description: str
    area: str
    volume: str
    group: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.identifier = check_identifier(self.identifier, self.KEY)
        self.description = check_free_description(self.description)
        self.area = require_positive(_text(self.area), "area")
        self.volume = require_positive(_text(self.volume), "volume")
        self.group = check_zone_group(",".join(self.group) if isinstance(self.group, list) else str(self.group))


@dataclass(eq=True)
class Material:
    KEY: ClassVar[str] = "M"
    identifier: str
    description: str
    specific_heat_capacity: str
    specific_thermal_resistance: str
    density: str
    R_value: str

    def __post_init__(self) -> None:
        self.identifier = check_identifier(self.identifier, self.KEY)
        self.description = check_free_description(self.description)
        fields = ("specific_heat_capacity", "specific_thermal_resistance", "density", "R_value")
        for name in fields:
            setattr(self, name, check_value(_text(getattr(self, name)), True))
        massless = self.R_value not in (Constants.EMPTY, Constants.NULL)
        if massless:
            require_positive(self.R_value, "R_value", allow_expression=True, allow_zero=True)
        else:
            require_positive(self.specific_heat_capacity, "specific_heat_capacity", allow_expression=True)
            require_positive(self.specific_thermal_resistance, "specific_thermal_resistance", allow_expression=True)
            require_positive(self.density, "density", allow_expression=True)


@dataclass(eq=True)
class Construction:
    KEY: ClassVar[str] = "C"
    identifier: str
    description: str
    material_identifiers: list[str]
    thickness: list[str]
    conv_coeff_adjacent_A: str
    conv_coeff_adjacent_B: str

    def __post_init__(self) -> None:
        self.identifier = check_identifier(self.identifier, self.KEY)
        self.description = check_free_description(self.description)
        self.material_identifiers = [check_identifier(item, Material.KEY) for item in self.material_identifiers]
        self.thickness = [check_value(_text(item), True) for item in self.thickness]
        if len(self.material_identifiers) != len(self.thickness):
            raise ValidationError("Material and thickness lists must have equal length")
        self.conv_coeff_adjacent_A = require_positive(
            _text(self.conv_coeff_adjacent_A), "conv_coeff_adjacent_A", allow_expression=True, allow_zero=True
        )
        self.conv_coeff_adjacent_B = require_positive(
            _text(self.conv_coeff_adjacent_B), "conv_coeff_adjacent_B", allow_expression=True, allow_zero=True
        )


@dataclass(eq=True)
class NoMassConstruction:
    KEY: ClassVar[str] = "NMC"
    identifier: str
    description: str
    U_value: str

    def __post_init__(self) -> None:
        self.identifier = check_identifier(self.identifier, self.KEY)
        self.description = check_free_description(self.description)
        self.U_value = require_positive(_text(self.U_value), "U_value", allow_expression=True)


@dataclass(eq=True)
class Window:
    KEY: ClassVar[str] = "W"
    identifier: str
    description: str
    glass_area: str
    frame_area: str
    U_value: str
    SHGC: str

    def __post_init__(self) -> None:
        self.identifier = check_identifier(self.identifier, self.KEY)
        self.description = check_free_description(self.description)
        self.glass_area = require_positive(_text(self.glass_area), "glass_area", allow_expression=True, allow_zero=True)
        self.frame_area = require_positive(_text(self.frame_area), "frame_area", allow_expression=True, allow_zero=True)
        self.U_value = require_positive(_text(self.U_value), "U_value", allow_expression=True)
        self.SHGC = require_positive(_text(self.SHGC), "SHGC", allow_expression=True, allow_zero=True)
        try:
            shgc = float(self.SHGC)
        except ValueError:
            pass
        else:
            if shgc > 1:
                raise ValidationError("SHGC must be between zero and one")


@dataclass(eq=True)
class Parameter:
    identifier: str
    description: str
    value: str

    def __post_init__(self) -> None:
        self.identifier = check_special_identifier(self.identifier)
        self.description = check_free_description(self.description)
        self.value = require_positive(_text(self.value), "parameter value", allow_zero=True)


@dataclass(eq=True)
class BuildingElement:
    KEY: ClassVar[str] = "B"
    identifier: str
    description: str
    construction_identifier: str
    adjacent_A: str
    adjacent_B: str
    window_identifier: str
    area: str
    vertices: tuple[Vertex, ...] | str = field(default_factory=tuple)

    def __post_init__(self) -> None:
        self.identifier = check_identifier(self.identifier, self.KEY)
        self.description = check_free_description(self.description)
        if self.construction_identifier != Constants.NULL:
            try:
                check_identifier(self.construction_identifier, Construction.KEY)
            except ValidationError:
                check_identifier(self.construction_identifier, NoMassConstruction.KEY)
        self.adjacent_A = check_identifier_adjacent(self.adjacent_A)
        self.adjacent_B = check_identifier_adjacent(self.adjacent_B)
        if not any(value.startswith(Zone.KEY) for value in (self.adjacent_A, self.adjacent_B)) and Constants.NULL not in (self.adjacent_A, self.adjacent_B):
            raise ValidationError("At least one adjacent identifier must be a zone")
        if self.window_identifier in (Constants.NAN, Constants.ZERO):
            self.window_identifier = Constants.EMPTY
        elif self.window_identifier != Constants.NULL and self.window_identifier:
            self.window_identifier = check_identifier(self.window_identifier, Window.KEY)
            if Constants.AMBIENT_IDENTIFIER not in (self.adjacent_A, self.adjacent_B):
                raise ValidationError("A window requires an ambient-adjacent building element")
        raw_area = _text(self.area)
        self.area = Constants.EMPTY if raw_area in (Constants.EMPTY, Constants.NAN) else check_value(raw_area, False)
        if self.area == Constants.EMPTY and not isinstance(self.vertices, tuple):
            raise ValidationError("Area and vertices cannot both be empty")
        if self.area not in (Constants.EMPTY, Constants.NULL):
            require_positive(self.area, "area")
        if isinstance(self.vertices, tuple) and self.vertices:
            computed = self.compute_area()
            if self.area == Constants.EMPTY:
                self.area = matlab_number(computed)
            elif abs(computed - float(self.area)) >= Constants.TOL_AREA:
                raise ValidationError("Specified and vertex-derived areas are inconsistent")

    def vertices_to_matrix(self) -> np.ndarray:
        return vertices_matrix(self.vertices if isinstance(self.vertices, tuple) else tuple())

    def vertices2Matrix(self) -> np.ndarray:
        return self.vertices_to_matrix()

    def compute_normal(self) -> np.ndarray:
        if not isinstance(self.vertices, tuple):
            raise ValidationError("Building element has no numeric vertices")
        return polygon_normal(self.vertices)

    def computeNormal(self) -> np.ndarray:
        return self.compute_normal()

    def is_horizontal(self) -> bool:
        try:
            normal = self.compute_normal()
        except ValidationError:
            return False
        return bool(np.hypot(normal[0], normal[1]) < Constants.TOL_NORMAL)

    def isHorizontal(self) -> bool:
        return self.is_horizontal()

    def compute_projection_z(self) -> float:
        matrix = self.vertices_to_matrix()
        return float(np.max(matrix[2]) - np.min(matrix[2]))

    def compute_area(self) -> float:
        if not isinstance(self.vertices, tuple):
            raise ValidationError("Building element has no numeric vertices")
        return polygon_area_3d(self.vertices)

    def computeArea(self) -> float:
        return self.compute_area()

    def compute_center(self) -> np.ndarray:
        return np.mean(self.vertices_to_matrix(), axis=1, keepdims=True)
