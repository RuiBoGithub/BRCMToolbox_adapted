"""One EnergyPlus parse feeding both fixed 5R1C and detailed BRCM models.

This is deliberately an adapter around the existing BRCM conversion rather
than a second IDF parser. JSON remains an overlay for assumptions that are not
available (or not yet converted) from the EnergyPlus model.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any, Mapping

import numpy as np

import brcm
from brcm.energyplus.geometry import polygon_area


@dataclass(frozen=True)
class CommonBuildingData:
    source: Path
    conversion: Any
    thermal_data: Any
    floor_area_m2: float
    volume_m3: float
    opaque_envelope_area_m2: float
    window_area_m2: float
    opaque_ua_w_k: float
    window_ua_w_k: float
    thermal_capacity_j_k: float
    infiltration_ach: float
    ventilation_ach: float
    heat_recovery_efficiency: float
    boundary_counts: Mapping[str, int]
    schedule_names: tuple[str, ...]
    json_overlay: Mapping[str, Any]

    def summary(self) -> dict[str, Any]:
        result = asdict(self)
        result.pop("conversion")
        result.pop("thermal_data")
        result["source"] = str(self.source)
        return result


@dataclass(frozen=True)
class FiveR1CModel:
    """ISO 13790 five-resistance/one-capacitance aggregate."""

    floor_area_m2: float
    volume_m3: float
    h_tr_em_w_k: float
    h_tr_w_w_k: float
    h_tr_ms_w_k: float
    h_tr_is_w_k: float
    h_ve_adj_w_k: float
    c_m_j_k: float
    mass_area_m2: float
    total_internal_area_m2: float


@dataclass(frozen=True)
class ModelPair:
    common: CommonBuildingData
    five_r1c: FiveR1CModel
    brcm_model: Any

    def audit(self) -> dict[str, Any]:
        return {
            "source": str(self.common.source),
            "shared": self.common.summary(),
            "5R1C": asdict(self.five_r1c),
            "BRCM": {
                "state_count": len(self.brcm_model.state_identifiers),
                "heat_flux_count": len(self.brcm_model.heat_flux_identifiers),
                "states": list(self.brcm_model.state_identifiers),
            },
        }


def _read_json(path: str | Path | None) -> dict[str, Any]:
    return {} if path is None else json.loads(Path(path).read_text())


def _area(surface: Any) -> float:
    return float(surface.area if surface.area is not None else polygon_area(surface.vertices))


def _material_resistance(material: Any) -> float:
    if material.resistance is not None:
        return float(material.resistance)
    if material.thickness is None or material.conductivity in (None, 0):
        return 0.0
    return float(material.thickness / material.conductivity)


def normalize_idf(
    idf_path: str | Path,
    *,
    idd_path: str | Path | None = None,
    geometry_json: str | Path | None = None,
    defaults_json: str | Path | None = None,
) -> CommonBuildingData:
    """Parse once and derive quantities shared by both RC formulations."""

    source = Path(idf_path).resolve()
    conversion = brcm.convert_idf_to_brcm_data(source, idd_path=idd_path)
    thermal_data = brcm.conversion_to_thermal_model_data(conversion)
    model = conversion.normalized_model
    geometry = _read_json(geometry_json)
    defaults = _read_json(defaults_json)
    overlay = {**geometry, **defaults}

    materials = {item.name.casefold(): item for item in model.materials}
    constructions = {item.name.casefold(): item for item in model.constructions}
    windows_by_parent: dict[str, float] = {}
    for window in model.windows:
        area = float(window.glass_area if window.glass_area is not None else polygon_area(window.vertices))
        windows_by_parent[window.parent_surface.casefold()] = windows_by_parent.get(window.parent_surface.casefold(), 0.0) + area + float(window.frame_area)

    # The raw IDF often uses "autocalculate"; BRCM's converted zone table has
    # already resolved those values from the surface geometry.
    floor_area = sum(thermal_data.eval_str(zone.area) for zone in thermal_data.zones)
    volume = sum(thermal_data.eval_str(zone.volume) for zone in thermal_data.zones)
    external = [surface for surface in model.surfaces if surface.outside_boundary.casefold() == "outdoors"]
    opaque_area = sum(max(0.0, _area(surface) - windows_by_parent.get(surface.name.casefold(), 0.0)) for surface in external)
    window_area = sum(windows_by_parent.values())
    opaque_ua = 0.0
    capacity = 0.0
    for surface in model.surfaces:
        construction = constructions.get(surface.construction.casefold())
        if construction is None:
            continue
        layers = [materials[name.casefold()] for name in construction.layers if name.casefold() in materials]
        gross_area = _area(surface)
        net_area = max(0.0, gross_area - windows_by_parent.get(surface.name.casefold(), 0.0))
        if surface.outside_boundary.casefold() == "outdoors":
            resistance = sum(_material_resistance(layer) for layer in layers)
            if resistance > 0:
                opaque_ua += net_area / resistance
        for layer in layers:
            if None not in (layer.thickness, layer.density, layer.specific_heat):
                capacity += net_area * float(layer.thickness) * float(layer.density) * float(layer.specific_heat)

    u_windows = float(defaults.get("u_windows", 1.0))
    infiltration_ach = float(defaults.get("ach_infl", defaults.get("infiltration_ach", 0.0)))
    if "infl_rate_m3ph_m2" in defaults and volume > 0:
        infiltration_ach += float(defaults["infl_rate_m3ph_m2"]) * opaque_area / volume
    ventilation_ach = float(defaults.get("ach_vent", 0.0))
    if ventilation_ach == 0 and volume > 0 and {"max_occupancy", "fresh_air_lps"} <= defaults.keys():
        ventilation_ach = 3.6 * float(defaults["max_occupancy"]) * float(defaults["fresh_air_lps"]) / volume

    boundaries: dict[str, int] = {}
    for surface in model.surfaces:
        key = surface.outside_boundary.casefold()
        boundaries[key] = boundaries.get(key, 0) + 1
    schedule_names = tuple(
        obj.values[0]
        for obj in model.raw_objects
        if obj.object_type.casefold().startswith("schedule:") and obj.values
    )
    return CommonBuildingData(
        source=source,
        conversion=conversion,
        thermal_data=thermal_data,
        floor_area_m2=float(geometry.get("FLOOR_AREA", floor_area)),
        volume_m3=float(geometry.get("VOLUME", volume)),
        opaque_envelope_area_m2=float(geometry.get("WALL_AREA", opaque_area)),
        window_area_m2=float(geometry.get("WINDOW_AREA", window_area)),
        opaque_ua_w_k=opaque_ua,
        window_ua_w_k=u_windows * float(geometry.get("WINDOW_AREA", window_area)),
        thermal_capacity_j_k=capacity,
        infiltration_ach=infiltration_ach,
        ventilation_ach=ventilation_ach,
        heat_recovery_efficiency=float(defaults.get("ventilation_efficiency", 0.0)),
        boundary_counts=boundaries,
        schedule_names=schedule_names,
        json_overlay=overlay,
    )


def generate_5R1C(data: CommonBuildingData) -> FiveR1CModel:
    """Aggregate shared data into the ETHlib/ISO 13790 fixed topology."""

    alpha = float(data.json_overlay.get("_alpha", 4.5))
    total_internal_area = alpha * data.floor_area_m2
    mass_area = 2.5 * data.floor_area_m2
    c_m = data.thermal_capacity_j_k
    if c_m <= 0:
        c_m = float(data.json_overlay.get("thermal_capacitance_per_floor_area", 165_000.0)) * data.floor_area_m2
    ach_total = data.infiltration_ach + data.ventilation_ach
    recovery_factor = 1.0
    if ach_total > 0:
        recovery_factor -= data.ventilation_ach / ach_total * data.heat_recovery_efficiency
    return FiveR1CModel(
        floor_area_m2=data.floor_area_m2,
        volume_m3=data.volume_m3,
        h_tr_em_w_k=data.opaque_ua_w_k,
        h_tr_w_w_k=data.window_ua_w_k,
        h_tr_ms_w_k=9.1 * mass_area,
        h_tr_is_w_k=3.45 * total_internal_area,
        h_ve_adj_w_k=1200.0 * recovery_factor * data.volume_m3 * ach_total / 3600.0,
        c_m_j_k=c_m,
        mass_area_m2=mass_area,
        total_internal_area_m2=total_internal_area,
    )


def generate_BRCM(data: CommonBuildingData):
    """Construct the detailed multi-node BRCM thermal network."""

    return brcm.generate_thermal_model(data.thermal_data)


def generate_model_pair(
    idf_path: str | Path,
    *,
    idd_path: str | Path | None = None,
    geometry_json: str | Path | None = None,
    defaults_json: str | Path | None = None,
) -> ModelPair:
    common = normalize_idf(
        idf_path,
        idd_path=idd_path,
        geometry_json=geometry_json,
        defaults_json=defaults_json,
    )
    return ModelPair(common, generate_5R1C(common), generate_BRCM(common))


def write_audit(pair: ModelPair, destination: str | Path) -> Path:
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(pair.audit(), indent=2) + "\n")
    return path
