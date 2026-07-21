#!/usr/bin/env python3
"""Compare independently generated MATLAB and Python parity-case artifacts."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import re

import numpy as np
from scipy.io import loadmat

from cases import resolve_case
TABLE_NAMES = ("zones", "buildingelements", "constructions", "materials", "windows", "parameters", "nomassconstructions")
RTOL = 1e-10
ATOL = 1e-12


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_table(path: Path) -> list[list[str]]:
    with path.open(newline="", encoding="utf-8-sig") as stream:
        rows = list(csv.reader(stream, delimiter=";", quoting=csv.QUOTE_NONE))
    return [row[:-1] if row and row[-1] == "" else row for row in rows]


def numeric(value: str) -> float | None:
    try:
        result = float(value)
    except ValueError:
        return None
    return result if math.isfinite(result) else None


def compare_cell(left: str, right: str, column: str) -> bool:
    if left == right or {left.casefold(), right.casefold()} <= {"", "nan"}:
        return True
    if column == "vertices":
        lv = np.asarray([float(x) for x in re.findall(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", left)])
        rv = np.asarray([float(x) for x in re.findall(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", right)])
        return lv.shape == rv.shape and bool(np.allclose(lv, rv, rtol=RTOL, atol=ATOL))
    ln, rn = numeric(left), numeric(right)
    return ln is not None and rn is not None and bool(np.isclose(ln, rn, rtol=RTOL, atol=ATOL))


def mismatch_detail(table: str, row: int, column: str, left: str, right: str) -> dict[str, object]:
    ln, rn = numeric(left), numeric(right)
    detail: dict[str, object] = {"row": row, "column": column,
                                "matlab_value": left, "python_value": right}
    if ln is not None and rn is not None:
        difference = abs(ln - rn)
        detail.update({"absolute_difference": difference,
                       "relative_difference": difference / max(abs(ln), abs(rn), ATOL),
                       "classification": "conversion logic"})
    else:
        detail.update({"absolute_difference": None, "relative_difference": None,
                       "classification": "text/identifier"})
    detail["source_idf_field"] = None
    return detail


def matrix_metrics(matlab: np.ndarray, python: np.ndarray) -> dict[str, object]:
    same_shape = matlab.shape == python.shape
    if not same_shape:
        return {"pass": False, "shape_equal": False, "matlab_shape": list(matlab.shape), "python_shape": list(python.shape),
                "max_absolute_error": None, "max_relative_error": None, "mismatching_entries": None,
                "nonzero_pattern_mismatches": None}
    difference = np.abs(matlab - python)
    scale = np.maximum(np.maximum(np.abs(matlab), np.abs(python)), ATOL)
    mismatch = ~np.isclose(matlab, python, rtol=RTOL, atol=ATOL)
    nz_mismatch = np.not_equal(matlab != 0, python != 0)
    return {"pass": not bool(np.any(mismatch)), "shape_equal": True, "matlab_shape": list(matlab.shape),
            "python_shape": list(python.shape), "max_absolute_error": float(difference.max(initial=0)),
            "max_relative_error": float((difference / scale).max(initial=0)),
            "mismatching_entries": int(mismatch.sum()), "nonzero_pattern_mismatches": int(nz_mismatch.sum())}


def first_failure(report: dict) -> str | None:
    if report["matlab_sha256"] == "NOT EXECUTED":
        return "MATLAB reference was not executed"
    if report["python_sha256"] == "NOT EXECUTED":
        return "Python reference was not executed"
    if not report["same_case_name"]:
        return "Case names differ"
    if not report["same_idf_filename"]:
        return "Source IDF filenames differ"
    if not report["same_input_file"]:
        return "Source IDF SHA-256 differs"
    for name, result in report["tables"].items():
        if not result["pass"]:
            return f"Table {name}: {result['first_mismatch']}"
    if not report["identifiers"]["pass"]:
        return report["identifiers"]["first_mismatch"]
    if not report["boundaries"]["pass"]:
        return report["boundaries"]["first_mismatch"]
    for name in ("A", "Bq", "Xcap"):
        if not report["matrices"][name]["pass"]:
            return f"Matrix {name} differs"
    if not report["simulation"]["pass"]:
        return report["simulation"]["first_mismatch"]
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True, dest="case_name")
    args = parser.parse_args()
    case = resolve_case(args.case_name)
    root = case.output
    matlab_dir, python_dir = root / "matlab", root / "python"
    matlab_manifest_path, python_manifest_path = matlab_dir / "manifest.json", python_dir / "manifest.json"
    matlab_manifest = read_json(matlab_manifest_path) if matlab_manifest_path.is_file() else None
    python_manifest = read_json(python_manifest_path) if python_manifest_path.is_file() else None
    matlab_hash = matlab_manifest.get("source_idf_sha256", "NOT EXECUTED") if matlab_manifest else "NOT EXECUTED"
    python_hash = python_manifest.get("source_idf_sha256", "NOT EXECUTED") if python_manifest else "NOT EXECUTED"
    expected_source = case.idf
    expected_hash = sha256_file(expected_source)
    same_case_name = bool(matlab_manifest and python_manifest and
                          matlab_manifest.get("case_name") == python_manifest.get("case_name") == case.name)
    same_idf_filename = bool(matlab_manifest and python_manifest and
                             matlab_manifest.get("source_idf") == python_manifest.get("source_idf") == expected_source.name)
    same_input = bool(same_case_name and same_idf_filename and
                      matlab_hash == python_hash == expected_hash)
    report: dict[str, object] = {"case_name": case.name, "source_idf": expected_source.name,
                                "matlab_sha256": matlab_hash,
                                "python_sha256": python_hash, "same_input_file": same_input,
                                "same_case_name": same_case_name,
                                "same_idf_filename": same_idf_filename,
                                "energyplus_version": {
                                    "matlab": matlab_manifest.get("energyplus_version") if matlab_manifest else None,
                                    "python": python_manifest.get("energyplus_version") if python_manifest else None,
                                },
                                "implementation": {
                                    "matlab": matlab_manifest.get("implementation") if matlab_manifest else None,
                                    "python": python_manifest.get("implementation") if python_manifest else None,
                                },
                                "tolerances": {"rtol": RTOL, "atol": ATOL}, "tables": {},
                                "identifiers": {"pass": False, "first_mismatch": "MATLAB output missing"},
                                "boundaries": {"pass": False, "first_mismatch": "MATLAB output missing"},
                                "matrices": {}, "simulation": {"pass": False, "first_mismatch": "MATLAB output missing"}}

    if matlab_manifest and python_manifest and same_input:
        for name in TABLE_NAMES:
            left, right = read_table(matlab_dir / "tables" / f"{name}.csv"), read_table(python_dir / "tables" / f"{name}.csv")
            result = {"pass": True, "row_order_equal": len(left) == len(right), "column_order_equal": bool(left and right and left[0] == right[0]),
                      "matlab_rows": len(left), "python_rows": len(right), "first_mismatch": None,
                      "numeric_mismatches": []}
            if len(left) != len(right) or not left or not right or left[0] != right[0]:
                result["pass"] = False; result["first_mismatch"] = "row count or header/order differs"
            else:
                for row_index, (lrow, rrow) in enumerate(zip(left, right)):
                    if len(lrow) != len(rrow):
                        result["pass"] = False; result["first_mismatch"] = f"row {row_index + 1} width differs"; break
                    for column_index, (lv, rv) in enumerate(zip(lrow, rrow)):
                        column = left[0][column_index]
                        if row_index and not compare_cell(lv, rv, column):
                            result["pass"] = False
                            result["first_mismatch"] = f"row {row_index + 1}, column {column!r}: MATLAB={lv!r}, Python={rv!r}"
                            result["numeric_mismatches"].append(
                                mismatch_detail(name, row_index + 1, column, lv, rv))
                            break
                    if not result["pass"]: break
            report["tables"][name] = result

        matlab_ids, python_ids = read_json(matlab_dir / "identifiers.json"), read_json(python_dir / "identifiers.json")
        id_pass = matlab_ids == python_ids
        report["identifiers"] = {"pass": id_pass, "state_exact": matlab_ids.get("state") == python_ids.get("state"),
                                 "heat_flux_exact": matlab_ids.get("heat_flux") == python_ids.get("heat_flux"),
                                 "first_mismatch": None if id_pass else "State or heat-flux identifier ordering differs"}
        matlab_boundaries, python_boundaries = read_json(matlab_dir / "boundaries.json"), read_json(python_dir / "boundaries.json")
        boundary_pass = True; boundary_first = None
        if list(matlab_boundaries) != list(python_boundaries):
            boundary_pass = False; boundary_first = "Boundary classifications/order differ"
        else:
            for kind in matlab_boundaries:
                left, right = matlab_boundaries[kind], python_boundaries[kind]
                if len(left) != len(right): boundary_pass = False; boundary_first = f"Boundary {kind} record count differs"; break
                for index, (lv, rv) in enumerate(zip(left, right)):
                    if lv["identifier_1"] != rv["identifier_1"] or lv["identifier_2"] != rv["identifier_2"] or not np.isclose(lv["value"], rv["value"], rtol=RTOL, atol=ATOL):
                        boundary_pass = False; boundary_first = f"Boundary {kind} record {index + 1} differs"; break
                if not boundary_pass: break
        report["boundaries"] = {"pass": boundary_pass, "first_mismatch": boundary_first,
                                "matlab": matlab_boundaries, "python": python_boundaries}

        matlab_arrays = loadmat(matlab_dir / "reference.mat", squeeze_me=False)
        python_arrays = np.load(python_dir / "reference.npz")
        for name in ("A", "Bq", "Xcap"):
            report["matrices"][name] = matrix_metrics(np.asarray(matlab_arrays[name], float), np.asarray(python_arrays[name], float))
        x_metrics = matrix_metrics(np.asarray(matlab_arrays["X"], float), np.asarray(python_arrays["X"], float))
        t_metrics = matrix_metrics(np.asarray(matlab_arrays["t_hrs"], float), np.asarray(python_arrays["t_hrs"], float))
        q_metrics = matrix_metrics(np.asarray(matlab_arrays["Q"], float), np.asarray(python_arrays["Q"], float))
        x0_metrics = matrix_metrics(np.asarray(matlab_arrays["x0"], float), np.asarray(python_arrays["x0"], float))
        config_equal = (float(np.asarray(matlab_arrays["Ts"]).squeeze()) == float(np.asarray(python_arrays["Ts"]).squeeze()) and
                        int(np.asarray(matlab_arrays["N"]).squeeze()) == int(np.asarray(python_arrays["N"]).squeeze()))
        x_left, x_right = np.asarray(matlab_arrays["X"], float), np.asarray(python_arrays["X"], float)
        if x_left.shape == x_right.shape:
            per_state_rmse = np.sqrt(np.mean((x_left - x_right) ** 2, axis=1)).tolist()
            final_state_error = np.abs(x_left[:, -1] - x_right[:, -1]).tolist()
        else:
            per_state_rmse = final_state_error = None
        sim_pass = bool(x_metrics["pass"] and t_metrics["pass"] and q_metrics["pass"] and
                        x0_metrics["pass"] and config_equal)
        report["simulation"] = {"pass": sim_pass, "X": x_metrics, "time": t_metrics,
                                "Q": q_metrics, "x0": x0_metrics, "configuration_equal": config_equal,
                                "per_state_rmse": per_state_rmse, "maximum_absolute_trajectory_error": x_metrics["max_absolute_error"],
                                "final_state_error": final_state_error,
                                "first_mismatch": None if sim_pass else "MATLAB-compatible X or time vector differs"}

    report["overall_pass"] = bool(same_input and report["tables"] and all(v["pass"] for v in report["tables"].values()) and
                                  report["identifiers"]["pass"] and report["boundaries"]["pass"] and
                                  all(report["matrices"].get(name, {}).get("pass", False) for name in ("A", "Bq", "Xcap")) and
                                  report["simulation"]["pass"])
    report["first_mismatch"] = first_failure(report)
    root.mkdir(parents=True, exist_ok=True)
    (root / "parity_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    status = lambda value: "PASS" if value else "FAIL"
    lines = [f"Case: {case.name}", f"Source IDF: {expected_source.name}",
             f"MATLAB SHA256: {matlab_hash}", f"Python SHA256: {python_hash}",
             f"Same case name: {status(same_case_name)}",
             f"Same IDF filename: {status(same_idf_filename)}",
             f"Same input file: {status(same_input)}", "", f"# `{case.name}` Operational Parity", "",
             f"1. Seven-table parity: {status(bool(report['tables']) and all(v['pass'] for v in report['tables'].values()))}"]
    for table_name in TABLE_NAMES:
        table = report["tables"].get(table_name)
        lines.append(f"   - {table_name}: {status(bool(table and table['pass']))}" +
                     (f" — {table['first_mismatch']}" if table and table["first_mismatch"] else ""))
    lines += [
             f"2. Identifier parity: {status(report['identifiers']['pass'])}", f"3. Boundary parity: {status(report['boundaries']['pass'])}"]
    for number, name in enumerate(("A", "Bq", "Xcap"), 4):
        metric = report["matrices"].get(name)
        lines.append(f"{number}. {name} parity: {status(bool(metric and metric['pass']))}")
        if metric:
            lines.append(f"   - Shape equality: {status(metric['shape_equal'])}; max abs: {metric['max_absolute_error']}; max rel: {metric['max_relative_error']}; mismatches: {metric['mismatching_entries']}; nonzero-pattern mismatches: {metric['nonzero_pattern_mismatches']}")
    lines += [f"7. Simulation parity: {status(report['simulation']['pass'])}"]
    simulation = report["simulation"]
    if "X" in simulation:
        max_rmse = max(simulation["per_state_rmse"], default=0.0) if simulation["per_state_rmse"] is not None else None
        max_final = max(simulation["final_state_error"], default=0.0) if simulation["final_state_error"] is not None else None
        lines += [f"   - Maximum absolute trajectory error: {simulation['maximum_absolute_trajectory_error']}",
                  f"   - Maximum per-state RMSE: {max_rmse}", f"   - Maximum final-state error: {max_final}",
                  f"   - Time vector: {status(simulation['time']['pass'])}",
                  f"   - Deterministic x0/Q/Ts/N: {status(simulation['Q']['pass'] and simulation['x0']['pass'] and simulation['configuration_equal'])}"]
    lines += [f"8. Overall {status(report['overall_pass'])}", "",
              f"First mismatch: {report['first_mismatch'] or 'None'}"]
    (root / "parity_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Overall {status(report['overall_pass'])}")
    print(f"First mismatch: {report['first_mismatch'] or 'None'}")
    return 0 if report["overall_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
