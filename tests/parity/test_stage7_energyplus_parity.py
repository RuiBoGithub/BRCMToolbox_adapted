"""Optional MATLAB EP2BRCM parity fixture hook.

The fixture is intentionally external: it must be produced by MATLAB using the
original toolbox.  This test never treats Python-generated output as parity.
"""
from pathlib import Path
import json
import pytest

FIXTURE=Path(__file__).parents[1]/"fixtures"/"matlab"/"ep2brcm_manifest.json"

@pytest.mark.skipif(not FIXTURE.exists(),reason="MATLAB EP2BRCM fixtures not generated")
def test_matlab_ep2brcm_fixture_manifest_is_loadable():
    manifest=json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert manifest["tables"]
    assert manifest["thermal_model"]
