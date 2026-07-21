from __future__ import annotations
from pathlib import Path
import warnings
from .normalize import normalize_idf_objects
from .parser import EnergyPlusParser,LegacyIDDParser
from .records import ConversionAudit,ConversionResult
from .sheets import generate_brcm_tables
from ..io import write_semicolon_table
from ..thermal_data import ThermalModelData

def convert_idf_to_brcm_data(idf_path: str|Path,parser: EnergyPlusParser|None=None,
                             idd_path: str|Path|None=None) -> ConversionResult:
    if parser is not None and idd_path is not None:
        raise ValueError("Pass either parser or idd_path, not both")
    path=Path(idf_path)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        objects=(parser or LegacyIDDParser(idd_path=idd_path)).parse(path); normalized=normalize_idf_objects(objects)
    return ConversionResult(generate_brcm_tables(normalized),normalized,path,tuple(str(item.message) for item in caught))

def convert_idf_to_brcm(idf_path: str|Path,output_directory: str|Path,
                        parser: EnergyPlusParser|None=None,overwrite: bool=False,
                        idd_path: str|Path|None=None) -> ConversionResult:
    result=convert_idf_to_brcm_data(idf_path,parser,idd_path); output=Path(output_directory)
    if output.exists() and any(output.iterdir()) and not overwrite: raise FileExistsError(f"Output directory is not empty: {output}")
    output.mkdir(parents=True,exist_ok=True)
    for name,rows in result.tables.items(): write_semicolon_table(output/f"{name}.csv",rows)
    return result

def conversion_to_thermal_model_data(result: ConversionResult) -> ThermalModelData:
    return ThermalModelData.from_tables(result.tables)

def audit_conversion(result: ConversionResult,thermal_model=None) -> ConversionAudit:
    boundaries=[surface.outside_boundary.casefold() for surface in result.normalized_model.surfaces]
    return ConversionAudit(
        result.normalized_model.version,len(result.normalized_model.zones),len(boundaries),len(result.normalized_model.windows),
        len(result.tables["buildingelements"])-1,None if thermal_model is None else len(thermal_model.state_identifiers),
        sum(item=="outdoors" for item in boundaries),sum(item=="ground" for item in boundaries),
        sum(item=="adiabatic" for item in boundaries),sum(item in ("surface","zone","zone/surface") for item in boundaries),
        result.normalized_model.ignored_object_types,result.warnings,
    )

def from_energyplus(idf_path: str|Path,parser: EnergyPlusParser|None=None,
                    idd_path: str|Path|None=None):
    """Thin in-memory IDF → BRCM tables → ThermalModelData → ThermalModel path."""
    from ..thermal_generation import generate_thermal_model
    result=convert_idf_to_brcm_data(idf_path,parser,idd_path)
    return generate_thermal_model(conversion_to_thermal_model_data(result))

convertIDFToBRCM=convert_idf_to_brcm
