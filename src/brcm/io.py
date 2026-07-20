"""Mixed-cell table I/O compatible with BRCM CSV/XLS conventions."""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .constants import Constants, matlab_number
from .exceptions import DataFormatError
from .validation import check_file_extension


@dataclass(frozen=True)
class TableAnchor:
    """Python 0-based table anchor, with MATLAB indices available explicitly."""

    row: int
    column: int

    @property
    def matlab_row(self) -> int:
        return self.row + 1

    @property
    def matlab_column(self) -> int:
        return self.column + 1


def _numeric_or_string(value: str) -> float | str:
    if value == "":
        return Constants.NAN
    try:
        number = float(value)
    except ValueError:
        return value
    if math.isnan(number):
        return value
    return number


def read_cell_from_file(filename: str | Path) -> list[list[float | str]]:
    path = Path(filename)
    extension = check_file_extension(path)
    if extension == ".csv":
        rows: list[list[float | str]] = []
        with path.open(newline="", encoding="utf-8-sig") as stream:
            for row in csv.reader(stream, delimiter=";", quoting=csv.QUOTE_NONE):
                rows.append([_numeric_or_string(value) for value in row])
        width = max((len(row) for row in rows), default=0)
        return [row + [Constants.NAN] * (width - len(row)) for row in rows]

    try:
        import pandas as pd
    except ImportError as error:
        raise DataFormatError(
            "Excel input is optional; install brcm[excel] or provide the CSV file"
        ) from error
    try:
        frame = pd.read_excel(path, header=None, dtype=object)
    except Exception as error:
        raise DataFormatError(f"Unable to read Excel file {path}: {error}") from error
    result = []
    for row in frame.itertuples(index=False, name=None):
        result.append([
            Constants.NAN if pd.isna(value) else (float(value) if isinstance(value, (int, float)) else str(value))
            for value in row
        ])
    return result


def _cell_to_string(value: Any) -> str:
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return matlab_number(value)
    return str(value)


def get_data_tables_from_file(
    filename: str | Path,
    headers: list[str] | tuple[str, ...] | list[list[str] | tuple[str, ...]],
    replace_nans: bool = True,
) -> tuple[list[list[list[str]]], list[TableAnchor]]:
    """Find anchored tables and crop all-NaN rows/columns like MATLAB."""

    if not headers or isinstance(headers[0], str):  # type: ignore[index]
        requested = [tuple(headers)]  # type: ignore[arg-type]
    else:
        requested = [tuple(header) for header in headers]  # type: ignore[assignment]
    full = [[_cell_to_string(value) for value in row] for row in read_cell_from_file(filename)]

    anchors: list[TableAnchor] = []
    for header in requested:
        matches = [
            TableAnchor(row_index, column_index)
            for row_index, row in enumerate(full)
            for column_index, value in enumerate(row)
            if value == header[0]
        ]
        if len(matches) != 1:
            raise DataFormatError(f"Expected one anchor {header[0]!r} in {filename}, found {len(matches)}")
        anchor = matches[0]
        actual = tuple(full[anchor.row][anchor.column : anchor.column + len(header)])
        if actual != header:
            raise DataFormatError(f"Header mismatch in {filename}: {actual!r} != {header!r}")
        anchors.append(anchor)

    sorted_indices = sorted(range(len(anchors)), key=lambda index: anchors[index].row)
    tables_by_index: dict[int, list[list[str]]] = {}
    for position, original_index in enumerate(sorted_indices):
        anchor = anchors[original_index]
        header = requested[original_index]
        end_row = anchors[sorted_indices[position + 1]].row if position + 1 < len(sorted_indices) else len(full)
        table = [row[anchor.column : anchor.column + len(header)] for row in full[anchor.row:end_row]]
        table = [row for row in table if not all(value.lower() == "nan" for value in row)]
        if table:
            keep_columns = [
                column for column in range(len(table[0]))
                if not all(row[column].lower() == "nan" for row in table)
            ]
            table = [[row[column] for column in keep_columns] for row in table]
        if not table or tuple(table[0]) != header:
            raise DataFormatError(f"Invalid cropped table header in {filename}")
        if replace_nans:
            table = [[Constants.EMPTY if value.lower() == "nan" else value for value in row] for row in table]
        tables_by_index[original_index] = table
    return [tables_by_index[index] for index in range(len(requested))], anchors


def choose_table_file(directory: str | Path, basename: str) -> Path:
    """Match ``loadThermalModelData`` precedence: CSV, then XLS, then XLSX."""

    directory = Path(directory)
    casefolded = {path.name.casefold(): path for path in directory.iterdir() if path.is_file()}
    for extension in (".csv", ".xls", ".xlsx"):
        candidate = casefolded.get(f"{basename}{extension}".casefold())
        if candidate is not None:
            return candidate
    raise DataFormatError(f"Missing required table {basename!r} in {directory}")


def write_semicolon_table(filename: str | Path, rows: list[list[str]]) -> None:
    path = Path(filename)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        for row in rows:
            stream.write(";".join(str(value).replace(";", "") for value in row) + ";\n")


# MATLAB-compatible spellings
readCellFromFile = read_cell_from_file
getDataTablesFromFile = get_data_tables_from_file

