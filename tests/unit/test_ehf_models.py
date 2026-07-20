from __future__ import annotations

import numpy as np
import pytest

from brcm import (
    AHU, BEHeatfluxes, BuildingHull, EHFModelBaseClass, EHF_REGISTRY,
    Identifier, InternalGains, Radiators, ThermalModelData, generate_thermal_model,
)
from brcm.exceptions import ValidationError


ROOT = "BuildingData/DemoBuilding"


@pytest.fixture(scope="module")
def demo():
    data = ThermalModelData.from_directory(f"{ROOT}/ThermalModel")
    return data, generate_thermal_model(data)


class Dummy(EHFModelBaseClass):
    def get_constraints_matrices(self, parameters): return self._empty_constraints()
    def get_cost_vector(self, parameters): return np.ones((len(self.identifiers.u), 1))


def test_base_remapping_expansion_nan_and_shape_validation(demo):
    data, thermal = demo
    obj = Dummy(data, thermal, "dummy", f"{ROOT}/EHFM/internalgains.csv")
    obj.identifiers.u = ["u_b", "u_a"]; obj.identifiers.v = ["v_b"]
    obj._zeros(); obj.Bq_u[0] = [2, 3]; obj.Bq_xu[0, 1] = [4, 5]; obj.Bq_vu[0, 0] = [6, 7]
    prescribed = Identifier(x=obj.identifiers.x, q=obj.identifiers.q, u=["u_a", "u_b", "u_c"], v=["v_a", "v_b"])
    _, bu, _, bxu, bvu = obj.get_prescribed_size_system_matrices(prescribed)
    np.testing.assert_array_equal(bu[0], [3, 2, 0]); np.testing.assert_array_equal(bxu[0, 1], [5, 4, 0]); np.testing.assert_array_equal(bvu[0, 1], [7, 6, 0])
    assert obj.get_prescribed_size_cost_vector(prescribed, {}).shape == (3, 1)
    obj.Bq_u[0, 0] = np.nan
    with pytest.raises(ValidationError, match="NaN"): obj.check_nan()
    obj.Bq_u = np.zeros((1, 1))
    with pytest.raises(ValidationError, match="shape"): obj.check_nan()


def test_internal_gains_demo_terms_and_order(demo):
    data, thermal = demo; model = InternalGains(data, thermal, "IG", f"{ROOT}/EHFM/internalgains")
    assert model.identifiers.v == ["v_IG_NonOffices", "v_IG_Offices"]
    assert np.count_nonzero(model.Bq_v) == 20
    assert not np.count_nonzero(model.Aq) and model.Bq_xu.shape == (390, 390, 0)
    assert model.Bq_v[model.identifiers.q.index("q_Z0001"), model.identifiers.v.index("v_IG_Offices")] > 0


def test_radiators_constraints_cost_and_sign(demo):
    data, thermal = demo; model = Radiators(data, thermal, "Rad", f"{ROOT}/EHFM/radiators")
    assert model.identifiers.u == ["u_rad_CornerOffices", "u_rad_Offices"]
    assert np.all(model.Bq_u[model.Bq_u != 0] > 0)
    p = {name: (0 if name.endswith("_min") else 100) for name in model.identifiers.constraints}
    fx, fu, fv, g, names = model.get_constraints_matrices(p)
    assert fx.shape == (4,390) and fu.shape == (4,2) and fv.shape == (4,0) and g.shape == (4,1) and names == model.identifiers.constraints
    assert np.count_nonzero(fu) == 4
    assert np.all(model.get_cost_vector({"costPerJouleHeated":2}) > 0)


def test_beheatfluxes_heating_cooling_constraints_and_cost(demo):
    data, thermal = demo; model = BEHeatfluxes(data, thermal, "TABS", f"{ROOT}/EHFM/BEHeatfluxes")
    assert model.identifiers.u == ["u_BEH_cTABS_cool", "u_BEH_hTABS_heat"]
    assert np.any(model.Bq_u < 0) and np.any(model.Bq_u > 0)
    assert np.count_nonzero(model.Bq_u) == 15
    p = {name: (0 if name.endswith("_min") else 100) for name in model.identifiers.constraints}
    assert model.get_constraints_matrices(p)[1].shape == (4,2)
    cost = model.get_cost_vector({"Ts_hrs":1, "costPerJouleHeated":2, "costPerJouleCooled":3})
    assert cost.shape == (2,1) and np.all(cost > 0)


def test_building_hull_linear_bilinear_boundaries_and_constraints(demo):
    data, thermal = demo; model = BuildingHull(data, thermal, "BuildingHull", f"{ROOT}/EHFM/buildinghull")
    assert model.identifiers.u == ["u_blinds_E", "u_blinds_L", "u_blinds_N", "u_blinds_S", "u_blinds_W"]
    assert model.identifiers.v == ["v_Tamb", "v_solGlobFac_E", "v_solGlobFac_N", "v_solGlobFac_S", "v_solGlobFac_W", "v_solGlobFac_W2"]
    assert np.any(model.Aq < 0) and np.any(model.Bq_v > 0) and np.any(model.Bq_vu > 0)
    assert not np.count_nonzero(model.Bq_u) and not np.count_nonzero(model.Bq_xu)
    p = {name: (0.1 if name.endswith("_min") else 1) for name in model.identifiers.constraints}
    assert model.get_constraints_matrices(p)[1].shape == (10,5)
    assert np.count_nonzero(model.get_cost_vector({})) == 0


def test_ahu_bilinear_signs_constraints_cost(demo):
    data, thermal = demo; model = AHU(data, thermal, "AHU1", f"{ROOT}/EHFM/ahu")
    assert model.identifiers.u == ["u_AHU1_noERC", "u_AHU1_ERC", "u_AHU1_evapCooler", "u_AHU1_heater"]
    assert model.identifiers.v == ["v_Tamb", "v_AHU1_Dwb"]
    assert np.any(model.Bq_xu > 0) and np.any(model.Bq_xu < 0)
    assert np.any(model.Bq_vu > 0) and np.any(model.Bq_vu < 0)
    full = Identifier(x=thermal.state_identifiers, q=thermal.heat_flux_identifiers, v=model.identifiers.v)
    p = dict(mdot_min=0,mdot_max=1,T_supply_min=22,T_supply_max=30,Q_heat_min=0,Q_heat_max=1000,
             x=np.full(390,23.),v_fullModel=np.full(2,20.),identifiers_fullModel=full)
    assert model.get_constraints_matrices(p)[1].shape == (10,4)
    cost=model.get_cost_vector(dict(Ts_hrs=1,costPerKgAirTransported=1,costPerJouleHeated=10,costPerKgCooledByEvapCooler=10))
    assert cost.shape == (4,1) and np.all(cost > 0)


def test_all_demo_models_are_deterministic_and_registry_is_explicit(demo):
    data, thermal = demo
    specs=[(InternalGains,"IG","internalgains"),(Radiators,"Rad","radiators"),(BEHeatfluxes,"TABS","BEHeatfluxes"),(BuildingHull,"BuildingHull","buildinghull"),(AHU,"AHU1","ahu")]
    assert list(EHF_REGISTRY) == ["InternalGains","Radiators","BEHeatfluxes","BuildingHull","AHU"]
    for cls, identifier, filename in specs:
        one=cls(data,thermal,identifier,f"{ROOT}/EHFM/{filename}"); two=cls(data,thermal,identifier,f"{ROOT}/EHFM/{filename}")
        assert one.identifiers == two.identifiers
        for name in ("Aq","Bq_u","Bq_v","Bq_xu","Bq_vu"): np.testing.assert_array_equal(getattr(one,name),getattr(two,name))
