from pathlib import Path
import re


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
    assert "this_file = mfilename('fullpath')" in source
    assert "parity_dir = fileparts(this_file)" in source
    assert "origin_matlab_dir = fileparts(parity_dir)" in source
    assert "toolbox_directory = fullfile(origin_matlab_dir, 'toolbox')" in source
    assert "repository_root = fileparts(origin_matlab_dir)" in source
    assert "assert(isfolder(toolbox_directory)" in source
    assert "applyModernMatlabCompatibility(toolbox_directory)" in source
    assert "which('Building', '-all')" in source
    assert "expected_building" in source
    assert "export_brcm_reference:AmbiguousBuilding" in source
    assert "clear classes" not in source
    assert "clear all" not in source
    assert "pwd" not in source
    assert "cd(" not in source


def test_original_toolbox_has_no_active_legacy_property_declarations():
    classes = ROOT / "origin_matlab" / "toolbox" / "Classes"
    legacy = re.compile(r"^\s*[A-Za-z]\w*\s*@[A-Za-z]\w*(?:\.[A-Za-z]\w*)*")
    occurrences = []
    for matlab_file in classes.rglob("*.m"):
        for line_number, line in enumerate(matlab_file.read_text(encoding="utf-8").splitlines(), 1):
            if legacy.match(line):
                occurrences.append(f"{matlab_file.relative_to(ROOT)}:{line_number}: {line.strip()}")
    assert occurrences == []


def test_exporter_never_saves_brcm_objects():
    source = EXPORTER.read_text(encoding="utf-8")
    save_lines = [line.strip() for line in source.splitlines() if line.lstrip().startswith("save(")]
    assert save_lines
    forbidden_names = ("'B'", "'SimExp'", "'ehf'", "'identifiers'")
    for line in save_lines:
        assert not any(name in line for name in forbidden_names)
