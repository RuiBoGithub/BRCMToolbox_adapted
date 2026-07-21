"""BRCM Python migration package.

Stage 1 intentionally exposes only MATLAB parity-fixture loading helpers.
"""

from .constants import Constants
from .parity import ReferenceFixture, load_reference_fixture
from .primitives import BoundaryCondition, Identifier, Vertex
from .records import (
    BuildingElement,
    Construction,
    Material,
    NoMassConstruction,
    Parameter,
    Window,
    Zone,
)
from .thermal_data import ThermalModelData
from .thermal_generation import (
    check_thermal_model_data_consistency,
    generate_thermal_model,
)
from .thermal_model import ThermalModel
from .ehf import AHU, BEHeatfluxes, BuildingHull, EHFModelBaseClass, EHF_REGISTRY, InternalGains, Radiators
from .building_model import BuildingModel, ContinuousModel, DiscreteModel, compose_building_model, generate_building_model
from .simulation import BuildingSimulationResult, SimulationExperiment, ThermalSimulationResult, simulate_bm, simulate_building_model, simulate_tm, simulate_thermal_model
from .energyplus import (
    audit_conversion,
    conversion_to_thermal_model_data,
    convert_idf_to_brcm,
    convert_idf_to_brcm_data,
    from_energyplus,
)

__all__ = [
    "BoundaryCondition", "BuildingElement", "Constants", "Construction",
    "Identifier", "Material", "NoMassConstruction", "Parameter",
    "ReferenceFixture", "ThermalModel", "ThermalModelData", "Vertex", "Window", "Zone",
    "check_thermal_model_data_consistency", "generate_thermal_model",
    "AHU", "BEHeatfluxes", "BuildingHull", "EHFModelBaseClass", "EHF_REGISTRY",
    "InternalGains", "Radiators",
    "BuildingModel", "ContinuousModel", "DiscreteModel", "compose_building_model", "generate_building_model",
    "BuildingSimulationResult", "SimulationExperiment", "ThermalSimulationResult",
    "simulate_bm", "simulate_building_model", "simulate_tm", "simulate_thermal_model",
    "audit_conversion", "conversion_to_thermal_model_data", "convert_idf_to_brcm",
    "convert_idf_to_brcm_data", "from_energyplus",
    "load_reference_fixture",
]
