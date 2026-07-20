from __future__ import annotations

import numpy as np
import pytest

from brcm import (
    BuildingElement, Construction, Material, NoMassConstruction, Parameter,
    ThermalModelData, Zone, generate_thermal_model,
)
from brcm.exceptions import ValidationError


def massive(identifier="M0001", cp="1000", resistance="2", density="1000"):
    return Material(identifier, "mass", cp, resistance, density, "")


def dataset(*, zones=None, elements=None, construction=None, materials=None, nomass=None, parameters=None):
    data = ThermalModelData()
    data.zones = zones or [Zone("Z0001", "zone", "10", "30", ["G"])]
    data.materials = materials or [massive()]
    data.constructions = construction or [Construction("C0001", "wall", ["M0001"], ["0.1"], "10", "5")]
    data.nomass_constructions = nomass or []
    data.parameters = parameters or []
    data.building_elements = elements or [BuildingElement("B0001", "wall", "C0001", "AMB", "Z0001", "", "2", ())]
    return data


def assert_model_contract(model):
    n = len(model.state_identifiers)
    assert model.A.shape == model.Bq.shape == model.Xcap.shape == (n, n)
    assert len(model.heat_flux_identifiers) == n
    assert np.isfinite(model.A).all() and np.isfinite(model.Bq).all()
    assert np.all(np.diag(model.Xcap) > 0)
    assert np.all(np.diag(model.A) <= 0)
    offdiag = model.A.copy(); np.fill_diagonal(offdiag, 0)
    assert np.all(offdiag >= 0)


def test_single_zone_external_opaque_element_and_ambient_boundary():
    model = generate_thermal_model(dataset())
    assert model.state_identifiers == ["x_Z0001", "x_B0001_L1_s1_AMBZ0001"]
    assert model.heat_flux_identifiers == ["q_Z0001", "q_B0001_L1_s1_AMBZ0001"]
    assert_model_contract(model)
    assert len(model.boundary_conditions["ambient"]) == 1
    abar = model.Xcap @ model.A
    np.testing.assert_allclose(abar.sum(axis=1), 0, atol=1e-12)
    np.testing.assert_allclose(abar, abar.T)
    np.testing.assert_allclose(model.Bq, np.diag(1 / np.diag(model.Xcap)))


def test_two_zones_internal_wall_is_reciprocal():
    zones = [Zone("Z0001", "a", "10", "30", ["G"]), Zone("Z0002", "b", "10", "40", ["G"])]
    be = BuildingElement("B0001", "wall", "C0001", "Z0001", "Z0002", "", "2", ())
    model = generate_thermal_model(dataset(zones=zones, elements=[be]))
    assert model.state_identifiers == ["x_Z0001", "x_Z0002", "x_B0001_L1_s1_Z0001Z0002"]
    abar = model.Xcap @ model.A
    np.testing.assert_allclose(abar, abar.T)
    np.testing.assert_allclose(abar.sum(axis=1), 0, atol=1e-12)


def test_multilayer_construction_preserves_layer_numbers_and_couples_states():
    mats = [massive("M0001"), Material("M0002", "gap", "", "", "", "0.4"), massive("M0003", resistance="4")]
    cons = [Construction("C0001", "multi", ["M0001", "M0002", "M0003"], ["0.1", "0", "0.2"], "10", "5")]
    model = generate_thermal_model(dataset(construction=cons, materials=mats))
    assert model.state_identifiers[-2:] == ["x_B0001_L1_s1_AMBZ0001", "x_B0001_L3_s1_AMBZ0001"]
    assert (model.Xcap @ model.A)[1, 2] > 0
    assert_model_contract(model)


def test_direct_nomass_construction_has_no_element_state():
    be = BuildingElement("B0001", "door", "NMC0001", "Z0001", "Z0002", "", "2", ())
    zones = [Zone("Z0001", "a", "10", "30", ["G"]), Zone("Z0002", "b", "10", "30", ["G"])]
    model = generate_thermal_model(dataset(zones=zones, elements=[be], nomass=[NoMassConstruction("NMC0001", "door", "3")]))
    assert model.state_identifiers == ["x_Z0001", "x_Z0002"]
    np.testing.assert_allclose((model.Xcap @ model.A)[0, 1], 6.0)


@pytest.mark.parametrize(("boundary", "bucket"), [("AMB", "ambient"), ("GND", "ground")])
def test_external_boundary_is_recorded_not_inserted(boundary, bucket):
    be = BuildingElement("B0001", "wall", "C0001", boundary, "Z0001", "", "2", ())
    model = generate_thermal_model(dataset(elements=[be]))
    assert len(model.boundary_conditions[bucket]) == 1
    np.testing.assert_allclose((model.Xcap @ model.A).sum(axis=1), 0, atol=1e-12)


def test_parameter_valued_material_properties():
    params = [Parameter("cp", "", "900"), Parameter("rho", "", "800"), Parameter("r", "", "2")]
    model = generate_thermal_model(dataset(materials=[massive(cp="cp", density="rho", resistance="r")], parameters=params))
    np.testing.assert_allclose(model.Xcap[1, 1], 2 * .1 * 800 * 900)


def test_all_massless_material_construction_connects_zones_without_state():
    mat = Material("M0001", "insulation", "", "", "", "0.5")
    zones = [Zone("Z0001", "a", "10", "30", ["G"]), Zone("Z0002", "b", "10", "30", ["G"])]
    be = BuildingElement("B0001", "partition", "C0001", "Z0001", "Z0002", "", "2", ())
    model = generate_thermal_model(dataset(zones=zones, elements=[be], materials=[mat]))
    assert len(model.state_identifiers) == 2
    assert (model.Xcap @ model.A)[0, 1] > 0


def test_invalid_zero_net_area_is_rejected():
    data = dataset()
    data.building_elements[0].area = "0"
    with pytest.raises(ValidationError):
        generate_thermal_model(data)


def test_demo_building_generation_is_finite_structural_and_deterministic():
    data = ThermalModelData.from_directory("BuildingData/DemoBuilding/ThermalModel")
    first = generate_thermal_model(data)
    second = generate_thermal_model(data)
    assert len(first.state_identifiers) == 390
    assert first.A.shape == first.Bq.shape == first.Xcap.shape == (390, 390)
    assert first.state_identifiers == second.state_identifiers
    assert first.heat_flux_identifiers == second.heat_flux_identifiers
    np.testing.assert_array_equal(first.A, second.A)
    np.testing.assert_array_equal(first.Bq, second.Bq)
    np.testing.assert_array_equal(first.Xcap, second.Xcap)
    assert np.isfinite(first.A).all()
    assert np.isfinite(first.Bq).all()
    assert np.isfinite(first.Xcap).all()
    assert np.count_nonzero(first.A) == 1222
    # q inputs are one-for-one state heat injections; only their own rows act.
    assert np.count_nonzero(first.Bq) == 390
