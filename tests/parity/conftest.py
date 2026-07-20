from pathlib import Path

import pytest

from brcm.parity import load_reference_fixture


FIXTURE_DIRECTORY = Path(__file__).parents[1] / "fixtures" / "matlab"


@pytest.fixture(scope="session")
def fixture_directory() -> Path:
    return FIXTURE_DIRECTORY


@pytest.fixture(scope="session")
def matlab_reference(fixture_directory):
    if not (fixture_directory / "manifest.json").is_file():
        partial = list(fixture_directory.glob("*.mat")) + list(fixture_directory.glob("*.json"))
        if partial:
            pytest.fail("Partial MATLAB fixture set found without manifest.json")
        pytest.skip("MATLAB fixtures not generated; run export_brcm_reference first")
    return load_reference_fixture(fixture_directory)
