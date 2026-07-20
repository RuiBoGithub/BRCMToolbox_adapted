"""Ports of ThermalModelData ``check_*`` functions."""

from __future__ import annotations

import math
import re
from collections.abc import Iterable, Sequence
from pathlib import Path

from .constants import Constants
from .exceptions import DataFormatError, ExpressionError, ValidationError
from .expressions import expression_names
from .geometry import parse_vertices


def check_file_extension(extension_or_path: str | Path) -> str:
    extension = Path(extension_or_path).suffix if Path(extension_or_path).suffix else str(extension_or_path)
    extension = extension.lower()
    if extension not in Constants.SUPPORTED_EXTENSIONS:
        raise ValidationError(f"Unsupported file extension {extension!r}")
    return extension


def check_identifier(identifier: str, key: str) -> str:
    if not isinstance(identifier, str) or re.fullmatch(re.escape(key) + r"\d{4}", identifier) is None:
        raise ValidationError(f"Invalid {key}dddd identifier: {identifier!r}")
    return identifier


def check_special_identifier(identifier: str) -> str:
    if not isinstance(identifier, str):
        raise ValidationError("Identifier must be a string")
    identifier = identifier.strip()
    if identifier == Constants.NAN or re.fullmatch(r"[A-Za-z](?:[A-Za-z0-9_]*[A-Za-z0-9])?", identifier) is None:
        raise ValidationError(f"Invalid special identifier: {identifier!r}")
    return identifier


def check_identifier_adjacent(identifier: str, key: str = "Z") -> str:
    if not isinstance(identifier, str):
        raise ValidationError("Adjacent identifier must be a string")
    if identifier == Constants.NAN:
        raise ValidationError("Adjacent identifier cannot be NaN")
    if identifier.strip().upper() == Constants.NULL:
        return Constants.NULL
    if identifier in Constants.EXTERIOR_IDENTIFIERS:
        return identifier
    return check_identifier(identifier, key)


def check_free_description(description: str) -> str:
    if description == Constants.NAN or not str(description).strip():
        return Constants.EMPTY
    if str(description).strip().upper() == Constants.NULL:
        return Constants.NULL
    return str(description)


def _as_finite_number(value: str) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def check_value(value: str | float | int, allow_parameter: bool) -> str:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        value = format(float(value), Constants.NUMERIC_FORMAT)
    if not isinstance(value, str):
        raise ValidationError("Value must be numeric or a string")
    stripped = value.strip()
    if stripped == Constants.NAN:
        return Constants.EMPTY
    if stripped == Constants.EMPTY and allow_parameter:
        return Constants.EMPTY
    if stripped.upper() == Constants.NULL:
        return Constants.NULL
    if _as_finite_number(stripped) is not None:
        return stripped
    if allow_parameter:
        try:
            expression_names(stripped)
        except ExpressionError as error:
            raise ValidationError(f"Invalid parameter expression {value!r}") from error
        return stripped
    raise ValidationError(f"Expected a numeric value, got {value!r}")


def check_group_identifiers(value: str, key: str, empty_entry: bool = False) -> list[str]:
    stripped = value.strip()
    if stripped.upper() == Constants.NULL:
        return [Constants.NULL]
    if empty_entry and stripped in (Constants.ZERO, Constants.NAN, Constants.EMPTY):
        return [Constants.ZERO if stripped == Constants.ZERO else Constants.EMPTY]
    if stripped == Constants.NAN:
        raise ValidationError("Identifier group cannot be NaN")
    return [check_identifier(item, key) for item in value.split(",")]


def check_special_group_identifiers(value: str, key: str, zero_entry: bool = False) -> list[str]:
    if value == Constants.NAN:
        raise ValidationError("Identifier group cannot be NaN")
    if zero_entry and value == Constants.ZERO:
        return [Constants.ZERO]
    result = []
    for item in value.split(","):
        try:
            result.append(check_identifier(item, key))
        except ValidationError:
            result.append(check_special_identifier(item))
    return result


def check_group_values(value: str) -> list[float] | list[str]:
    if value == Constants.NAN:
        raise ValidationError("Value group cannot be NaN")
    if value.strip().upper() == Constants.NULL:
        return [Constants.NULL]
    result = []
    for item in value.split(","):
        checked = check_value(item, False)
        result.append(float(checked))
    return result


def check_zone_group(value: str) -> list[str]:
    stripped = value.strip()
    if stripped in (Constants.NAN, Constants.EMPTY):
        return [Constants.EMPTY]
    if stripped.upper() == Constants.NULL:
        return [Constants.NULL]
    return [check_special_identifier(item) for item in value.split(",")]


def check_uniqueness_id(current: Iterable[str], new_identifier: str, type_name: str = "") -> None:
    if new_identifier in current:
        label = f"{type_name} " if type_name else ""
        raise ValidationError(f"{label}identifier {new_identifier!r} is already in use")


def check_xls_file_header(actual: Sequence[str], expected: Sequence[str], filename: str = "") -> None:
    # MATLAB uses setdiff here, so permutations are accepted by this helper.
    if len(actual) != len(expected) or set(actual).difference(expected):
        raise DataFormatError(f"Inappropriate header in {filename or 'table'}: {list(actual)!r}")


def require_positive(value: str, field: str, *, allow_expression: bool = False, allow_zero: bool = False) -> str:
    checked = check_value(value, allow_expression)
    if checked in (Constants.EMPTY, Constants.NULL):
        raise ValidationError(f"{field} must be specified")
    number = _as_finite_number(checked)
    if number is not None and (number < 0 if allow_zero else number <= 0):
        relation = "non-negative" if allow_zero else "positive"
        raise ValidationError(f"{field} must be {relation}")
    return checked


check_vertices = parse_vertices


def check_zone_xls_entries(entries: Sequence[str], *_context: object) -> object:
    from .records import Zone

    if len(entries) != len(Constants.ZONE_HEADER):
        raise ValidationError("Zone row has the wrong number of columns")
    return Zone(entries[0], entries[1], entries[2], entries[3], entries[4].split(","))


def check_material_xls_entries(entries: Sequence[str], *_context: object) -> object:
    from .records import Material

    if len(entries) != len(Constants.MATERIAL_HEADER):
        raise ValidationError("Material row has the wrong number of columns")
    return Material(*entries)


def check_construction_xls_entries(entries: Sequence[str], *_context: object) -> object:
    from .records import Construction

    if len(entries) != len(Constants.CONSTRUCTION_HEADER):
        raise ValidationError("Construction row has the wrong number of columns")
    return Construction(entries[0], entries[1], entries[2].split(","), entries[3].split(","), entries[4], entries[5])


def check_nomass_construction_xls_entries(entries: Sequence[str], *_context: object) -> object:
    from .records import NoMassConstruction

    if len(entries) != len(Constants.NOMASS_CONSTRUCTION_HEADER):
        raise ValidationError("No-mass construction row has the wrong number of columns")
    return NoMassConstruction(*entries)


def check_window_xls_entries(entries: Sequence[str], *_context: object) -> object:
    from .records import Window

    if len(entries) != len(Constants.WINDOW_HEADER):
        raise ValidationError("Window row has the wrong number of columns")
    return Window(*entries)


def check_parameter_xls_entries(entries: Sequence[str], *_context: object) -> object:
    from .records import Parameter

    if len(entries) != len(Constants.PARAMETER_HEADER):
        raise ValidationError("Parameter row has the wrong number of columns")
    return Parameter(*entries)


def check_buildingelement_xls_entries(entries: Sequence[str], *_context: object) -> object:
    from .records import BuildingElement

    if len(entries) != len(Constants.BUILDING_ELEMENT_HEADER):
        raise ValidationError("Building-element row has the wrong number of columns")
    return BuildingElement(
        entries[0], entries[1], entries[2], entries[3], entries[4], entries[5],
        entries[6], parse_vertices(entries[7]),
    )
