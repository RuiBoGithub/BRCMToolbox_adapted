import json
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).parents[2]
SOURCE = ROOT / "tests" / "fixtures" / "energyplus" / "_simp.idf"
MATLAB_EXPORTER = ROOT / "origin_matlab" / "parity" / "export_simp_reference.m"
PYTHON_RUNNER = ROOT / "tools" / "parity" / "run_simp_python_reference.py"
COMPARATOR = ROOT / "tools" / "parity" / "compare_simp_parity.py"
REPORT = ROOT / "outputs" / "parity" / "simp" / "parity_report.json"
MATLAB_MANIFEST = ROOT / "outputs" / "parity" / "simp" / "matlab" / "manifest.json"


def test_simp_workflow_is_pinned_to_one_source_idf():
    assert SOURCE.is_file()
    matlab = MATLAB_EXPORTER.read_text(encoding="utf-8")
    python = PYTHON_RUNNER.read_text(encoding="utf-8")
    compare = COMPARATOR.read_text(encoding="utf-8")
    assert "tests', 'fixtures', 'energyplus', '_simp.idf'" in matlab
    assert 'tests/fixtures/energyplus/_simp.idf' in python
    assert "sha256_file(idf_file)" in matlab
    assert "sha256_file(idf)" in python
    assert 'same_input_file' in compare
    assert "DemoBuilding" not in matlab


def test_simp_operational_parity_when_matlab_was_executed():
    if not MATLAB_MANIFEST.is_file():
        pytest.skip("MATLAB _simp.idf reference not generated")
    subprocess.run([sys.executable, str(PYTHON_RUNNER)], cwd=ROOT, check=True)
    comparison = subprocess.run([sys.executable, str(COMPARATOR)], cwd=ROOT, check=False)
    assert REPORT.is_file()
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    assert comparison.returncode == 0, report["first_mismatch"]
    assert report["overall_pass"], report["first_mismatch"]
