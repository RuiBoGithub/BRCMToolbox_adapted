from __future__ import annotations

import numpy as np
import pytest
from scipy.linalg import expm

from brcm import (
    AHU, BEHeatfluxes, BuildingHull, BuildingModel, EHFModelBaseClass,
    Identifier, InternalGains, Radiators, ThermalModel, ThermalModelData,
    compose_building_model, generate_thermal_model,
)
from brcm.exceptions import ValidationError


SOURCE="origin_matlab/toolbox/BuildingData/DemoBuilding/EHFM/internalgains.csv"


class SyntheticEHF(EHFModelBaseClass):
    def __init__(self, thermal, u=(), v=(), constraints=(), cost=()):
        # Avoid data parsing while retaining the production base-class contract.
        self.thermal_model=thermal; self.data=None; self.EHF_identifier="synthetic"; self.source_file=SOURCE
        self.identifiers=Identifier(x=list(thermal.state_identifiers),q=list(thermal.heat_flux_identifiers),u=list(u),v=list(v),constraints=list(constraints))
        self._zeros(); self.cost=np.asarray(cost if cost else np.zeros(len(u)),dtype=float)
    def get_constraints_matrices(self, parameters):
        fx,fu,fv,g,names=self._empty_constraints()
        for i in range(len(names)):
            if fu.shape[1]: fu[i,0]=1
            g[i,0]=parameters.get(names[i],0)
        return fx,fu,fv,g,names
    def get_cost_vector(self, parameters): return self.cost.reshape(-1,1)


def thermal(A):
    A=np.asarray(A,dtype=float); n=A.shape[0]
    return ThermalModel(A,np.eye(n),np.eye(n),[f"x_Z{i+1:04d}" for i in range(n)],[f"q_Z{i+1:04d}" for i in range(n)])


def test_linear_ehf_composition_exact_equation():
    t=thermal([[-2.] ]); e=SyntheticEHF(t,u=["u_a"],v=["v_a"])
    e.Aq[0,0]=.5; e.Bq_u[0,0]=3; e.Bq_v[0,0]=4
    model=compose_building_model(t,[e])
    np.testing.assert_array_equal(model.A,[[-1.5]]); np.testing.assert_array_equal(model.Bu,[[3]]); np.testing.assert_array_equal(model.Bv,[[4]])


def test_shared_u_is_rejected_as_matlab_load_ehf_model_requires():
    t=thermal([[-1.]])
    with pytest.raises(ValidationError,match="Duplicate input"):
        compose_building_model(t,[SyntheticEHF(t,u=["u_shared"]),SyntheticEHF(t,u=["u_shared"])])


def test_shared_v_is_sorted_merged_and_accumulated():
    t=thermal([[-1.] ]); a=SyntheticEHF(t,v=["v_shared","v_z"]); b=SyntheticEHF(t,v=["v_a","v_shared"])
    a.Bq_v[0]=[2,4]; b.Bq_v[0]=[8,16]
    model=compose_building_model(t,[a,b])
    assert model.identifiers.v == ["v_a","v_shared","v_z"]
    np.testing.assert_array_equal(model.Bv[0],[8,18,4])


def test_bilinear_axis_mapping_and_empty_dimensions():
    t=thermal([[-1.,0.],[0.,-2.] ]); e=SyntheticEHF(t,u=["u_a"],v=["v_a"])
    e.Bq_xu[1,0,0]=3; e.Bq_vu[0,0,0]=4
    model=compose_building_model(t,[e])
    assert model.Bxu.shape==(2,2,1) and model.Bvu.shape==(2,1,1)
    assert model.Bxu[1,0,0]==3 and model.Bvu[0,0,0]==4
    empty=compose_building_model(t,[])
    assert empty.Bu.shape==(2,0) and empty.Bv.shape==(2,0) and empty.Bxu.shape==(2,2,0)


def test_constraints_stack_in_model_order_and_costs_sum_by_global_mapping():
    t=thermal([[-1.] ]); a=SyntheticEHF(t,u=["u_a"],constraints=["c_a"],cost=[2]); a.EHF_identifier="a"
    b=SyntheticEHF(t,u=["u_b"],constraints=["c_b"],cost=[3]); b.EHF_identifier="b"
    model=compose_building_model(t,[a,b]); model.set_discretization_step(.25)
    fx,fu,fv,g,names=model.get_constraints_matrices({"a":{"c_a":4},"b":{"c_b":5}})
    assert names==["c_a","c_b"] and fu.shape==(2,2); np.testing.assert_array_equal(g[:,0],[4,5])
    np.testing.assert_array_equal(model.get_cost_vector({}),[[2],[3]])


def test_outputs_are_empty_not_identity():
    model=compose_building_model(thermal([[-1.]]),[])
    assert model.identifiers.y==[] and model.C.shape==(0,1) and model.Du.shape==(0,0) and model.Dxu.shape==(0,1,0)


@pytest.mark.parametrize("hours",[1/3600,.25,1.0])
def test_scalar_stable_discretization_matches_analytic_solution(hours):
    t=thermal([[-2.] ]); e=SyntheticEHF(t,u=["u"]); e.Bq_u[0,0]=3
    model=compose_building_model(t,[e]); d=model.discretize(hours); seconds=hours*3600
    np.testing.assert_allclose(d.A,[[np.exp(-2*seconds)]])
    np.testing.assert_allclose(d.Bu,[[(1-np.exp(-2*seconds))*3/2]])
    np.testing.assert_array_equal(d.A,model.discretize(hours).A)


def test_coupled_two_state_discretization():
    A=np.array([[-2.,1.],[1.,-3.] ]); t=thermal(A); e=SyntheticEHF(t,u=["u"]); e.Bq_u[:,0]=[1,2]
    model=compose_building_model(t,[e]); d=model.discretize(1/3600)
    np.testing.assert_allclose(d.A,expm(A)); np.testing.assert_allclose(A@d.Bu,(d.A-np.eye(2))@e.Bq_u)


@pytest.mark.parametrize("A",[np.zeros((1,1)),np.array([[0.,1.],[0.,0.]])])
def test_zero_and_singular_A_use_exact_augmented_exponential(A):
    t=thermal(A); e=SyntheticEHF(t,u=["u"]); e.Bq_u[:,0]=np.arange(1,A.shape[0]+1)
    d=compose_building_model(t,[e]).discretize(1/3600)
    n=A.shape[0]; aug=np.zeros((n+1,n+1)); aug[:n,:n]=A; aug[:n,n:]=e.Bq_u
    expected=expm(aug)
    np.testing.assert_allclose(d.A,expected[:n,:n]); np.testing.assert_allclose(d.Bu,expected[:n,n:])


def test_demo_building_composition_discretization_constraints_cost_and_determinism():
    data=ThermalModelData.from_directory("origin_matlab/toolbox/BuildingData/DemoBuilding/ThermalModel"); t=generate_thermal_model(data); root="origin_matlab/toolbox/BuildingData/DemoBuilding/EHFM"
    def build():
        models=[BuildingHull(data,t,"BuildingHull",root+"/buildinghull"),AHU(data,t,"AHU1",root+"/ahu"),InternalGains(data,t,"IG",root+"/internalgains"),BEHeatfluxes(data,t,"TABS",root+"/BEHeatfluxes"),Radiators(data,t,"Rad",root+"/radiators")]
        return compose_building_model(t,models)
    one=build(); two=build()
    assert (len(one.identifiers.x),len(one.identifiers.q),len(one.identifiers.u),len(one.identifiers.v),len(one.identifiers.y),len(one.identifiers.constraints))==(390,390,13,9,0,28)
    np.testing.assert_array_equal(one.A,t.A + t.Bq@sum((m.Aq for m in one.EHF_submodels),start=np.zeros((390,390))))
    for name in ("A","Bu","Bv","Bxu","Bvu"): np.testing.assert_array_equal(getattr(one,name),getattr(two,name))
    one.discretize(.25); two.discretize(.25)
    for name in ("Ad","Bdu","Bdv","Bdxu","Bdvu"): np.testing.assert_array_equal(getattr(one,name),getattr(two,name))
    p={"AHU1":dict(mdot_min=0,mdot_max=1,T_supply_min=22,T_supply_max=30,Q_heat_min=0,Q_heat_max=1000,x=np.full(390,23.),v_fullModel=np.full(9,20.)),
       "BuildingHull":{},"TABS":{},"Rad":{}}
    for name in one.EHF_submodels[0].identifiers.constraints: p["BuildingHull"][name]=.1 if name.endswith("min") else 1
    for model_id,index in (("TABS",3),("Rad",4)):
        for name in one.EHF_submodels[index].identifiers.constraints: p[model_id][name]=0 if name.endswith("min") else 1000
    assert one.get_constraints_matrices(p)[0].shape==(28,390)
    costs={"AHU1":dict(costPerKgAirTransported=1,costPerJouleHeated=10,costPerKgCooledByEvapCooler=10),"TABS":dict(costPerJouleHeated=10,costPerJouleCooled=10),"Rad":dict(costPerJouleHeated=10)}
    assert one.get_cost_vector(costs).shape==(13,1)
