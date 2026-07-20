"""Load portable reference fixtures exported by MATLAB.

This module contains no BRCM model or physics implementation.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

import numpy as np
from scipy.io import loadmat, whosmat


_NUMERIC_MATLAB_CLASSES = {
    "double",
    "single",
    "logical",
    "int8",
    "uint8",
    "int16",
    "uint16",
    "int32",
    "uint32",
    "int64",
    "uint64",
}


@dataclass(frozen=True)
class ReferenceFixture:
    """Plain data loaded from one MATLAB reference-fixture directory."""

    root: Path
    manifest: dict[str, Any]
    thermal_model_data: dict[str, Any]
    matrices: dict[str, np.ndarray]


def _logical_shape(entry: dict[str, Any]) -> tuple[int, ...]:
    return tuple(int(value) for value in entry["shape"])


def _load_numeric_mat_file(path: Path) -> dict[str, np.ndarray]:
    """Load a MAT file after rejecting opaque MATLAB values."""

    unsupported = [
        (name, matlab_class)
        for name, _shape, matlab_class in whosmat(path)
        if not name.startswith("__") and matlab_class not in _NUMERIC_MATLAB_CLASSES
    ]
    if unsupported:
        details = ", ".join(f"{name}:{kind}" for name, kind in unsupported)
        raise TypeError(f"{path.name} contains non-numeric MATLAB data: {details}")

    loaded = loadmat(path, struct_as_record=False, squeeze_me=False)
    result: dict[str, np.ndarray] = {}
    for name, value in loaded.items():
        if name.startswith("__"):
            continue
        array = np.asarray(value)
        if array.dtype.kind == "O":
            raise TypeError(f"{path.name}:{name} requires MATLAB object data")
        result[name] = array
    return result


def load_reference_fixture(directory: str | Path) -> ReferenceFixture:
    """Load and structurally normalize an exported MATLAB fixture set."""

    root = Path(directory).resolve()
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(
            f"MATLAB reference manifest not found: {manifest_path}. "
            "Run export_brcm_reference in MATLAB first."
        )

    with manifest_path.open(encoding="utf-8") as stream:
        manifest = json.load(stream)
    if manifest.get("format") != "brcm-matlab-reference":
        raise ValueError("Unrecognized MATLAB reference-fixture format")
    if manifest.get("format_version") != 1:
        raise ValueError("Unsupported MATLAB reference-fixture version")

    thermal_path = root / manifest["thermal_data_file"]
    with thermal_path.open(encoding="utf-8") as stream:
        thermal_model_data = json.load(stream)

    by_file: dict[str, dict[str, np.ndarray]] = {}
    matrices: dict[str, np.ndarray] = {}
    for entry in manifest["matrices"]:
        filename = entry["file"]
        if filename not in by_file:
            by_file[filename] = _load_numeric_mat_file(root / filename)
        variable = entry["variable"]
        try:
            array = by_file[filename][variable]
        except KeyError as error:
            raise KeyError(f"{filename} does not contain {variable}") from error

        expected_shape = _logical_shape(entry)
        expected_size = int(np.prod(expected_shape, dtype=np.int64))
        if array.size != expected_size:
            raise ValueError(
                f"{entry['key']} has {array.size} values, expected "
                f"{expected_size} for shape {expected_shape}"
            )
        # MATLAB may omit trailing singleton dimensions in MAT metadata.
        matrices[entry["key"]] = np.reshape(array, expected_shape, order="F")

    return ReferenceFixture(root, manifest, thermal_model_data, matrices)

