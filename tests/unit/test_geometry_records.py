import numpy as np
import pytest

from brcm.constants import Constants
from brcm.exceptions import ValidationError
from brcm.geometry import parse_vertices, polygon_area_3d
from brcm.primitives import Vertex
from brcm.records import (
    BuildingElement, Construction, Material, NoMassConstruction, Parameter,
    Window, Zone,
)


def square_vertices():
    return (Vertex(0, 0, 0), Vertex(2, 0, 0), Vertex(2, 2, 0), Vertex(0, 2, 0))


def test_vertex_parsing_and_polygon_geometry():
    vertices = parse_vertices("(0,0,0),(2,0,0),(2,2,0),(0,2,0)")
    assert isinstance(vertices, tuple)
    assert polygon_area_3d(vertices) == pytest.approx(4)
    assert parse_vertices("NULL") == Constants.NULL
    assert parse_vertices("NaN") == ()
    with pytest.raises(ValidationError):
        parse_vertices("(0, 0,0),(1,0,0),(0,1,0)")
    with pytest.raises(ValidationError):
        parse_vertices("(0,0,0),(1,0,0),(0,1,1),(0,0,3)")


def test_every_thermal_record_type():
    zone = Zone("Z0001", "Office", "4", "12", ["ZoneGrp_Office"])
    material = Material("M0001", "Concrete", "1000", "0.5", "2000", "")
    resistance = Material("M0002", "Air", "", "", "", "0.3")
    construction = Construction("C0001", "Wall", ["M0001"], ["0.2"], "7", "12")
    nomass = NoMassConstruction("NMC0001", "Opening", "100")
    window = Window("W0001", "Window", "1", "0.1", "UWindow", "0.5")
    parameter = Parameter("UWindow", "U value", "1.2")
    element = BuildingElement(
        "B0001", "Floor", "C0001", "ADB", "Z0001", "", "4", square_vertices()
    )
    assert zone.group == ["ZoneGrp_Office"]
    assert material.R_value == ""
    assert resistance.R_value == "0.3"
    assert construction.material_identifiers == ["M0001"]
    assert nomass.U_value == "100"
    assert window.U_value == "UWindow"
    assert parameter.value == "1.2"
    assert element.compute_area() == pytest.approx(4)
    assert element.is_horizontal()
    np.testing.assert_array_equal(element.compute_center(), [[1], [1], [0]])


def test_record_validation_failures():
    with pytest.raises(ValidationError):
        Zone("zone", "", "1", "1", [""])
    with pytest.raises(ValidationError):
        Parameter("bad-name", "", "1")
    with pytest.raises(ValidationError):
        Material("M0001", "", "", "", "", "")
    with pytest.raises(ValidationError):
        Construction("C0001", "", ["M0001"], ["1", "2"], "1", "1")
    with pytest.raises(ValidationError):
        NoMassConstruction("NMC0001", "", "0")
    with pytest.raises(ValidationError):
        Window("W0001", "", "1", "0", "1", "2")
    with pytest.raises(ValidationError):
        BuildingElement("B0001", "", "C0001", "AMB", "GND", "", "1", square_vertices())

