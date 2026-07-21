import numpy as np

from brcm import ThermalModelData, generate_thermal_model


def test_thermal_generation_matches_matlab_fixture(matlab_reference):
    data = ThermalModelData.from_directory("origin_matlab/toolbox/BuildingData/DemoBuilding/ThermalModel")
    model = generate_thermal_model(data)
    identifiers = matlab_reference.manifest["identifiers"]
    assert model.state_identifiers == identifiers["x"]
    assert model.heat_flux_identifiers == identifiers["q"]
    np.testing.assert_allclose(model.A, matlab_reference.matrices["thermal.A"], rtol=1e-10, atol=1e-12)
    np.testing.assert_allclose(model.Bq, matlab_reference.matrices["thermal.Bq"], rtol=1e-10, atol=1e-12)
    np.testing.assert_allclose(model.Xcap, matlab_reference.matrices["thermal.Xcap"], rtol=1e-10, atol=1e-12)
