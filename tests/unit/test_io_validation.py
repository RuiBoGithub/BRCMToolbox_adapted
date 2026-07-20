from pathlib import Path

import pytest

from brcm.constants import Constants
from brcm.exceptions import DataFormatError, ValidationError
from brcm.io import choose_table_file, get_data_tables_from_file, read_cell_from_file
from brcm.records import BuildingElement, Construction, Material, NoMassConstruction, Parameter, Window, Zone
from brcm.validation import (
    check_buildingelement_xls_entries, check_construction_xls_entries,
    check_file_extension, check_free_description, check_group_identifiers,
    check_group_values, check_identifier, check_identifier_adjacent,
    check_material_xls_entries, check_nomass_construction_xls_entries,
    check_parameter_xls_entries, check_special_group_identifiers,
    check_special_identifier, check_uniqueness_id, check_value,
    check_window_xls_entries, check_xls_file_header, check_zone_group,
    check_zone_xls_entries,
)


def test_semicolon_csv_nan_mixed_types_and_trailing_delimiter(tmp_path):
    path = tmp_path / "table.csv"
    path.write_text("identifier;value;empty;\nA;1;;\n", encoding="utf-8")
    cells = read_cell_from_file(path)
    assert cells[0] == ["identifier", "value", "empty", "NaN"]
    assert cells[1] == ["A", 1.0, "NaN", "NaN"]
    tables, anchors = get_data_tables_from_file(path, ("identifier", "value", "empty"))
    assert tables == [[list(("identifier", "value", "empty")), ["A", "1", ""]]]
    assert anchors[0].row == 0 and anchors[0].matlab_row == 1


def test_csv_precedence_over_excel(tmp_path):
    for name in ("zones.xlsx", "zones.xls", "zones.csv"):
        (tmp_path / name).touch()
    assert choose_table_file(tmp_path, "zones").suffix == ".csv"


def test_all_scalar_and_group_check_helpers():
    assert check_identifier("Z0001", "Z") == "Z0001"
    assert check_special_identifier("ZoneGrp_North") == "ZoneGrp_North"
    assert check_identifier_adjacent("AMB") == "AMB"
    assert check_free_description("NaN") == ""
    assert check_value("12.5", False) == "12.5"
    assert check_value("UWindow*2", True) == "UWindow*2"
    assert check_group_identifiers("M0001,M0002", "M") == ["M0001", "M0002"]
    assert check_special_group_identifiers("Z0001,Group", "Z") == ["Z0001", "Group"]
    assert check_group_values("0,1.5") == [0, 1.5]
    assert check_zone_group("ZoneGrp_A,ZoneGrp_B") == ["ZoneGrp_A", "ZoneGrp_B"]
    check_uniqueness_id(["Z0001"], "Z0002")
    check_xls_file_header(["b", "a"], ["a", "b"])
    assert check_file_extension(".csv") == ".csv"


@pytest.mark.parametrize(
    "call",
    [
        lambda: check_identifier("Z1", "Z"),
        lambda: check_special_identifier("bad-identifier"),
        lambda: check_identifier_adjacent("OUTSIDE"),
        lambda: check_value("abc", False),
        lambda: check_group_identifiers("M1", "M"),
        lambda: check_group_values("abc"),
        lambda: check_zone_group("bad-name"),
        lambda: check_uniqueness_id(["Z0001"], "Z0001"),
        lambda: check_xls_file_header(["wrong"], ["right"]),
        lambda: check_file_extension(".txt"),
    ],
)
def test_check_helper_failure_rules(call):
    with pytest.raises((ValidationError, DataFormatError)):
        call()


def test_all_record_row_check_functions():
    assert isinstance(check_zone_xls_entries(["Z0001", "", "1", "3", "Group"]), Zone)
    assert isinstance(check_material_xls_entries(["M0001", "", "1", "1", "1", ""]), Material)
    assert isinstance(check_construction_xls_entries(["C0001", "", "M0001", "1", "1", "1"]), Construction)
    assert isinstance(check_nomass_construction_xls_entries(["NMC0001", "", "1"]), NoMassConstruction)
    assert isinstance(check_window_xls_entries(["W0001", "", "1", "0", "1", "0.5"]), Window)
    assert isinstance(check_parameter_xls_entries(["P", "", "1"]), Parameter)
    record = check_buildingelement_xls_entries([
        "B0001", "", "C0001", "ADB", "Z0001", "", "1",
        "(0,0,0),(1,0,0),(1,1,0),(0,1,0)",
    ])
    assert isinstance(record, BuildingElement)


def test_anchor_and_exact_table_header_failures(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("wrong;header;\n", encoding="utf-8")
    with pytest.raises(DataFormatError):
        get_data_tables_from_file(path, ("identifier", "value"))

