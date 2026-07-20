"""Constants and file conventions from MATLAB ``Constants.m``."""

from __future__ import annotations


class Constants:
    C_AIR = 1012.0
    RHO_AIR = 1.2041

    NULL = "NULL"
    NAN = "NaN"
    EMPTY = ""
    ZERO = "0"
    NUMERIC_FORMAT = ".10g"

    GROUND_IDENTIFIER = "GND"
    AMBIENT_IDENTIFIER = "AMB"
    ADIABATIC_IDENTIFIER = "ADB"
    EXTERIOR_IDENTIFIERS = (GROUND_IDENTIFIER, AMBIENT_IDENTIFIER, ADIABATIC_IDENTIFIER)
    TBC_WITH_FILM_COEFFICIENT = "TBCwFC"
    TBC_WITHOUT_FILM_COEFFICIENT = "TBCwoFC"
    STATE_VARIABLE = "x"
    LAYER_STATE_VARIABLE = "s"
    HEAT_FLUX_VARIABLE = "q"
    INPUT_VARIABLE = "u"
    DISTURBANCE_VARIABLE = "v"
    AMBIENT_TEMPERATURE_VARIABLE = "Tamb"
    GROUND_TEMPERATURE_VARIABLE = "Tgnd"

    TOL_PLANARITY = 0.05
    TOL_AREA = 0.01
    TOL_HEIGHT = 0.01
    TOL_NORMAL = 0.01

    ZONE_HEADER = ("identifier", "description", "area", "volume", "group")
    BUILDING_ELEMENT_HEADER = (
        "identifier", "description", "construction_identifier", "adjacent_A",
        "adjacent_B", "window_identifier", "area", "vertices",
    )
    CONSTRUCTION_HEADER = (
        "identifier", "description", "material_identifiers", "thickness",
        "conv_coeff_adjacent_A", "conv_coeff_adjacent_B",
    )
    NOMASS_CONSTRUCTION_HEADER = ("identifier", "description", "U_value")
    MATERIAL_HEADER = (
        "identifier", "description", "specific_heat_capacity",
        "specific_thermal_resistance", "density", "R_value",
    )
    WINDOW_HEADER = ("identifier", "description", "glass_area", "frame_area", "U_value", "SHGC")
    PARAMETER_HEADER = ("identifier", "description", "value")

    TABLE_SCHEMAS = {
        "zones": ZONE_HEADER,
        "buildingelements": BUILDING_ELEMENT_HEADER,
        "constructions": CONSTRUCTION_HEADER,
        "materials": MATERIAL_HEADER,
        "windows": WINDOW_HEADER,
        "parameters": PARAMETER_HEADER,
        "nomassconstructions": NOMASS_CONSTRUCTION_HEADER,
    }
    SUPPORTED_EXTENSIONS = (".xls", ".xlsx", ".csv")


def matlab_number(value: float | int) -> str:
    """Match the toolbox's observable ``num2str(..., '%.10g')`` convention."""

    return format(float(value), Constants.NUMERIC_FORMAT)
