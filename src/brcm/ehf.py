"""Dense external-heat-flux submodels from the MATLAB BRCM toolbox.

Tensor axes preserve MATLAB semantics: ``Bq_xu[q, x, u]`` and
``Bq_vu[q, v, u]``.  All thermal rows use the Stage 3 model ordering.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from .constants import Constants
from .exceptions import DataFormatError, ValidationError
from .io import get_data_tables_from_file
from .primitives import Identifier
from .thermal_data import ThermalModelData
from .thermal_model import ThermalModel


def _source(path: str | Path) -> Path:
    path = Path(path)
    if path.is_file():
        return path
    for suffix in (".csv", ".xls", ".xlsx"):
        candidate = path.with_suffix(suffix)
        if candidate.is_file():
            return candidate
    raise DataFormatError(f"EHF data file not found: {path}")


def _index(values: Sequence[str], identifier: str, label: str = "identifier") -> int:
    matches = [i for i, value in enumerate(values) if value == identifier]
    if len(matches) != 1:
        raise ValidationError(f"Expected exactly one {label} {identifier!r}, found {len(matches)}")
    return matches[0]


def _sorted_unique(values: Sequence[str]) -> list[str]:
    """MATLAB ``unique`` ordering for the ASCII identifiers used by BRCM."""
    return sorted(set(values))


class EHFModelBaseClass(ABC):
    """Base contract for independently constructible EHF models."""

    multi_include_ok = False

    def __init__(self, data: ThermalModelData, thermal_model: ThermalModel, identifier: str, source_file: str | Path):
        self.data = data
        self.thermal_model = thermal_model
        self.EHF_identifier = identifier
        self.source_file = _source(source_file)
        self.identifiers = Identifier(x=list(thermal_model.state_identifiers), q=list(thermal_model.heat_flux_identifiers))
        self.Aq = np.empty((0, 0)); self.Bq_u = np.empty((0, 0)); self.Bq_v = np.empty((0, 0))
        self.Bq_xu = np.empty((0, 0, 0)); self.Bq_vu = np.empty((0, 0, 0))

    def _zeros(self) -> None:
        nq, nx = len(self.identifiers.q), len(self.identifiers.x)
        nu, nv = len(self.identifiers.u), len(self.identifiers.v)
        self.Aq = np.zeros((nq, nx)); self.Bq_u = np.zeros((nq, nu)); self.Bq_v = np.zeros((nq, nv))
        self.Bq_xu = np.zeros((nq, nx, nu)); self.Bq_vu = np.zeros((nq, nv, nu))

    def check_nan(self) -> None:
        expected = {
            "Aq": (len(self.identifiers.q), len(self.identifiers.x)),
            "Bq_u": (len(self.identifiers.q), len(self.identifiers.u)),
            "Bq_v": (len(self.identifiers.q), len(self.identifiers.v)),
            "Bq_xu": (len(self.identifiers.q), len(self.identifiers.x), len(self.identifiers.u)),
            "Bq_vu": (len(self.identifiers.q), len(self.identifiers.v), len(self.identifiers.u)),
        }
        for name, shape in expected.items():
            value = np.asarray(getattr(self, name))
            if value.shape != shape:
                raise ValidationError(f"{self.EHF_identifier}.{name} has shape {value.shape}, expected {shape}")
            if np.isnan(value).any():
                raise ValidationError(f"{self.EHF_identifier}.{name} contains NaNs")

    checkNan = check_nan

    def get_prescribed_size_system_matrices(self, identifiers: Identifier):
        nq, nx, nu, nv = len(identifiers.q), len(identifiers.x), len(identifiers.u), len(identifiers.v)
        if identifiers.q != self.identifiers.q or identifiers.x != self.identifiers.x:
            raise ValidationError("Prescribed thermal identifiers must exactly match EHF thermal ordering")
        bu = np.zeros((nq, nu)); bv = np.zeros((nq, nv)); bxu = np.zeros((nq, nx, nu)); bvu = np.zeros((nq, nv, nu))
        for local, name in enumerate(self.identifiers.u):
            target = _index(identifiers.u, name, "input")
            bu[:, target] = self.Bq_u[:, local]; bxu[:, :, target] = self.Bq_xu[:, :, local]
            for local_v, vname in enumerate(self.identifiers.v):
                bvu[:, _index(identifiers.v, vname, "disturbance"), target] = self.Bq_vu[:, local_v, local]
        for local, name in enumerate(self.identifiers.v):
            bv[:, _index(identifiers.v, name, "disturbance")] = self.Bq_v[:, local]
        return self.Aq.copy(), bu, bv, bxu, bvu

    getPrescribedSizeSystemMatrices = get_prescribed_size_system_matrices

    def get_prescribed_size_constraints_matrices(self, identifiers: Identifier, parameters: Mapping[str, Any]):
        fx, local_fu, local_fv, g, names = self.get_constraints_matrices(parameters)
        fu = np.zeros((len(names), len(identifiers.u))); fv = np.zeros((len(names), len(identifiers.v)))
        for j, name in enumerate(self.identifiers.u): fu[:, _index(identifiers.u, name)] = local_fu[:, j]
        for j, name in enumerate(self.identifiers.v): fv[:, _index(identifiers.v, name)] = local_fv[:, j]
        return fx, fu, fv, g, names

    getPrescribedSizeConstraintsMatrices = get_prescribed_size_constraints_matrices

    def get_prescribed_size_cost_vector(self, identifiers: Identifier, parameters: Mapping[str, Any]) -> np.ndarray:
        result = np.zeros((len(identifiers.u), 1)); local = self.get_cost_vector(parameters).reshape(-1)
        for j, name in enumerate(self.identifiers.u): result[_index(identifiers.u, name), 0] = local[j]
        return result

    getPrescribedSizeCostVector = get_prescribed_size_cost_vector

    @abstractmethod
    def get_constraints_matrices(self, parameters: Mapping[str, Any]): ...
    @abstractmethod
    def get_cost_vector(self, parameters: Mapping[str, Any]): ...

    def _empty_constraints(self):
        nc, nx, nu, nv = len(self.identifiers.constraints), len(self.identifiers.x), len(self.identifiers.u), len(self.identifiers.v)
        return np.zeros((nc, nx)), np.zeros((nc, nu)), np.zeros((nc, nv)), np.zeros((nc, 1)), list(self.identifiers.constraints)


class InternalGains(EHFModelBaseClass):
    def __init__(self, data, thermal_model, identifier, source_file):
        super().__init__(data, thermal_model, identifier, source_file)
        tables, _ = get_data_tables_from_file(self.source_file, ("zone_identifier", "disturbance_identifier"))
        specs = [(row[0], row[1]) for row in tables[0][1:] if row[1]]
        zone_ids = [z.identifier for z in data.zones]
        for zone, _ in specs: _index(zone_ids, zone, "zone")
        self.identifiers.v = _sorted_unique([f"v_IG_{disturbance}" for _, disturbance in specs])
        self._zeros()
        for zone, disturbance in specs:
            qi = _index(self.identifiers.q, f"q_{zone}"); vi = _index(self.identifiers.v, f"v_IG_{disturbance}")
            self.Bq_v[qi, vi] = float(data.zones[_index(zone_ids, zone)].area)
        self.check_nan()

    def get_constraints_matrices(self, parameters): return self._empty_constraints()
    def get_cost_vector(self, parameters): return np.zeros((len(self.identifiers.u), 1))


def _bounded_constraints(model: EHFModelBaseClass, parameters: Mapping[str, Any], prefix: str):
    fx, fu, fv, g, names = model._empty_constraints()
    for ui, uid in enumerate(model.identifiers.u):
        low, high = prefix + uid[1:] + "_min", prefix + uid[1:] + "_max"
        if low not in parameters or high not in parameters: raise ValidationError(f"Missing {low} or {high}")
        if float(parameters[low]) > float(parameters[high]): raise ValidationError(f"{low} exceeds {high}")
        fu[_index(names, low), ui] = -1; g[_index(names, low), 0] = -float(parameters[low])
        fu[_index(names, high), ui] = 1; g[_index(names, high), 0] = float(parameters[high])
    return fx, fu, fv, g, names


class Radiators(EHFModelBaseClass):
    def __init__(self, data, thermal_model, identifier, source_file):
        super().__init__(data, thermal_model, identifier, source_file)
        tables, _ = get_data_tables_from_file(self.source_file, ("zone_identifier", "control_identifier"))
        zone_ids = [z.identifier for z in data.zones]
        self.specs = [(r[0], r[1], data.eval_str(data.zones[_index(zone_ids, r[0])].area)) for r in tables[0][1:] if r[1]]
        self.identifiers.u = _sorted_unique([f"u_rad_{control}" for _, control, _ in self.specs])
        self.identifiers.constraints = [name for uid in self.identifiers.u for name in (f"Q{uid[1:]}_min", f"Q{uid[1:]}_max")]
        self._zeros()
        for zone, control, area in self.specs: self.Bq_u[_index(self.identifiers.q, f"q_{zone}"), _index(self.identifiers.u, f"u_rad_{control}")] = area
        self.check_nan()

    def get_constraints_matrices(self, parameters): return _bounded_constraints(self, parameters, "Q")
    def get_cost_vector(self, parameters):
        cost = float(parameters["costPerJouleHeated"]); result = np.zeros((len(self.identifiers.u), 1))
        if cost <= 0: raise ValidationError("costPerJouleHeated must be positive")
        for _, control, area in self.specs: result[_index(self.identifiers.u, f"u_rad_{control}"), 0] += cost * area
        return result


class BEHeatfluxes(EHFModelBaseClass):
    def __init__(self, data, thermal_model, identifier, source_file):
        super().__init__(data, thermal_model, identifier, source_file)
        header = ("buildingelement_identifier", "layer_number", "control_identifier", "heating_cooling_selection")
        tables, _ = get_data_tables_from_file(self.source_file, header)
        be_ids = [b.identifier for b in data.building_elements]; specs = []
        selection: dict[str, str] = {}
        for r in tables[0][1:]:
            be, layer, control, hc = r[0], int(float(r[1])), r[2], r[3]
            bei = _index(be_ids, be, "building element"); element = data.building_elements[bei]
            if hc not in ("h", "c") or (control in selection and selection[control] != hc): raise ValidationError("Invalid heating/cooling selection")
            selection[control] = hc; specs.append((element, layer, control, hc, data.eval_str(element.area)))
        self.specs = specs
        for control in _sorted_unique(list(selection)):
            suffix = "heat" if selection[control] == "h" else "cool"; uid = f"u_BEH_{control}_{suffix}"
            self.identifiers.u.append(uid); self.identifiers.constraints.extend((f"Q{uid[1:]}_min", f"Q{uid[1:]}_max"))
        self._zeros()
        for element, layer, control, hc, area in specs:
            qid = f"q_{element.identifier}_L{layer}_s1_{element.adjacent_A}{element.adjacent_B}"
            uid = f"u_BEH_{control}_{'heat' if hc == 'h' else 'cool'}"
            self.Bq_u[_index(self.identifiers.q, qid), _index(self.identifiers.u, uid)] += area if hc == "h" else -area
        self.check_nan()

    def get_constraints_matrices(self, parameters): return _bounded_constraints(self, parameters, "Q")
    def get_cost_vector(self, parameters):
        ts = float(parameters["Ts_hrs"]); result = np.zeros((len(self.identifiers.u), 1))
        for _, _, control, hc, area in self.specs:
            key = "costPerJouleHeated" if hc == "h" else "costPerJouleCooled"; value = float(parameters[key])
            if value <= 0: raise ValidationError(f"{key} must be positive")
            uid = f"u_BEH_{control}_{'heat' if hc == 'h' else 'cool'}"; result[_index(self.identifiers.u, uid), 0] += area * value * ts
        return result


def _net_area(data: ThermalModelData, element) -> float:
    area = data.eval_str(element.area)
    if element.window_identifier:
        window = data.windows[data.get_window_idx_from_identifier(element.window_identifier)]
        area -= data.eval_str(window.glass_area) + data.eval_str(window.frame_area)
    return area


def _outer_q(model: EHFModelBaseClass, element) -> tuple[str | None, str | None]:
    prefix = f"q_{element.identifier}_L"
    found = [qid for qid in model.identifiers.q if qid.startswith(prefix) and qid.endswith(element.adjacent_A + element.adjacent_B)]
    return (found[0], found[-1]) if found else (None, None)


class BuildingHull(EHFModelBaseClass):
    """Ambient/ground conduction, opaque/window solar gain and infiltration."""
    def __init__(self, data, thermal_model, identifier, source_file):
        super().__init__(data, thermal_model, identifier, source_file)
        headers = [
            ("facade_solar_group", "buildingelement_identifier", "disturbance_identifier", "absorptance"),
            ("window_solar_group", "buildingelement_identifier", "disturbance_identifier", "control_identifier", "secondary_gains_fraction"),
            ("infiltration_specification", "zone_identifier", "airchangerate"),
        ]
        tables, _ = get_data_tables_from_file(self.source_file, headers)
        be_map = {b.identifier: b for b in data.building_elements}; zone_ids = [z.identifier for z in data.zones]
        self.facade_specs = [(r[1], r[2], float(r[3])) for r in tables[0][1:]]
        self.window_specs = [(r[1], r[2], r[3], float(r[4])) for r in tables[1][1:]]
        self.infiltration_specs = [(r[1], float(r[2] or 0)) for r in tables[2][1:]]
        for be, _, absorptance in self.facade_specs:
            element = be_map.get(be)
            if element is None or Constants.AMBIENT_IDENTIFIER not in (element.adjacent_A, element.adjacent_B) or not 0 <= absorptance <= 1:
                raise ValidationError(f"Invalid facade specification for {be}")
        for be, _, _, fraction in self.window_specs:
            element = be_map.get(be)
            if element is None or not element.window_identifier or Constants.AMBIENT_IDENTIFIER not in (element.adjacent_A, element.adjacent_B) or not 0 <= fraction <= 1:
                raise ValidationError(f"Invalid window specification for {be}")
        expected_windows = sorted(b.identifier for b in data.building_elements if b.window_identifier)
        if sorted(be for be, *_ in self.window_specs) != expected_windows: raise ValidationError("Every window building element must occur exactly once")
        for zone, rate in self.infiltration_specs:
            _index(zone_ids, zone, "zone")
            if rate < 0: raise ValidationError("Air-change rate must be non-negative")

        self.identifiers.v = ["v_Tamb"]
        if thermal_model.boundary_conditions.get("ground"): self.identifiers.v.append("v_Tgnd")
        adjacent = _sorted_unique([x for b in data.building_elements for x in (b.adjacent_A, b.adjacent_B)])
        for value in adjacent:
            if value not in Constants.EXTERIOR_IDENTIFIERS and not (len(value) == 5 and value.startswith("Z") and value[1:].isdigit()): self.identifiers.v.append(f"v_{value}")
        solar = [v for _, v, _ in self.facade_specs] + [v for _, v, _, _ in self.window_specs]
        self.identifiers.v.extend(_sorted_unique([f"v_solGlobFac_{v}" for v in solar if v]))
        controls = _sorted_unique([f"u_blinds_{u}" for _, _, u, _ in self.window_specs if u])
        self.identifiers.u = controls
        self.identifiers.constraints = [name for uid in controls for name in (f"BPos{uid[1:]}_min", f"BPos{uid[1:]}_max")]
        self._zeros(); vi_amb = _index(self.identifiers.v, "v_Tamb")

        for bucket, vname in (("ground", "v_Tgnd"),):
            for bc in thermal_model.boundary_conditions.get(bucket, []):
                xi = _index(self.identifiers.x, bc.identifier_1); qi = _index(self.identifiers.q, "q" + bc.identifier_1[1:]); vi = _index(self.identifiers.v, vname)
                self.Aq[qi, xi] -= bc.value; self.Bq_v[qi, vi] += bc.value
        for bc in thermal_model.boundary_conditions.get("user_defined", []):
            xi = _index(self.identifiers.x, bc.identifier_1); qi = _index(self.identifiers.q, "q" + bc.identifier_1[1:]); vi = _index(self.identifiers.v, "v_" + bc.identifier_2)
            self.Aq[qi, xi] -= bc.value; self.Bq_v[qi, vi] += bc.value
        for bc in thermal_model.boundary_conditions.get("ambient", []):
            xid = bc.identifier_1 if bc.identifier_1 in self.identifiers.x else bc.identifier_2
            xi = _index(self.identifiers.x, xid); qi = _index(self.identifiers.q, "q" + xid[1:])
            self.Aq[qi, xi] -= bc.value; self.Bq_v[qi, vi_amb] += bc.value

        for be, disturbance, absorptance in self.facade_specs:
            element = be_map[be]; qa, qb = _outer_q(self, element)
            qid = qa if element.adjacent_A == Constants.AMBIENT_IDENTIFIER else qb
            if qid is None: raise ValidationError(f"Facade {be} has no massive state")
            self.Bq_v[_index(self.identifiers.q, qid), _index(self.identifiers.v, f"v_solGlobFac_{disturbance}")] += _net_area(data, element) * absorptance

        for be, disturbance, control, secondary in self.window_specs:
            element = be_map[be]; zone = element.adjacent_B if element.adjacent_A == Constants.AMBIENT_IDENTIFIER else element.adjacent_A
            window = data.windows[data.get_window_idx_from_identifier(element.window_identifier)]
            glass, frame = data.eval_str(window.glass_area), data.eval_str(window.frame_area); area = glass + frame
            ua = data.eval_str(window.U_value) * area; qi_zone = _index(self.identifiers.q, f"q_{zone}"); xi_zone = _index(self.identifiers.x, f"x_{zone}")
            self.Aq[qi_zone, xi_zone] -= ua; self.Bq_v[qi_zone, vi_amb] += ua
            vi = _index(self.identifiers.v, f"v_solGlobFac_{disturbance}"); coefficient = area * data.eval_str(window.SHGC)
            # MATLAB distributes primary gains across massive BE faces by net area.
            elements = [b for b in data.building_elements if zone in (b.adjacent_A, b.adjacent_B) and _outer_q(self, b)[0] is not None]
            areas = [_net_area(data, b) for b in elements]
            total = sum(a * ((b.adjacent_A == zone) + (b.adjacent_B == zone)) for a, b in zip(areas, elements))
            ui = _index(self.identifiers.u, f"u_blinds_{control}") if control else None
            for other, other_area in zip(elements, areas):
                qa, qb = _outer_q(self, other)
                for matches, qid in ((other.adjacent_A == zone, qa), (other.adjacent_B == zone, qb)):
                    if matches:
                        value = other_area / total * (1 - secondary) * coefficient
                        if ui is None: self.Bq_v[_index(self.identifiers.q, qid), vi] += value
                        else: self.Bq_vu[_index(self.identifiers.q, qid), vi, ui] += value
            value = secondary * coefficient
            if ui is None: self.Bq_v[qi_zone, vi] += value
            else: self.Bq_vu[qi_zone, vi, ui] += value
        for zone, rate in self.infiltration_specs:
            volume = data.eval_str(data.zones[_index(zone_ids, zone)].volume); value = rate * volume / 3600 * Constants.C_AIR * Constants.RHO_AIR
            qi, xi = _index(self.identifiers.q, f"q_{zone}"), _index(self.identifiers.x, f"x_{zone}")
            self.Aq[qi, xi] -= value; self.Bq_v[qi, vi_amb] += value
        self.check_nan()

    def get_constraints_matrices(self, parameters): return _bounded_constraints(self, parameters, "BPos")
    def get_cost_vector(self, parameters): return np.zeros((len(self.identifiers.u), 1))


class AHU(EHFModelBaseClass):
    multi_include_ok = True
    def __init__(self, data, thermal_model, identifier, source_file):
        super().__init__(data, thermal_model, identifier, source_file)
        headers = [("AHU_specification", "key", "value"), ("airflow_specification", "zone_identifier", "flow_fraction", "from_identifier")]
        tables, _ = get_data_tables_from_file(self.source_file, headers)
        spec = {r[1]: float(r[2]) for r in tables[0][1:]}
        required = ("hasERC", "ERCefficiency", "hasEvapCooler", "EvapCoolerEfficiency", "hasHeater", "hasCooler", "has_AHU_Tin")
        if any(k not in spec for k in required): raise ValidationError("Missing AHU specification")
        self.hasERC = bool(spec["hasERC"]); self.ERCefficiency = spec["ERCefficiency"] if self.hasERC else 0
        self.hasEvapCooler = bool(spec["hasEvapCooler"]); self.evapCoolerEfficiency = spec["EvapCoolerEfficiency"] if self.hasEvapCooler else 0
        self.hasHeater = bool(spec["hasHeater"]); self.hasCooler = bool(spec["hasCooler"]); self.has_AHU_Tin = bool(spec["has_AHU_Tin"])
        if self.hasEvapCooler and not self.hasERC: raise ValidationError("Evaporative cooler requires ERC")
        zones = [z.identifier for z in data.zones]
        self.airflows = [(r[1], float(r[2]), r[3]) for r in tables[1][1:]]
        for zone, flow, source in self.airflows:
            _index(zones, zone, "zone")
            if source != "AHU": _index(zones, source, "zone")
            if flow < 0: raise ValidationError("Flow fractions must be non-negative")
        airflow_zones = _sorted_unique([x for z, _, source in self.airflows for x in (z, source) if x != "AHU"])
        self.return_zones = []
        for zone in airflow_zones:
            net = sum(f for z, f, _ in self.airflows if z == zone) - sum(f for _, f, source in self.airflows if source == zone)
            if net < 0: raise ValidationError(f"Negative AHU net flow for {zone}")
            if net > 0: self.return_zones.append((zone, net))
        if not np.isclose(sum(f for _, f in self.return_zones), 1, rtol=0, atol=1e-12): raise ValidationError("Total AHU return flow is not one")
        self.supply_zones = [(zone, sum(f for z, f, source in self.airflows if z == zone and source == "AHU")) for zone in airflow_zones]
        self.supply_zones = [(z, f) for z, f in self.supply_zones if f]

        self.identifiers.u = [f"u_{identifier}_noERC"]
        self.identifiers.constraints = [f"{identifier}_mdot_min", f"{identifier}_mdot_max", f"{identifier}_mdotNoERC_nonneg"]
        self.identifiers.v = [f"v_{identifier}_Tin" if self.has_AHU_Tin else "v_Tamb"]
        if self.hasERC: self.identifiers.u.append(f"u_{identifier}_ERC"); self.identifiers.constraints.append(f"{identifier}_mdotERC_nonneg")
        if self.hasEvapCooler:
            self.identifiers.u.append(f"u_{identifier}_evapCooler"); self.identifiers.v.append(f"v_{identifier}_Dwb")
            self.identifiers.constraints.extend((f"{identifier}_evapCooler_nonneg", f"{identifier}_evapCooler_max"))
        if self.hasHeater: self.identifiers.u.append(f"u_{identifier}_heater"); self.identifiers.constraints.extend((f"{identifier}_Q_heat_min", f"{identifier}_Q_heat_max"))
        if self.hasCooler: self.identifiers.u.append(f"u_{identifier}_cooler"); self.identifiers.constraints.extend((f"{identifier}_Q_cool_min", f"{identifier}_Q_cool_max"))
        self.identifiers.constraints.extend((f"{identifier}_T_supply_min", f"{identifier}_T_supply_max"))
        self._zeros(); uno = _index(self.identifiers.u, f"u_{identifier}_noERC"); vin = 0
        for zone, fraction in self.supply_zones:
            qi, xi = _index(self.identifiers.q, f"q_{zone}"), _index(self.identifiers.x, f"x_{zone}")
            self.Bq_vu[qi, vin, uno] += fraction * Constants.C_AIR; self.Bq_xu[qi, xi, uno] -= fraction * Constants.C_AIR
            if self.hasERC:
                ue = _index(self.identifiers.u, f"u_{identifier}_ERC"); self.Bq_vu[qi, vin, ue] += fraction * Constants.C_AIR * (1-self.ERCefficiency)
                for ret, ret_fraction in self.return_zones: self.Bq_xu[qi, _index(self.identifiers.x, f"x_{ret}"), ue] += fraction * Constants.C_AIR * self.ERCefficiency * ret_fraction
                self.Bq_xu[qi, xi, ue] -= fraction * Constants.C_AIR
            if self.hasHeater: self.Bq_u[qi, _index(self.identifiers.u, f"u_{identifier}_heater")] += fraction
            if self.hasCooler: self.Bq_u[qi, _index(self.identifiers.u, f"u_{identifier}_cooler")] -= fraction
            if self.hasEvapCooler:
                self.Bq_vu[qi, _index(self.identifiers.v, f"v_{identifier}_Dwb"), _index(self.identifiers.u, f"u_{identifier}_evapCooler")] -= fraction*Constants.C_AIR*self.ERCefficiency*self.evapCoolerEfficiency
        for zone, fraction, source in self.airflows:
            if source == "AHU": continue
            qi, xi, xfrom = _index(self.identifiers.q, f"q_{zone}"), _index(self.identifiers.x, f"x_{zone}"), _index(self.identifiers.x, f"x_{source}")
            for uid in ([uno] + ([_index(self.identifiers.u, f"u_{identifier}_ERC")] if self.hasERC else [])):
                self.Bq_xu[qi, xi, uid] -= fraction*Constants.C_AIR; self.Bq_xu[qi, xfrom, uid] += fraction*Constants.C_AIR
        self.check_nan()

    def get_constraints_matrices(self, parameters):
        nc, nx, nu, nv = len(self.identifiers.constraints), len(self.identifiers.x), len(self.identifiers.u), len(self.identifiers.v)
        fx, fu, fv, g = np.zeros((nc,nx)), np.zeros((nc,nu)), np.zeros((nc,nv)), np.zeros((nc,1)); names=self.identifiers.constraints; eid=self.EHF_identifier
        def row(name): return _index(names, f"{eid}_{name}")
        def u(name): return _index(self.identifiers.u, f"u_{eid}_{name}")
        for lo, hi, uname in (("mdot_min","mdot_max","noERC"),):
            fu[row(lo),u(uname)] = -1; fu[row(hi),u(uname)] = 1; g[row(lo),0]=-float(parameters[lo]); g[row(hi),0]=float(parameters[hi])
        if self.hasERC: fu[row("mdot_min"),u("ERC")]-=1; fu[row("mdot_max"),u("ERC")]+=1; fu[row("mdotERC_nonneg"),u("ERC")]=-1
        fu[row("mdotNoERC_nonneg"),u("noERC")]=-1
        if self.hasHeater:
            fu[row("Q_heat_min"),u("heater")]=-1; fu[row("Q_heat_max"),u("heater")]=1; g[row("Q_heat_min"),0]=-float(parameters["Q_heat_min"]); g[row("Q_heat_max"),0]=float(parameters["Q_heat_max"])
        if self.hasCooler:
            fu[row("Q_cool_min"),u("cooler")]=-1; fu[row("Q_cool_max"),u("cooler")]=1; g[row("Q_cool_min"),0]=-float(parameters["Q_cool_min"]); g[row("Q_cool_max"),0]=float(parameters["Q_cool_max"])
        if self.hasEvapCooler: fu[row("evapCooler_nonneg"),u("evapCooler")]=-1; fu[row("evapCooler_max"),u("evapCooler")]=1; fu[row("evapCooler_max"),u("ERC")]=-1
        # Supply-temperature rows intentionally depend on the supplied operating point, as in MATLAB.
        full_ids = parameters["identifiers_fullModel"]; full_v = np.asarray(parameters["v_fullModel"]).reshape(-1); x = np.asarray(parameters["x"]).reshape(-1)
        vin_name = f"v_{eid}_Tin" if self.has_AHU_Tin else "v_Tamb"; tin=full_v[_index(full_ids.v,vin_name)]
        treturn=sum(fr*x[_index(self.identifiers.x,f"x_{z}")] for z,fr in self.return_zones); c=Constants.C_AIR; tmin=float(parameters["T_supply_min"]); tmax=float(parameters["T_supply_max"])
        fu[row("T_supply_min"),u("noERC")]=-c*tin+c*tmin; fu[row("T_supply_max"),u("noERC")]=c*tin-c*tmax
        if self.hasERC:
            base=self.ERCefficiency*(treturn-tin)+tin; fu[row("T_supply_min"),u("ERC")]=-c*base+c*tmin; fu[row("T_supply_max"),u("ERC")]=c*base-c*tmax
        if self.hasHeater: fu[row("T_supply_min"),u("heater")]=-1; fu[row("T_supply_max"),u("heater")]=1
        if self.hasCooler: fu[row("T_supply_min"),u("cooler")]=1; fu[row("T_supply_max"),u("cooler")]=-1
        if self.hasEvapCooler:
            dwb=full_v[_index(full_ids.v,f"v_{eid}_Dwb")]; val=-c*self.ERCefficiency*self.evapCoolerEfficiency*dwb
            fu[row("T_supply_min"),u("evapCooler")]=-val; fu[row("T_supply_max"),u("evapCooler")]=val
        return fx,fu,fv,g,list(names)

    def get_cost_vector(self, parameters):
        ts=float(parameters["Ts_hrs"]); result=np.zeros((len(self.identifiers.u),1)); eid=self.EHF_identifier
        assignments=[("noERC","costPerKgAirTransported")]
        if self.hasERC: assignments.append(("ERC","costPerKgAirTransported"))
        if self.hasHeater: assignments.append(("heater","costPerJouleHeated"))
        if self.hasCooler: assignments.append(("cooler","costPerJouleCooled"))
        if self.hasEvapCooler: assignments.append(("evapCooler","costPerKgCooledByEvapCooler"))
        for uname,key in assignments:
            value=float(parameters[key]);
            if value<=0: raise ValidationError(f"{key} must be positive")
            result[_index(self.identifiers.u,f"u_{eid}_{uname}"),0]+=value*ts
        return result


EHF_REGISTRY = {"InternalGains": InternalGains, "Radiators": Radiators, "BEHeatfluxes": BEHeatfluxes, "BuildingHull": BuildingHull, "AHU": AHU}
