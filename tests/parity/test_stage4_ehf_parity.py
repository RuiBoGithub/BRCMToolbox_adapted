import numpy as np

from brcm import AHU, BEHeatfluxes, BuildingHull, Identifier, InternalGains, Radiators, ThermalModelData, generate_thermal_model


def test_ehf_matrices_match_matlab_fixtures(matlab_reference):
    data=ThermalModelData.from_directory("BuildingData/DemoBuilding/ThermalModel"); thermal=generate_thermal_model(data)
    definitions={"BuildingHull":(BuildingHull,"buildinghull"),"AHU1":(AHU,"ahu"),"IG":(InternalGains,"internalgains"),"TABS":(BEHeatfluxes,"BEHeatfluxes"),"Rad":(Radiators,"radiators")}
    for entry in matlab_reference.manifest["ehf_models"]:
        identifier=entry["identifier"]; cls,filename=definitions[identifier]
        model=cls(data,thermal,identifier,f"BuildingData/DemoBuilding/EHFM/{filename}")
        assert model.identifiers.x == entry["identifiers"]["x"]
        assert model.identifiers.q == entry["identifiers"]["q"]
        assert model.identifiers.u == entry["identifiers"]["u"]
        assert model.identifiers.v == entry["identifiers"]["v"]
        for python_name,fixture_name in (("Aq","Aq"),("Bq_u","Bq_u"),("Bq_v","Bq_v"),("Bq_xu","Bq_xu"),("Bq_vu","Bq_vu")):
            np.testing.assert_allclose(getattr(model,python_name),matlab_reference.matrices[f"ehf.{identifier}.{fixture_name}"],rtol=1e-10,atol=1e-12)


def test_ehf_constraints_and_cost_match_exported_matlab_totals(matlab_reference):
    data=ThermalModelData.from_directory("BuildingData/DemoBuilding/ThermalModel"); thermal=generate_thermal_model(data)
    definitions=[(BuildingHull,"BuildingHull","buildinghull"),(AHU,"AHU1","ahu"),(InternalGains,"IG","internalgains"),(BEHeatfluxes,"TABS","BEHeatfluxes"),(Radiators,"Rad","radiators")]
    models=[cls(data,thermal,identifier,f"BuildingData/DemoBuilding/EHFM/{filename}") for cls,identifier,filename in definitions]
    ids=matlab_reference.manifest["identifiers"]
    full=Identifier(x=ids["x"],q=ids["q"],u=ids["u"],v=ids["v"],constraints=ids["constraints"])
    constraint_parameters={}
    values=matlab_reference.matrices["parameters.constraint_values"].reshape(-1)
    for name,value in zip(matlab_reference.manifest["constraint_parameter_names"],values):
        model_id,key=name.split(".",1); constraint_parameters.setdefault(model_id,{})[key]=float(value)
    constraint_parameters.setdefault("AHU1",{}).update(
        x=matlab_reference.matrices["parameters.AHU1.x"].reshape(-1),
        v_fullModel=matlab_reference.matrices["parameters.AHU1.v_fullModel"].reshape(-1),
    )
    blocks=[]
    for model in models:
        parameters=dict(constraint_parameters.get(model.EHF_identifier,{}),identifiers_fullModel=full)
        blocks.append(model.get_prescribed_size_constraints_matrices(full,parameters))
    stacked_names=[name for block in blocks for name in block[4]]; permutation=[stacked_names.index(name) for name in full.constraints]
    for position,key in enumerate(("constraints.Fx","constraints.Fu","constraints.Fv","constraints.g")):
        actual=np.vstack([block[position] for block in blocks])[permutation]
        np.testing.assert_allclose(actual,matlab_reference.matrices[key],rtol=1e-10,atol=1e-12)
    cost_parameters={}
    values=matlab_reference.matrices["parameters.cost_values"].reshape(-1)
    for name,value in zip(matlab_reference.manifest["cost_parameter_names"],values):
        model_id,key=name.split(".",1); cost_parameters.setdefault(model_id,{})[key]=float(value)
    actual=np.zeros((len(full.u),1))
    for model in models:
        parameters=dict(cost_parameters.get(model.EHF_identifier,{}),Ts_hrs=matlab_reference.manifest["sampling_time_hours"],identifiers_fullModel=full)
        actual += model.get_prescribed_size_cost_vector(full,parameters)
    np.testing.assert_allclose(actual,matlab_reference.matrices["cost.cu"],rtol=1e-10,atol=1e-12)
