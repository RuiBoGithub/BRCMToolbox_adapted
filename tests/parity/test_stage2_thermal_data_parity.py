"""Stage-2 checks activated once MATLAB's Stage-1 fixtures exist."""

from brcm import ThermalModelData


def test_python_loaded_record_order_matches_matlab_fixture(matlab_reference):
    source = matlab_reference.root.parents[2] / "BuildingData" / "DemoBuilding" / "ThermalModel"
    # Installed/relocated fixtures need not live below the repository. In the
    # normal source tree, use the repository data; otherwise this test is not
    # applicable yet.
    if not source.is_dir():
        import pytest

        pytest.skip("MATLAB fixture is not located in the BRCM source tree")
    python_data = ThermalModelData.from_directory(source)
    fixture_data = matlab_reference.thermal_model_data
    mapping = {
        "zones": python_data.zones,
        "building_elements": python_data.building_elements,
        "constructions": python_data.constructions,
        "materials": python_data.materials,
        "windows": python_data.windows,
        "parameters": python_data.parameters,
        "nomass_constructions": python_data.nomass_constructions,
    }
    for name, records in mapping.items():
        assert [record.identifier for record in records] == [record["identifier"] for record in fixture_data[name]]

