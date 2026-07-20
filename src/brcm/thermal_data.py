"""Mutable repository for the seven BRCM thermal-model input tables."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import fields
from pathlib import Path
from typing import Any, TypeVar

from .constants import Constants, matlab_number
from .exceptions import DataFormatError, ExpressionError, ValidationError
from .expressions import evaluate_expression, expression_names
from .geometry import parse_vertices
from .helpers import get_id_index
from .io import choose_table_file, get_data_tables_from_file, write_semicolon_table
from .primitives import Vertex
from .records import (
    BuildingElement,
    Construction,
    Material,
    NoMassConstruction,
    Parameter,
    Window,
    Zone,
)
from .validation import check_uniqueness_id
from . import validation as _validation

Record = TypeVar("Record")


class ThermalModelData:
    """Ordered, mutable equivalent of MATLAB ``ThermalModelData``."""

    check_file_extension = staticmethod(_validation.check_file_extension)
    check_free_description = staticmethod(_validation.check_free_description)
    check_group_identifiers = staticmethod(_validation.check_group_identifiers)
    check_group_values = staticmethod(_validation.check_group_values)
    check_identifier = staticmethod(_validation.check_identifier)
    check_identifier_adjacent = staticmethod(_validation.check_identifier_adjacent)
    check_special_group_identifiers = staticmethod(_validation.check_special_group_identifiers)
    check_special_identifier = staticmethod(_validation.check_special_identifier)
    check_uniqueness_id = staticmethod(_validation.check_uniqueness_id)
    check_value = staticmethod(_validation.check_value)
    check_vertices = staticmethod(_validation.check_vertices)
    check_xls_file_header = staticmethod(_validation.check_xls_file_header)
    check_zone_group = staticmethod(_validation.check_zone_group)
    check_zone_xls_entries = staticmethod(_validation.check_zone_xls_entries)
    check_material_xls_entries = staticmethod(_validation.check_material_xls_entries)
    check_construction_xls_entries = staticmethod(_validation.check_construction_xls_entries)
    check_nomass_construction_xls_entries = staticmethod(_validation.check_nomass_construction_xls_entries)
    check_window_xls_entries = staticmethod(_validation.check_window_xls_entries)
    check_parameter_xls_entries = staticmethod(_validation.check_parameter_xls_entries)
    check_buildingelement_xls_entries = staticmethod(_validation.check_buildingelement_xls_entries)

    def __init__(self) -> None:
        self.zones: list[Zone] = []
        self.building_elements: list[BuildingElement] = []
        self.constructions: list[Construction] = []
        self.materials: list[Material] = []
        self.windows: list[Window] = []
        self.parameters: list[Parameter] = []
        self.nomass_constructions: list[NoMassConstruction] = []
        self.source_files: dict[str, Path | None] = {name: None for name in Constants.TABLE_SCHEMAS}
        self.data_directory_source: Path | None = None
        self.data_directory_target: Path | None = None
        self.is_dirty = False

    @classmethod
    def from_directory(cls, directory: str | Path) -> "ThermalModelData":
        instance = cls()
        instance.load_directory(directory)
        return instance

    @classmethod
    def from_tables(cls, tables: dict[str, list[list[Any]]]) -> "ThermalModelData":
        """Load the seven logical tables directly, without temporary files."""
        missing=set(Constants.TABLE_SCHEMAS).difference(tables)
        if missing:
            raise DataFormatError(f"Missing thermal-model tables: {sorted(missing)}")
        normalized: dict[str,list[list[str]]] = {}
        for name,header in Constants.TABLE_SCHEMAS.items():
            rows=tables[name]
            if not rows or tuple(str(x) for x in rows[0]) != header:
                raise DataFormatError(f"Invalid {name} header")
            normalized[name]=[[Constants.EMPTY if value is None else str(value) for value in row] for row in rows]
            if any(len(row)!=len(header) for row in normalized[name]):
                raise DataFormatError(f"Invalid {name} row width")
        obj=cls()
        obj.zones=[Zone(r[0],r[1],r[2],r[3],r[4].split(',') if r[4] else []) for r in normalized['zones'][1:]]
        obj.building_elements=[BuildingElement(r[0],r[1],r[2],r[3],r[4],r[5],r[6],parse_vertices(r[7])) for r in normalized['buildingelements'][1:]]
        obj.constructions=[Construction(r[0],r[1],r[2].split(','),r[3].split(','),r[4],r[5]) for r in normalized['constructions'][1:]]
        obj.materials=[Material(*r) for r in normalized['materials'][1:]]
        obj.windows=[Window(*r) for r in normalized['windows'][1:]]
        obj.parameters=[Parameter(*r) for r in normalized['parameters'][1:]]
        obj.nomass_constructions=[NoMassConstruction(*r) for r in normalized['nomassconstructions'][1:]]
        for label,records in (("Zone",obj.zones),("Building element",obj.building_elements),("Construction",obj.constructions),("Material",obj.materials),("Window",obj.windows),("Parameter",obj.parameters),("No-mass construction",obj.nomass_constructions)):
            obj._assert_unique(records,label)
        obj.validate_references(); obj.is_dirty=True
        return obj

    fromTables = from_tables

    def load_directory(self, directory: str | Path) -> None:
        directory = Path(directory)
        if not directory.is_dir():
            raise DataFormatError(f"Not a thermal-model data directory: {directory}")
        # Match MATLAB's observable load order.
        self.load_zones_data(choose_table_file(directory, "zones"))
        self.load_building_elements_data(choose_table_file(directory, "buildingelements"))
        self.load_constructions_data(choose_table_file(directory, "constructions"))
        self.load_materials_data(choose_table_file(directory, "materials"))
        self.load_windows_data(choose_table_file(directory, "windows"))
        self.load_parameters_data(choose_table_file(directory, "parameters"))
        self.load_nomass_constructions_data(choose_table_file(directory, "nomassconstructions"))
        self.validate_references()

    loadThermalModelData = load_directory

    @staticmethod
    def _rows(path: str | Path, header: tuple[str, ...]) -> list[list[str]]:
        tables, _anchors = get_data_tables_from_file(path, header, replace_nans=True)
        return tables[0][1:]

    @staticmethod
    def _assert_unique(records: list[Record], label: str) -> None:
        seen: list[str] = []
        for record in records:
            identifier = getattr(record, "identifier")
            check_uniqueness_id(seen, identifier, label)
            seen.append(identifier)

    def _loaded(self, name: str, path: str | Path) -> None:
        resolved = Path(path)
        self.source_files[name] = resolved
        self.data_directory_source = resolved.parent
        self.is_dirty = True

    def load_zones_data(self, path: str | Path) -> None:
        records = [Zone(row[0], row[1], row[2], row[3], row[4].split(",")) for row in self._rows(path, Constants.ZONE_HEADER)]
        self._assert_unique(records, "Zone")
        self.zones = records
        self._loaded("zones", path)

    loadZonesData = load_zones_data

    def load_building_elements_data(self, path: str | Path) -> None:
        records = [
            BuildingElement(row[0], row[1], row[2], row[3], row[4], row[5], row[6], parse_vertices(row[7]))
            for row in self._rows(path, Constants.BUILDING_ELEMENT_HEADER)
        ]
        self._assert_unique(records, "Building element")
        self.building_elements = records
        self._loaded("buildingelements", path)

    loadBuildingElementsData = load_building_elements_data

    def load_constructions_data(self, path: str | Path) -> None:
        records = [
            Construction(row[0], row[1], row[2].split(","), row[3].split(","), row[4], row[5])
            for row in self._rows(path, Constants.CONSTRUCTION_HEADER)
        ]
        self._assert_unique(records, "Construction")
        self.constructions = records
        self._loaded("constructions", path)

    loadConstructionsData = load_constructions_data

    def load_materials_data(self, path: str | Path) -> None:
        records = [Material(*row) for row in self._rows(path, Constants.MATERIAL_HEADER)]
        self._assert_unique(records, "Material")
        self.materials = records
        self._loaded("materials", path)

    loadMaterialsData = load_materials_data

    def load_windows_data(self, path: str | Path) -> None:
        records = [Window(*row) for row in self._rows(path, Constants.WINDOW_HEADER)]
        self._assert_unique(records, "Window")
        self.windows = records
        self._loaded("windows", path)

    loadWindowsData = load_windows_data

    def load_parameters_data(self, path: str | Path) -> None:
        records = [Parameter(*row) for row in self._rows(path, Constants.PARAMETER_HEADER)]
        self._assert_unique(records, "Parameter")
        self.parameters = records
        self._loaded("parameters", path)

    loadParametersData = load_parameters_data

    def load_nomass_constructions_data(self, path: str | Path) -> None:
        records = [NoMassConstruction(*row) for row in self._rows(path, Constants.NOMASS_CONSTRUCTION_HEADER)]
        self._assert_unique(records, "No-mass construction")
        self.nomass_constructions = records
        self._loaded("nomassconstructions", path)

    loadNoMassConstructionsData = load_nomass_constructions_data

    def _parameter_values(self) -> dict[str, float]:
        values: dict[str, float] = {}
        pending = {parameter.identifier: parameter.value for parameter in self.parameters}
        while pending:
            progressed = False
            for name, expression in list(pending.items()):
                if expression_names(expression).issubset(values):
                    values[name] = evaluate_expression(expression, values)
                    del pending[name]
                    progressed = True
            if not progressed:
                unresolved = ", ".join(sorted(pending))
                raise ExpressionError(f"Cyclic or unknown parameter references: {unresolved}")
        return values

    def eval_str(self, expression: str, error_context: str | None = None) -> float:
        try:
            return evaluate_expression(expression, self._parameter_values())
        except ExpressionError as error:
            suffix = f" ({error_context})" if error_context else ""
            raise ExpressionError(f"Evaluating {expression!r}{suffix} failed: {error}") from error

    evalStr = eval_str

    def _record_for_identifier(self, identifier: str) -> Any:
        groups: tuple[tuple[str, list[Any]], ...] = (
            (NoMassConstruction.KEY, self.nomass_constructions),
            (Zone.KEY, self.zones),
            (BuildingElement.KEY, self.building_elements),
            (Construction.KEY, self.constructions),
            (Material.KEY, self.materials),
            (Window.KEY, self.windows),
        )
        for key, records in groups:
            if identifier.startswith(key) and len(identifier) == len(key) + 4:
                matches = [record for record in records if record.identifier == identifier]
                if len(matches) != 1:
                    raise ValidationError(f"Unknown identifier {identifier!r}")
                return matches[0]
        matches = [parameter for parameter in self.parameters if parameter.identifier == identifier]
        if len(matches) != 1:
            raise ValidationError(f"Unknown identifier {identifier!r}")
        return matches[0]

    def get_value(self, identifier: str, property_name: str) -> Any:
        record = self._record_for_identifier(identifier)
        if property_name not in {field.name for field in fields(record)}:
            raise ValidationError(f"Unknown property {property_name!r} for {type(record).__name__}")
        value = getattr(record, property_name)
        if isinstance(value, str):
            try:
                return self.eval_str(value)
            except ExpressionError:
                return value
        return value

    getValue = get_value

    def set_value(self, identifier: str, property_name: str, value: Any) -> None:
        current = self._record_for_identifier(identifier)
        field_names = {field.name for field in fields(current)}
        if property_name not in field_names or property_name == "identifier":
            raise ValidationError(f"Property {property_name!r} cannot be set")
        candidate = deepcopy(current)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            value = matlab_number(value)
        setattr(candidate, property_name, value)
        candidate.__post_init__()
        for records in (
            self.zones, self.building_elements, self.constructions, self.materials,
            self.windows, self.parameters, self.nomass_constructions,
        ):
            for index, record in enumerate(records):
                if record is current:
                    records[index] = candidate
                    try:
                        self.validate_references()
                    except Exception:
                        records[index] = current
                        raise
                    self.is_dirty = True
                    return
        raise AssertionError("Record repository lookup became inconsistent")

    setValue = set_value

    def validate_references(self) -> None:
        zone_ids = {item.identifier for item in self.zones}
        material_ids = {item.identifier for item in self.materials}
        construction_ids = {item.identifier for item in self.constructions}
        nomass_ids = {item.identifier for item in self.nomass_constructions}
        window_ids = {item.identifier for item in self.windows}
        parameter_ids = {item.identifier for item in self.parameters}

        for construction in self.constructions:
            missing = set(construction.material_identifiers).difference(material_ids)
            if missing:
                raise ValidationError(f"Construction {construction.identifier} references missing materials {sorted(missing)}")
        for element in self.building_elements:
            if element.construction_identifier not in construction_ids | nomass_ids | {Constants.NULL}:
                raise ValidationError(f"Building element {element.identifier} references a missing construction")
            for adjacent in (element.adjacent_A, element.adjacent_B):
                if adjacent.startswith("Z") and adjacent not in zone_ids:
                    raise ValidationError(f"Building element {element.identifier} references missing zone {adjacent}")
            if element.window_identifier and element.window_identifier not in window_ids | {Constants.NULL}:
                raise ValidationError(f"Building element {element.identifier} references missing window")
        expression_fields = {
            Material: ("specific_heat_capacity", "specific_thermal_resistance", "density", "R_value"),
            Construction: ("thickness", "conv_coeff_adjacent_A", "conv_coeff_adjacent_B"),
            Window: ("glass_area", "frame_area", "U_value", "SHGC"),
            NoMassConstruction: ("U_value",),
        }
        for record in [*self.materials, *self.constructions, *self.windows, *self.nomass_constructions]:
            for field_name in expression_fields[type(record)]:
                value = getattr(record, field_name)
                candidates = value if isinstance(value, list) else [value]
                for candidate in candidates:
                    if isinstance(candidate, str) and candidate not in (Constants.EMPTY, Constants.NULL):
                        try:
                            names = expression_names(candidate)
                        except ExpressionError:
                            continue
                        missing = names.difference(parameter_ids)
                        if missing:
                            raise ValidationError(
                                f"{record.identifier}.{field_name} references missing parameters {sorted(missing)}"
                            )

    def _vertices_string(self, value: tuple[Vertex, ...] | str) -> str:
        if isinstance(value, str):
            return value
        return ",".join(
            f"({matlab_number(vertex.x)},{matlab_number(vertex.y)},{matlab_number(vertex.z)})"
            for vertex in value
        )

    def to_tables(self) -> dict[str, list[list[str]]]:
        tables: dict[str, list[list[str]]] = {}
        mapping = {
            "zones": self.zones,
            "buildingelements": self.building_elements,
            "constructions": self.constructions,
            "materials": self.materials,
            "windows": self.windows,
            "parameters": self.parameters,
            "nomassconstructions": self.nomass_constructions,
        }
        for name, records in mapping.items():
            header = Constants.TABLE_SCHEMAS[name]
            rows = [list(header)]
            for record in records:
                row: list[str] = []
                for column in header:
                    value = getattr(record, column)
                    if column == "vertices":
                        row.append(self._vertices_string(value))
                    elif isinstance(value, list):
                        row.append(",".join(value))
                    else:
                        row.append(str(value) if value != Constants.EMPTY else Constants.NAN)
                rows.append(row)
            tables[name] = rows
        return tables

    def write_directory(self, directory: str | Path) -> None:
        directory = Path(directory)
        for name, rows in self.to_tables().items():
            write_semicolon_table(directory / f"{name}.csv", rows)
        self.data_directory_target = directory

    writeThermalModelData = write_directory

    def get_zone_idx_from_identifier(self, identifier: str) -> int:
        return get_id_index([zone.identifier for zone in self.zones], identifier)

    getZoneIdxFromIdentifier = get_zone_idx_from_identifier

    def get_zone_identifiers_from_group_identifier(self, group: str) -> list[str]:
        result = [zone.identifier for zone in self.zones if group in zone.group]
        if not result:
            raise ValidationError(f"Unknown zone group {group!r}")
        return result

    getZoneIdentifiersFromGroupIdentifier = get_zone_identifiers_from_group_identifier

    def get_building_element_idx_from_identifier(self, identifier: str) -> int:
        return get_id_index([item.identifier for item in self.building_elements], identifier)

    def get_construction_idx_from_identifier(self, identifier: str) -> int:
        return get_id_index([item.identifier for item in self.constructions], identifier)

    def get_material_idx_from_identifier(self, identifier: str) -> int:
        return get_id_index([item.identifier for item in self.materials], identifier)

    def get_window_idx_from_identifier(self, identifier: str) -> int:
        return get_id_index([item.identifier for item in self.windows], identifier)

    def get_parameter_idx_from_identifier(self, identifier: str) -> int:
        return get_id_index([item.identifier for item in self.parameters], identifier)

    def get_nomass_construction_idx_from_identifier(self, identifier: str) -> int:
        return get_id_index([item.identifier for item in self.nomass_constructions], identifier)

    getBuildingElementIdxFromIdentifier = get_building_element_idx_from_identifier
    getConstructionIdxFromIdentifier = get_construction_idx_from_identifier
    getMaterialIdxFromIdentifier = get_material_idx_from_identifier
    getWindowIdxFromIdentifier = get_window_idx_from_identifier
    getParameterIdxFromIdentifier = get_parameter_idx_from_identifier
    getNoMassConstructionIdxFromIdentifier = get_nomass_construction_idx_from_identifier
