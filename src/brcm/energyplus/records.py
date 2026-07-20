"""Parser-neutral EnergyPlus and conversion records."""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

@dataclass(frozen=True)
class IDFObject:
    object_type: str
    values: tuple[str, ...]
    field_names: tuple[str, ...] = ()
    @property
    def type(self): return self.object_type
    def field(self,name: str,default: str="") -> str:
        for i,label in enumerate(self.field_names):
            if label.casefold()==name.casefold(): return self.values[i] if i<len(self.values) else default
        return default

@dataclass
class EPZone:
    name: str; north: float=0; origin: tuple[float,float,float]=(0,0,0); height: float|None=None; volume: float|None=None; area: float|None=None
@dataclass
class EPMaterial:
    name: str; kind: str; thickness: float|None=None; conductivity: float|None=None; density: float|None=None; specific_heat: float|None=None; resistance: float|None=None
@dataclass
class EPConstruction:
    name: str; layers: list[str]
@dataclass
class EPSurface:
    name: str; surface_type: str; construction: str; zone: str; outside_boundary: str; outside_object: str; vertices: tuple[tuple[float,float,float],...]=(); area: float|None=None
@dataclass
class EPWindow:
    name: str; construction: str; parent_surface: str; vertices: tuple[tuple[float,float,float],...]; frame_area: float=0; glass_area: float|None=None
@dataclass
class EPInternalMass:
    name: str; construction: str; zone: str; area: float
@dataclass
class NormalizedEnergyPlusModel:
    version: str; coordinate_system: str; zones: list[EPZone]=field(default_factory=list); materials: list[EPMaterial]=field(default_factory=list); constructions: list[EPConstruction]=field(default_factory=list); surfaces: list[EPSurface]=field(default_factory=list); windows: list[EPWindow]=field(default_factory=list); internal_masses: list[EPInternalMass]=field(default_factory=list); raw_objects: list[IDFObject]=field(default_factory=list); ignored_object_types: tuple[str,...]=()
@dataclass(frozen=True)
class ConversionResult:
    tables: dict[str,list[list[str]]]
    normalized_model: NormalizedEnergyPlusModel
    source: Path|None=None
    warnings: tuple[str,...]=()

@dataclass(frozen=True)
class ConversionAudit:
    energyplus_version: str
    zones: int
    surfaces: int
    windows: int
    building_elements: int
    rc_states: int|None
    ambient_boundaries: int
    ground_boundaries: int
    adiabatic_boundaries: int
    interzone_boundaries: int
    ignored_object_types: tuple[str,...]
    warnings: tuple[str,...]
