#!/usr/bin/env python3
"""Generate the Python side of the operational _simp.idf parity workflow."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from brcm import SimulationExperiment, ThermalModelData, generate_thermal_model  # noqa: E402
from brcm.constants import matlab_default_num2str  # noqa: E402
from brcm.energyplus import convert_idf_to_brcm_data  # noqa: E402


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def boundaries_to_plain(model) -> dict[str, list[dict[str, object]]]:
    return {
        name: [
            {"identifier_1": item.identifier_1, "identifier_2": item.identifier_2, "value": item.value}
            for item in records
        ]
        for name, records in model.boundary_conditions.items()
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--idf", type=Path, default=REPOSITORY_ROOT / "tests/fixtures/energyplus/_simp.idf")
    parser.add_argument("--output", type=Path, default=REPOSITORY_ROOT / "outputs/parity/simp/python")
    args = parser.parse_args()
    idf = args.idf.resolve()
    output = args.output.resolve()
    expected = (REPOSITORY_ROOT / "tests/fixtures/energyplus/_simp.idf").resolve()
    if idf != expected:
        raise SystemExit(f"Operational parity requires exactly {expected}, got {idf}")
    output.mkdir(parents=True, exist_ok=True)

    conversion = convert_idf_to_brcm_data(idf)
    data = ThermalModelData.from_tables(conversion.tables)
    model = generate_thermal_model(data)
    table_directory = output / "tables"
    table_directory.mkdir(parents=True, exist_ok=True)
    data.write_directory(table_directory)

    source_material = next(item for item in conversion.normalized_model.materials
                           if item.name == "C5 - 4 IN HW CONCRETE")
    floor_row = next(row for row in conversion.tables["constructions"]
                     if len(row) > 1 and row[1] == "FLOOR")
    loaded_floor = next(item for item in data.constructions if item.description == "FLOOR")
    thickness_trace = {
        "source_idf": {"object": "Material", "name": "C5 - 4 IN HW CONCRETE",
                       "field": "Thickness", "line": 223, "value": 0.1014984, "units": "m"},
        "parser_text": "0.1014984",
        "normalized_value": source_material.thickness,
        "generated_table_value": floor_row[3],
        "serialized_value": floor_row[3],
        "reloaded_value": float(loaded_floor.thickness[0]),
        "effective_model_value": float(loaded_floor.thickness[0]),
        "matlab_num2str_emulation": matlab_default_num2str(source_material.thickness),
        "classification": "workflow quantization",
    }
    (output / "thickness_trace.json").write_text(
        json.dumps(thickness_trace, indent=2) + "\n", encoding="utf-8")

    ts = 0.25
    steps = 16
    nx = len(model.state_identifiers)
    nq = len(model.heat_flux_identifiers)
    x0 = 20.0 + 0.01 * np.arange(1, nx + 1, dtype=float).reshape(-1, 1)
    q = np.empty((nq, steps), dtype=float)
    for k in range(steps):
        q[:, k] = 100.0 + 0.5 * np.arange(1, nq + 1, dtype=float) + 2.0 * k

    # Use the public MATLAB-compatible wrapper with a thermal-only BuildingModel shell.
    from brcm import BuildingModel

    building = BuildingModel(model, [])
    building.set_discretization_step(ts)
    experiment = SimulationExperiment(building)
    experiment.setNumberOfSimulationTimeSteps(steps)
    experiment.setInitialState(x0)
    x, q_returned, t_hrs = experiment.simulateThermalModel("inputTrajectory", q)
    if not np.array_equal(q, q_returned):
        raise RuntimeError("Python simulation did not return the requested deterministic Q trajectory")

    np.savez(output / "reference.npz", A=model.A, Bq=model.Bq, Xcap=model.Xcap,
             X=x, X_full=experiment.X_full, Q=q, t_hrs=t_hrs, x0=x0, Ts=ts, N=steps)
    (output / "identifiers.json").write_text(json.dumps({
        "state": model.state_identifiers, "heat_flux": model.heat_flux_identifiers,
    }, indent=2) + "\n", encoding="utf-8")
    (output / "boundaries.json").write_text(json.dumps(boundaries_to_plain(model), indent=2) + "\n", encoding="utf-8")
    manifest = {
        "format": "brcm-simp-python-reference", "format_version": 1,
        "source_idf": "_simp.idf", "source_idf_path": str(idf),
        "source_idf_sha256": sha256_file(idf), "tables_directory": "tables",
        "matrix_file": "reference.npz", "sampling_time_hours": ts,
        "number_of_steps": steps, "thickness_trace": "thickness_trace.json",
        "python_executed": True,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Exported _simp.idf Python reference to {output}")
    print(f"SHA256: {manifest['source_idf_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
