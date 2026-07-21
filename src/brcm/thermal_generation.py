"""MATLAB-compatible one-state-per-mass-layer thermal RC generation."""

from __future__ import annotations

import math

import numpy as np

from .constants import Constants
from .exceptions import ValidationError
from .primitives import BoundaryCondition
from .records import Construction, Material, NoMassConstruction, Zone
from .thermal_data import ThermalModelData
from .thermal_model import ThermalModel


def _require_finite_positive(value: float, label: str, *, zero: bool = False) -> None:
    if not math.isfinite(value) or value < 0 or (not zero and value == 0):
        raise ValidationError(f"{label} must be finite and {'non-negative' if zero else 'positive'}")


def check_thermal_model_data_consistency(data: ThermalModelData) -> None:
    """Port of consistency checks that are observable during RC generation."""
    if not data.zones or not data.building_elements or not data.constructions or not data.materials:
        raise ValidationError("Thermal model data are incomplete")
    data.validate_references()
    zone_ids = {z.identifier for z in data.zones}
    construction_ids = {c.identifier for c in data.constructions}
    nomass_ids = {c.identifier for c in data.nomass_constructions}
    material_ids = {m.identifier for m in data.materials}
    window_ids = {w.identifier for w in data.windows}
    for zone in data.zones:
        _require_finite_positive(data.eval_str(zone.area), f"{zone.identifier}.area")
        _require_finite_positive(data.eval_str(zone.volume), f"{zone.identifier}.volume")
    for construction in data.constructions:
        if len(construction.material_identifiers) != len(construction.thickness):
            raise ValidationError(f"{construction.identifier} has unequal material/thickness counts")
        if not construction.material_identifiers or any(x not in material_ids for x in construction.material_identifiers):
            raise ValidationError(f"{construction.identifier} references missing materials")
        for thickness in construction.thickness:
            # MATLAB permits zero thickness (commonly used for R-value-only layers).
            _require_finite_positive(data.eval_str(thickness), f"{construction.identifier}.thickness", zero=True)
    for element in data.building_elements:
        if element.construction_identifier not in construction_ids | nomass_ids:
            raise ValidationError(f"{element.identifier} references a missing construction")
        if not any(adj in zone_ids for adj in (element.adjacent_A, element.adjacent_B)):
            raise ValidationError(f"{element.identifier} must be adjacent to at least one zone")
        area = data.eval_str(element.area)
        _require_finite_positive(area, f"{element.identifier}.area")
        if element.window_identifier:
            if element.window_identifier not in window_ids:
                raise ValidationError(f"{element.identifier} references a missing window")
            if Constants.AMBIENT_IDENTIFIER not in (element.adjacent_A, element.adjacent_B):
                raise ValidationError(f"{element.identifier} window requires ambient adjacency")
            window = next(w for w in data.windows if w.identifier == element.window_identifier)
            if area - data.eval_str(window.glass_area) - data.eval_str(window.frame_area) < 0:
                raise ValidationError(f"Window area exceeds {element.identifier} area")
        if element.construction_identifier in nomass_ids and element.adjacent_A == element.adjacent_B:
            raise ValidationError("No-mass construction cannot have equal adjacent identifiers")
    # Force evaluation now so unknown parameters and invalid physical values fail here.
    for material in data.materials:
        if material.R_value:
            _require_finite_positive(data.eval_str(material.R_value), f"{material.identifier}.R_value", zero=True)
        else:
            for name in ("specific_heat_capacity", "specific_thermal_resistance", "density"):
                _require_finite_positive(data.eval_str(getattr(material, name)), f"{material.identifier}.{name}")
    for item in data.nomass_constructions:
        _require_finite_positive(data.eval_str(item.U_value), f"{item.identifier}.U_value")


def _append_block(matrix: np.ndarray, block: np.ndarray) -> np.ndarray:
    old, new = matrix.shape[0], block.shape[0]
    result = np.zeros((old + new, old + new), dtype=float)
    result[:old, :old] = matrix
    result[old:, old:] = block
    return result


def _is_zone(identifier: str) -> bool:
    return len(identifier) == 5 and identifier.startswith(Zone.KEY) and identifier[1:].isdigit()


def _film_coefficient(data: ThermalModelData, adjacent: str, raw: str) -> float:
    value = data.eval_str(raw)
    if _is_zone(adjacent) or Constants.AMBIENT_IDENTIFIER in adjacent or Constants.TBC_WITH_FILM_COEFFICIENT in adjacent:
        result = value
    else:  # GND, ADB, TBCwoFC, and MATLAB's catch-all branch
        result = math.inf
    if math.isnan(result) or result <= 0:
        raise ValidationError("Bad value of convective coefficient")
    return result


def generate_thermal_model(data: ThermalModelData) -> ThermalModel:
    """Generate the dense continuous thermal RC model in MATLAB source order."""
    check_thermal_model_data_consistency(data)
    states = [f"{Constants.STATE_VARIABLE}_{zone.identifier}" for zone in data.zones]
    capacities = [Constants.C_AIR * Constants.RHO_AIR * data.eval_str(zone.volume) for zone in data.zones]
    abar = np.zeros((len(states), len(states)), dtype=float)
    boundary: dict[str, list[BoundaryCondition]] = {"ambient": [], "adiabatic": [], "ground": [], "user_defined": []}

    constructions = {item.identifier: item for item in data.constructions}
    materials = {item.identifier: item for item in data.materials}
    nomass = {item.identifier: item for item in data.nomass_constructions}
    windows = {item.identifier: item for item in data.windows}

    for element in data.building_elements:
        area = data.eval_str(element.area)
        if element.window_identifier:
            win = windows[element.window_identifier]
            area -= data.eval_str(win.glass_area) + data.eval_str(win.frame_area)
        _require_finite_positive(area, f"{element.identifier}.net_area")
        element_states: list[str] = []
        element_caps: list[float] = []
        first_r = cumulative_r = 0.0

        construction = constructions.get(element.construction_identifier)
        if construction is None:
            last_r = 1.0 / (area * data.eval_str(nomass[element.construction_identifier].U_value))
            element_abar = np.zeros((0, 0))
        else:
            mass_count = sum(not materials[mid].R_value for mid in construction.material_identifiers)
            element_abar = np.zeros((mass_count, mass_count), dtype=float)
            previous_mass = -1
            for layer0, (material_id, thickness_raw) in enumerate(zip(construction.material_identifiers, construction.thickness)):
                material = materials[material_id]
                if not material.R_value:
                    layer1 = layer0 + 1  # Identifier contract remains MATLAB 1-based.
                    element_states.append(f"x_{element.identifier}_L{layer1}_s1_{element.adjacent_A}{element.adjacent_B}")
                    thickness = data.eval_str(thickness_raw)
                    cap = area * thickness * data.eval_str(material.density) * data.eval_str(material.specific_heat_capacity)
                    _require_finite_positive(cap, f"{element.identifier}.L{layer1}.capacity")
                    element_caps.append(cap)
                    half_r = thickness * data.eval_str(material.specific_thermal_resistance) / (2.0 * area)
                    cumulative_r += half_r
                    current_mass = previous_mass + 1
                    if previous_mass < 0:
                        first_r = cumulative_r
                    else:
                        conductance = 1.0 / cumulative_r
                        element_abar[previous_mass, previous_mass] -= conductance
                        element_abar[current_mass, current_mass] -= conductance
                        element_abar[previous_mass, current_mass] += conductance
                        element_abar[current_mass, previous_mass] += conductance
                    previous_mass = current_mass
                    cumulative_r = half_r
                else:
                    cumulative_r += data.eval_str(material.R_value) / area
            last_r = cumulative_r

        abar = _append_block(abar, element_abar)
        states.extend(element_states)
        capacities.extend(element_caps)

        bcs: list[BoundaryCondition] = []
        if construction is not None:
            h_a = _film_coefficient(data, element.adjacent_A, construction.conv_coeff_adjacent_A)
            h_b = _film_coefficient(data, element.adjacent_B, construction.conv_coeff_adjacent_B)
            if element_states:
                bcs = [
                    BoundaryCondition(element_states[0], f"x_{element.adjacent_A}" if _is_zone(element.adjacent_A) else element.adjacent_A,
                                      1.0 / (first_r + 1.0 / (area * h_a))),
                    BoundaryCondition(element_states[-1], f"x_{element.adjacent_B}" if _is_zone(element.adjacent_B) else element.adjacent_B,
                                      1.0 / (last_r + 1.0 / (area * h_b))),
                ]
            else:
                bcs = [BoundaryCondition(), BoundaryCondition(
                    f"x_{element.adjacent_A}" if _is_zone(element.adjacent_A) else element.adjacent_A,
                    f"x_{element.adjacent_B}" if _is_zone(element.adjacent_B) else element.adjacent_B,
                    1.0 / (last_r + 1.0 / (area * h_a) + 1.0 / (area * h_b)))
                ]
        else:
            bcs = [BoundaryCondition(), BoundaryCondition(
                f"x_{element.adjacent_A}" if _is_zone(element.adjacent_A) else element.adjacent_A,
                f"x_{element.adjacent_B}" if _is_zone(element.adjacent_B) else element.adjacent_B,
                1.0 / last_r
            )]

        state_index = {identifier: index for index, identifier in enumerate(states)}
        for bc in bcs:
            if not bc.identifier_1 or not bc.identifier_2:
                continue
            endpoints = (bc.identifier_1, bc.identifier_2)
            if Constants.AMBIENT_IDENTIFIER in endpoints:
                boundary["ambient"].append(bc)
            elif Constants.ADIABATIC_IDENTIFIER in endpoints:
                boundary["adiabatic"].append(bc)
            elif Constants.GROUND_IDENTIFIER in endpoints:
                boundary["ground"].append(bc)
            elif bc.identifier_1 in state_index and bc.identifier_2 in state_index:
                i, j = state_index[bc.identifier_1], state_index[bc.identifier_2]
                abar[i, i] -= bc.value
                abar[j, j] -= bc.value
                abar[i, j] += bc.value
                abar[j, i] += bc.value
            else:
                boundary["user_defined"].append(bc)

    xcap = np.diag(np.asarray(capacities, dtype=float))
    a = np.linalg.solve(xcap, abar)
    bq = np.linalg.solve(xcap, np.eye(len(states)))
    heat_fluxes = [Constants.HEAT_FLUX_VARIABLE + identifier[1:] for identifier in states]
    return ThermalModel(a, bq, xcap, states, heat_fluxes, boundary)


checkThermalModelDataConsistency = check_thermal_model_data_consistency
generateThermalModel = generate_thermal_model
