from pathlib import Path


ROOT = Path(__file__).parents[2]
EXPORTER = ROOT / "origin_matlab" / "parity" / "export_brcm_reference.m"


def test_exporter_exists_and_uses_public_reference_workflow():
    source = EXPORTER.read_text(encoding="utf-8")
    required_calls = (
        "B.loadThermalModelData",
        "B.declareEHFModel",
        "B.generateBuildingModel",
        "B.building_model.discretize",
        "getConstraintsMatrices",
        "getCostVector",
        "simulateBuildingModel('inputTrajectory'",
    )
    for call in required_calls:
        assert call in source


def test_exporter_applies_modern_matlab_compatibility_and_checks_class_scope():
    source = EXPORTER.read_text(encoding="utf-8")
    assert "applyModernMatlabCompatibility(toolbox_directory)" in source
    assert "which('Building', '-all')" in source
    assert "expected_building" in source
    assert "export_brcm_reference:AmbiguousBuilding" in source


def test_exporter_never_saves_brcm_objects():
    source = EXPORTER.read_text(encoding="utf-8")
    save_lines = [line.strip() for line in source.splitlines() if line.lstrip().startswith("save(")]
    assert save_lines
    forbidden_names = ("'B'", "'SimExp'", "'ehf'", "'identifiers'")
    for line in save_lines:
        assert not any(name in line for name in forbidden_names)
