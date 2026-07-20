from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from brcm import ThermalModelData
from brcm.constants import Constants
from brcm.exceptions import ExpressionError, ValidationError


ROOT = Path(__file__).parents[2]
DEMO = ROOT / "BuildingData" / "DemoBuilding" / "ThermalModel"


@pytest.fixture()
def demo_data():
    return ThermalModelData.from_directory(DEMO)


def test_loads_all_seven_demo_tables_in_source_order(demo_data):
    assert len(demo_data.zones) == 20
    assert len(demo_data.building_elements) == 124
    assert len(demo_data.constructions) == 10
    assert len(demo_data.materials) == 18
    assert len(demo_data.windows) == 20
    assert len(demo_data.parameters) == 12
    assert len(demo_data.nomass_constructions) == 1
    assert [zone.identifier for zone in demo_data.zones[:3]] == ["Z0001", "Z0002", "Z0003"]
    assert demo_data.get_zone_idx_from_identifier("Z0001") == 0
    assert demo_data.get_zone_identifiers_from_group_identifier("ZoneGrp_North") == [
        "Z0002", "Z0018", "Z0019", "Z0020"
    ]
    assert all(path is not None and path.suffix == ".csv" for path in demo_data.source_files.values())


def test_get_value_evaluates_numeric_and_parameter_references(demo_data):
    assert demo_data.getValue("M0001", "specific_heat_capacity") == 1000
    assert demo_data.getValue("W0001", "U_value") == 1
    assert demo_data.getValue("W0001", "description").startswith("EP Surface")
    assert demo_data.getValue("C0001", "material_identifiers") == ["M0002", "M0014", "M0015", "M0003"]
    with pytest.raises(ValidationError):
        demo_data.getValue("Z9999", "area")
    with pytest.raises(ValidationError):
        demo_data.getValue("Z0001", "not_a_property")


def test_set_value_validates_and_marks_repository_dirty(demo_data):
    demo_data.is_dirty = False
    demo_data.setValue("M0001", "specific_heat_capacity", 1200)
    assert demo_data.getValue("M0001", "specific_heat_capacity") == 1200
    assert demo_data.is_dirty
    demo_data.setValue("W0001", "U_value", "UValue_Window_EPConstr_WindowGlazing_Lobby")
    assert demo_data.getValue("W0001", "U_value") == 1
    with pytest.raises(ValidationError):
        demo_data.setValue("M0001", "specific_heat_capacity", "not_known")
    assert demo_data.getValue("M0001", "specific_heat_capacity") == 1200
    with pytest.raises(ValidationError):
        demo_data.setValue("M0001", "identifier", "M9999")


def test_demo_semantic_round_trip(tmp_path, demo_data):
    demo_data.write_directory(tmp_path)
    reloaded = ThermalModelData.from_directory(tmp_path)
    assert [item.identifier for item in reloaded.zones] == [item.identifier for item in demo_data.zones]
    assert [item.identifier for item in reloaded.building_elements] == [item.identifier for item in demo_data.building_elements]
    assert reloaded.to_tables().keys() == demo_data.to_tables().keys()
    assert reloaded.getValue("W0001", "U_value") == demo_data.getValue("W0001", "U_value")
    assert reloaded.getValue("C0001", "material_identifiers") == demo_data.getValue("C0001", "material_identifiers")
    assert float(reloaded.building_elements[0].area) == pytest.approx(float(demo_data.building_elements[0].area))


def _copy_demo(tmp_path):
    target = tmp_path / "ThermalModel"
    shutil.copytree(DEMO, target)
    for excel in target.glob("*.xls*"):
        excel.unlink()
    return target


def test_duplicate_identifier_failure(tmp_path):
    target = _copy_demo(tmp_path)
    zones = target / "zones.csv"
    text = zones.read_text(encoding="utf-8")
    zones.write_text(text + text.splitlines()[1] + "\n", encoding="utf-8")
    with pytest.raises(ValidationError, match="already in use"):
        ThermalModelData.from_directory(target)


def test_missing_reference_failure(tmp_path):
    target = _copy_demo(tmp_path)
    constructions = target / "constructions.csv"
    text = constructions.read_text(encoding="utf-8").replace("M0002,M0014", "M9999,M0014", 1)
    constructions.write_text(text, encoding="utf-8")
    with pytest.raises(ValidationError, match="missing materials"):
        ThermalModelData.from_directory(target)


def test_malformed_value_failure(tmp_path):
    target = _copy_demo(tmp_path)
    zones = target / "zones.csv"
    text = zones.read_text(encoding="utf-8").replace("17.78832618;53.36497853", "not-a-number;53.36497853", 1)
    zones.write_text(text, encoding="utf-8")
    with pytest.raises(ValidationError):
        ThermalModelData.from_directory(target)


def test_invalid_expression_and_cycle_failures(demo_data):
    with pytest.raises(ExpressionError):
        demo_data.evalStr("abs(UValue_IRTransparent)")
    demo_data.parameters[0].value = "other + 1"
    demo_data.parameters[1].identifier = "other"
    demo_data.parameters[1].value = "UValue_IRTransparent + 1"
    with pytest.raises(ExpressionError, match="Cyclic"):
        demo_data.evalStr("UValue_IRTransparent")


def test_missing_required_table_failure(tmp_path):
    target = _copy_demo(tmp_path)
    (target / "windows.csv").unlink()
    with pytest.raises(Exception, match="Missing required table"):
        ThermalModelData.from_directory(target)
