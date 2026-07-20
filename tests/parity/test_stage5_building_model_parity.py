import numpy as np

from brcm import AHU, BEHeatfluxes, BuildingHull, InternalGains, Radiators, ThermalModelData, compose_building_model, generate_thermal_model


def test_complete_building_model_matches_matlab_fixture(matlab_reference):
    data=ThermalModelData.from_directory("BuildingData/DemoBuilding/ThermalModel"); thermal=generate_thermal_model(data); root="BuildingData/DemoBuilding/EHFM"
    models=[BuildingHull(data,thermal,"BuildingHull",root+"/buildinghull"),AHU(data,thermal,"AHU1",root+"/ahu"),InternalGains(data,thermal,"IG",root+"/internalgains"),BEHeatfluxes(data,thermal,"TABS",root+"/BEHeatfluxes"),Radiators(data,thermal,"Rad",root+"/radiators")]
    model=compose_building_model(thermal,models); model.discretize(matlab_reference.manifest["sampling_time_hours"])
    expected=matlab_reference.manifest["identifiers"]
    for name in ("x","q","u","v","y","constraints"): assert getattr(model.identifiers,name)==expected[name]
    for name in ("A","Bu","Bv","Bxu","Bvu","C","Du","Dv","Dxu","Dvu"):
        np.testing.assert_allclose(getattr(model.continuous_time_model,name),matlab_reference.matrices[f"continuous.{name}"],rtol=1e-10,atol=1e-12)
        np.testing.assert_allclose(getattr(model.discrete_time_model,name),matlab_reference.matrices[f"discrete.{name}"],rtol=1e-10,atol=1e-12)


def test_complete_constraints_and_cost_match_matlab_fixture(matlab_reference):
    data=ThermalModelData.from_directory("BuildingData/DemoBuilding/ThermalModel"); thermal=generate_thermal_model(data); root="BuildingData/DemoBuilding/EHFM"
    models=[BuildingHull(data,thermal,"BuildingHull",root+"/buildinghull"),AHU(data,thermal,"AHU1",root+"/ahu"),InternalGains(data,thermal,"IG",root+"/internalgains"),BEHeatfluxes(data,thermal,"TABS",root+"/BEHeatfluxes"),Radiators(data,thermal,"Rad",root+"/radiators")]
    model=compose_building_model(thermal,models); model.set_discretization_step(matlab_reference.manifest["sampling_time_hours"])
    parameters={}; values=matlab_reference.matrices["parameters.constraint_values"].reshape(-1)
    for name,value in zip(matlab_reference.manifest["constraint_parameter_names"],values):
        identifier,key=name.split(".",1); parameters.setdefault(identifier,{})[key]=float(value)
    parameters["AHU1"].update(x=matlab_reference.matrices["parameters.AHU1.x"].reshape(-1),v_fullModel=matlab_reference.matrices["parameters.AHU1.v_fullModel"].reshape(-1))
    fx,fu,fv,g,_=model.get_constraints_matrices(parameters)
    for value,key in ((fx,"Fx"),(fu,"Fu"),(fv,"Fv"),(g,"g")): np.testing.assert_allclose(value,matlab_reference.matrices[f"constraints.{key}"],rtol=1e-10,atol=1e-12)
    costs={}; values=matlab_reference.matrices["parameters.cost_values"].reshape(-1)
    for name,value in zip(matlab_reference.manifest["cost_parameter_names"],values):
        identifier,key=name.split(".",1); costs.setdefault(identifier,{})[key]=float(value)
    np.testing.assert_allclose(model.get_cost_vector(costs),matlab_reference.matrices["cost.cu"],rtol=1e-10,atol=1e-12)
