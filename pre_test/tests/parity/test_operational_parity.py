from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from brcm.energyplus import convert_idf_to_brcm_data


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
PRE_TEST = REPOSITORY_ROOT / "pre_test"
PARITY_TOOLS = PRE_TEST / "tools" / "parity"
sys.path.insert(0, str(PARITY_TOOLS))

from cases import resolve_case  # noqa: E402


PARITY_CASES = [
    "_simp",
    "two_zone_interzone",
]
MATLAB_EXPORTER = REPOSITORY_ROOT / "origin_matlab" / "parity" / "export_case_reference.m"
PYTHON_RUNNER = PARITY_TOOLS / "run_python_reference.py"
COMPARATOR = PARITY_TOOLS / "compare_parity.py"


@pytest.mark.parametrize("case_name", PARITY_CASES)
def test_case_resolution_and_python_reference(case_name):
    case = resolve_case(case_name)
    assert case.idf == (PRE_TEST / "tests/fixtures/energyplus" / f"{case_name}.idf").resolve()
    assert case.output == (PRE_TEST / "outputs/parity" / case_name).resolve()
    subprocess.run(
        [sys.executable, str(PYTHON_RUNNER), "--case", case_name],
        cwd=REPOSITORY_ROOT, check=True,
    )
    manifest = json.loads((case.output / "python/manifest.json").read_text(encoding="utf-8"))
    assert manifest["case_name"] == case_name
    assert manifest["source_idf"] == f"{case_name}.idf"
    assert manifest["source_idf_sha256"] == hashlib.sha256(case.idf.read_bytes()).hexdigest()
    assert manifest["energyplus_version"]
    assert manifest["implementation"] == "Python"


def test_generic_workflow_contains_no_case_specific_execution_logic():
    matlab = MATLAB_EXPORTER.read_text(encoding="utf-8")
    python = PYTHON_RUNNER.read_text(encoding="utf-8")
    compare = COMPARATOR.read_text(encoding="utf-8")
    for source in (matlab, python, compare):
        assert "case_name" in source
        assert "_simp" not in source
    assert "resolve_case" in python and "resolve_case" in compare
    assert "pre_test" in matlab


def test_empty_optional_tables_keep_exact_headers():
    case = resolve_case("_simp")
    conversion = convert_idf_to_brcm_data(case.idf)
    assert len(conversion.normalized_model.windows) == 0
    assert len(conversion.normalized_model.internal_masses) == 0
    assert conversion.tables["windows"] == [[
        "identifier", "description", "glass_area", "frame_area", "U_value", "SHGC"
    ]]
    assert conversion.tables["nomassconstructions"] == [["identifier", "description", "U_value"]]


@pytest.mark.parametrize("case_name", PARITY_CASES)
def test_operational_parity_when_current_matlab_reference_exists(case_name):
    case = resolve_case(case_name)
    manifest_path = case.output / "matlab/manifest.json"
    if not manifest_path.is_file():
        pytest.skip(f"MATLAB reference not generated for {case_name}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    source_hash = hashlib.sha256(case.idf.read_bytes()).hexdigest()
    if (manifest.get("case_name") != case_name or
            manifest.get("source_idf_sha256") != source_hash):
        pytest.skip(f"MATLAB reference is stale for {case_name}")
    subprocess.run([sys.executable, str(PYTHON_RUNNER), "--case", case_name],
                   cwd=REPOSITORY_ROOT, check=True)
    comparison = subprocess.run(
        [sys.executable, str(COMPARATOR), "--case", case_name],
        cwd=REPOSITORY_ROOT, check=False,
    )
    report = json.loads((case.output / "parity_report.json").read_text(encoding="utf-8"))
    assert comparison.returncode == 0, report["first_mismatch"]
    assert report["same_input_file"]
    assert all(report["tables"][name]["pass"] for name in report["tables"])
    assert report["identifiers"]["pass"] and report["boundaries"]["pass"]
    assert all(report["matrices"][name]["pass"] for name in ("A", "Bq", "Xcap"))
    assert report["simulation"]["pass"] and report["overall_pass"]
