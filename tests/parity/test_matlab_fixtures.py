from __future__ import annotations

import json

import numpy as np
from scipy.io import loadmat, whosmat


NUMERIC_MATLAB_CLASSES = {
    "double", "single", "logical", "int8", "uint8", "int16", "uint16",
    "int32", "uint32", "int64", "uint64",
}


def _counts(reference):
    ids = reference.manifest["identifiers"]
    return {name: len(ids[name]) for name in ("x", "q", "u", "v", "y", "constraints")}


def test_every_exported_file_is_portable(matlab_reference):
    root = matlab_reference.root
    manifest = matlab_reference.manifest
    json_files = {"manifest.json", manifest["thermal_data_file"]}
    mat_files = {entry["file"] for entry in manifest["matrices"]}

    for filename in json_files:
        with (root / filename).open(encoding="utf-8") as stream:
            assert isinstance(json.load(stream), dict)

    for filename in mat_files:
        declarations = whosmat(root / filename)
        assert declarations
        assert all(kind in NUMERIC_MATLAB_CLASSES for _name, _shape, kind in declarations)
        values = loadmat(root / filename, struct_as_record=False, squeeze_me=False)
        assert all(np.asarray(value).dtype.kind != "O" for name, value in values.items() if not name.startswith("__"))


def test_manifest_shapes_and_axes_are_complete(matlab_reference):
    for entry in matlab_reference.manifest["matrices"]:
        shape = tuple(entry["shape"])
        axes = entry["axes"]
        assert len(shape) == len(axes)
        assert matlab_reference.matrices[entry["key"]].shape == shape


def test_thermal_model_dimensions(matlab_reference):
    n = _counts(matlab_reference)
    m = matlab_reference.matrices
    assert m["thermal.A"].shape == (n["x"], n["x"])
    assert m["thermal.Bq"].shape == (n["x"], n["q"])
    assert m["thermal.Xcap"].shape == (n["x"], n["x"])
    assert m["thermal.A_d"].shape == (n["x"], n["x"])
    assert m["thermal.Bq_d"].shape == (n["x"], n["q"])


def test_each_ehf_model_dimensions(matlab_reference):
    m = matlab_reference.matrices
    for model in matlab_reference.manifest["ehf_models"]:
        prefix = f"ehf.{model['identifier']}"
        ids = model["identifiers"]
        nx, nq, nu, nv = map(lambda name: len(ids[name]), ("x", "q", "u", "v"))
        assert m[f"{prefix}.Aq"].shape == (nq, nx)
        assert m[f"{prefix}.Bq_u"].shape == (nq, nu)
        assert m[f"{prefix}.Bq_v"].shape == (nq, nv)
        assert m[f"{prefix}.Bq_xu"].shape == (nq, nx, nu)
        assert m[f"{prefix}.Bq_vu"].shape == (nq, nv, nu)


def test_complete_model_dimensions(matlab_reference):
    n = _counts(matlab_reference)
    m = matlab_reference.matrices
    expected = {
        "A": (n["x"], n["x"]), "Bu": (n["x"], n["u"]),
        "Bv": (n["x"], n["v"]), "Bxu": (n["x"], n["x"], n["u"]),
        "Bvu": (n["x"], n["v"], n["u"]), "C": (n["y"], n["x"]),
        "Du": (n["y"], n["u"]), "Dv": (n["y"], n["v"]),
        "Dxu": (n["y"], n["x"], n["u"]),
        "Dvu": (n["y"], n["v"], n["u"]),
    }
    for time_domain in ("continuous", "discrete"):
        for name, shape in expected.items():
            assert m[f"{time_domain}.{name}"].shape == shape


def test_constraint_cost_and_simulation_dimensions(matlab_reference):
    n = _counts(matlab_reference)
    m = matlab_reference.matrices
    nt = matlab_reference.manifest["simulation_time_steps"]
    assert m["constraints.Fx"].shape == (n["constraints"], n["x"])
    assert m["constraints.Fu"].shape == (n["constraints"], n["u"])
    assert m["constraints.Fv"].shape == (n["constraints"], n["v"])
    assert m["constraints.g"].shape == (n["constraints"], 1)
    assert m["cost.cu"].shape == (n["u"], 1)
    assert m["simulation.x0"].shape == (n["x"], 1)
    assert m["simulation.X"].shape == (n["x"], nt)
    assert m["simulation.U"].shape == (n["u"], nt)
    assert m["simulation.V"].shape == (n["v"], nt)
    assert m["simulation.t_hrs"].shape == (1, nt)
    np.testing.assert_array_equal(m["simulation.U"], m["simulation.requested_U"])
    np.testing.assert_array_equal(m["simulation.V"], m["simulation.requested_V"])
    np.testing.assert_allclose(
        np.diff(m["simulation.t_hrs"], axis=1),
        matlab_reference.manifest["sampling_time_hours"],
    )
    assert matlab_reference.manifest["constraint_identifiers_returned"] == matlab_reference.manifest["identifiers"]["constraints"]
    assert m["parameters.constraint_values"].shape == (
        len(matlab_reference.manifest["constraint_parameter_names"]), 1
    )
    assert m["parameters.cost_values"].shape == (
        len(matlab_reference.manifest["cost_parameter_names"]), 1
    )


def test_loaded_thermal_data_is_plain_and_complete(matlab_reference):
    data = matlab_reference.thermal_model_data
    expected_groups = {
        "zones", "building_elements", "constructions", "nomass_constructions",
        "materials", "windows", "parameters",
    }
    assert set(data) == expected_groups
    assert all(isinstance(data[group], list) for group in expected_groups)
    assert all(data[group] for group in expected_groups)
