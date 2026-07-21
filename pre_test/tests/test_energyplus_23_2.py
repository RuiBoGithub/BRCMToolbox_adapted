from __future__ import annotations

from collections import Counter
from pathlib import Path

import numpy as np
import pytest

from brcm import ThermalModelData, generate_thermal_model
from brcm.energyplus import LegacyIDDParser, convert_idf_to_brcm_data
from brcm.exceptions import DataFormatError


ROOT = Path(__file__).resolve().parents[2]
IDF_23_2 = ROOT / "_E+" / "5Zone_Transformer.idf"
IDF_1ZONE_23_2 = ROOT / "_E+" / "1ZoneUncontrolled1.idf"
IDD_23_2 = ROOT / "_E+" / "idd" / "23.2" / "Energy+.idd"


def _assert_complete_pipeline(result):
    normalized = result.normalized_model
    assert normalized.version == "23.2"
    assert (len(normalized.zones), len(normalized.surfaces), len(normalized.windows)) == (6, 40, 6)
    assert len(normalized.materials) == 16
    assert len(normalized.constructions) == 7
    assert {name: len(rows) - 1 for name, rows in result.tables.items()} == {
        "zones": 6,
        "buildingelements": 27,
        "constructions": 6,
        "materials": 16,
        "windows": 6,
        "parameters": 10,
        "nomassconstructions": 0,
    }
    data = ThermalModelData.from_tables(result.tables)
    model = generate_thermal_model(data)
    assert model.A.shape == model.Bq.shape == model.Xcap.shape == (63, 63)
    assert np.isfinite(model.A).all()
    assert np.isfinite(model.Bq).all()
    assert np.isfinite(model.Xcap).all()


def test_explicit_23_2_idd_runs_complete_conversion_pipeline():
    result = convert_idf_to_brcm_data(IDF_23_2, idd_path=IDD_23_2)
    _assert_complete_pipeline(result)


def test_23_2_idd_is_resolved_automatically():
    _assert_complete_pipeline(convert_idf_to_brcm_data(IDF_23_2))


def test_modern_shifted_surface_fields_are_resolved_by_name():
    objects = LegacyIDDParser(idd_path=IDD_23_2).parse(IDF_23_2)
    opaque = next(item for item in objects if item.type == "BuildingSurface:Detailed")
    window = next(item for item in objects if item.type == "FenestrationSurface:Detailed")
    assert opaque.field_names[4:7] == (
        "Space Name", "Outside Boundary Condition", "Outside Boundary Condition Object"
    )
    assert window.field_names[6:9] == (
        "Frame and Divider Name", "Multiplier", "Number of Vertices"
    )
    result = convert_idf_to_brcm_data(IDF_23_2, idd_path=IDD_23_2)
    assert all(surface.zone for surface in result.normalized_model.surfaces)
    assert all(window.parent_surface for window in result.normalized_model.windows)


def test_23_2_object_inventory_and_nonstructural_ignores():
    result = convert_idf_to_brcm_data(IDF_23_2, idd_path=IDD_23_2)
    counts = Counter(item.type for item in result.normalized_model.raw_objects)
    assert counts["BuildingSurface:Detailed"] == 40
    assert counts["FenestrationSurface:Detailed"] == 6
    assert counts["AirLoopHVAC"] == 1
    assert counts["ElectricLoadCenter:Transformer"] == 1
    assert "ZoneHVAC:EquipmentList" in result.normalized_model.ignored_object_types
    assert "WindowMaterial:Glazing" in result.normalized_model.ignored_object_types


def test_23_2_window_data_file_and_nomass_envelope_reach_rc_generation():
    result = convert_idf_to_brcm_data(IDF_1ZONE_23_2, idd_path=IDD_23_2)
    assert any(item.type == "Construction:WindowDataFile" for item in result.normalized_model.raw_objects)
    assert {name: len(rows) - 1 for name, rows in result.tables.items()} == {
        "zones": 1,
        "buildingelements": 6,
        "constructions": 3,
        "materials": 3,
        "windows": 1,
        "parameters": 7,
        "nomassconstructions": 0,
    }
    model = generate_thermal_model(ThermalModelData.from_tables(result.tables))
    assert model.A.shape == model.Bq.shape == model.Xcap.shape == (2, 2)
    assert len(model.boundary_conditions["ambient"]) == 5
    assert not model.boundary_conditions["user_defined"]
    assert all(np.isfinite(matrix).all() for matrix in (model.A, model.Bq, model.Xcap))


def test_missing_explicit_idd_fails_clearly():
    with pytest.raises(DataFormatError, match="IDD does not exist"):
        convert_idf_to_brcm_data(IDF_23_2, idd_path=ROOT / "_E+/idd/missing/Energy+.idd")


def test_mismatched_explicit_idd_fails_clearly():
    legacy_idd = ROOT / "origin_matlab/toolbox/EP2BRCM/IDDFiles/V8-1-0-Energy+.idd"
    with pytest.raises(DataFormatError, match="does not match IDD version"):
        convert_idf_to_brcm_data(IDF_23_2, idd_path=legacy_idd)


def test_legacy_8_1_pipeline_remains_available():
    legacy = ROOT / "pre_test/tests/fixtures/energyplus/minimal.idf"
    result = convert_idf_to_brcm_data(legacy)
    assert result.normalized_model.version == "8.1"
    assert len(result.tables["zones"]) == 2
    assert generate_thermal_model(ThermalModelData.from_tables(result.tables)).A.shape == (2, 2)
