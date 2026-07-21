import numpy as np

from brcm import AHU, BEHeatfluxes, BuildingHull, InternalGains, Radiators, SimulationExperiment, ThermalModelData, compose_building_model, generate_thermal_model


def test_deterministic_simulation_matches_matlab_fixture(matlab_reference):
    data=ThermalModelData.from_directory("origin_matlab/toolbox/BuildingData/DemoBuilding/ThermalModel"); thermal=generate_thermal_model(data); root="origin_matlab/toolbox/BuildingData/DemoBuilding/EHFM"
    models=[BuildingHull(data,thermal,"BuildingHull",root+"/buildinghull"),AHU(data,thermal,"AHU1",root+"/ahu"),InternalGains(data,thermal,"IG",root+"/internalgains"),BEHeatfluxes(data,thermal,"TABS",root+"/BEHeatfluxes"),Radiators(data,thermal,"Rad",root+"/radiators")]
    building=compose_building_model(thermal,models); building.discretize(matlab_reference.manifest["sampling_time_hours"])
    reference=matlab_reference.matrices; x0=reference["simulation.x0"]
    requested_u=reference["simulation.requested_U"]; requested_v=reference["simulation.requested_V"]
    experiment=SimulationExperiment(building); experiment.setNumberOfSimulationTimeSteps(requested_u.shape[1]); experiment.setInitialState(x0)
    X,U,V,t=experiment.simulateBuildingModel("inputTrajectory",requested_u,requested_v)
    np.testing.assert_allclose(x0,reference["simulation.x0"],rtol=1e-10,atol=1e-12)
    np.testing.assert_array_equal(requested_u,reference["simulation.requested_U"])
    np.testing.assert_array_equal(requested_v,reference["simulation.requested_V"])
    np.testing.assert_allclose(U,reference["simulation.U"],rtol=1e-10,atol=1e-12)
    np.testing.assert_allclose(V,reference["simulation.V"],rtol=1e-10,atol=1e-12)
    np.testing.assert_allclose(X,reference["simulation.X"],rtol=1e-10,atol=1e-12)
    np.testing.assert_allclose(t,reference["simulation.t_hrs"],rtol=1e-10,atol=1e-12)
