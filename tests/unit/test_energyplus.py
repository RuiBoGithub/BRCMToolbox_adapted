from __future__ import annotations

from pathlib import Path
import numpy as np
import pytest

from brcm import ThermalModelData,generate_thermal_model
from brcm.energyplus import LegacyIDDParser,convert_idf_to_brcm,convert_idf_to_brcm_data,generate_brcm_tables,get_objects_from_string,normalize_idf_objects,parse_idd
from brcm.exceptions import DataFormatError,ValidationError


BASE="""
Version,8.1;
GlobalGeometryRules,UpperLeftCorner,CounterClockWise,{coordinates};
{materials}
{constructions}
{zones}
{surfaces}
{extra}
"""
MAT="Material,Brick,Rough,0.1,0.5,1800,840;"
CON="Construction,Wall Construction,Brick;"
ZONE="Zone,Room,0,0,0,0,1,1,3,30,10;"

def wall(name="Wall",zone="Room",boundary="Outdoors",outside="",construction="Wall Construction",x=0):
    return f"BuildingSurface:Detailed,{name},Wall,{construction},{zone},{boundary},{outside},SunExposed,WindExposed,0.5,4,{x},0,0,{x+4},0,0,{x+4},0,3,{x},0,3;"

def normalized(text): return normalize_idf_objects(get_objects_from_string(text))
def snippet(**kwargs):
    defaults=dict(coordinates="World",materials=MAT,constructions=CON,zones=ZONE,surfaces=wall(),extra="")
    defaults.update(kwargs); return BASE.format(**defaults)

def test_parser_comments_quotes_repetition_and_order():
    objects=get_objects_from_string('Version,8.1; ! comment\nZone,"Odd, Name",0; Zone,Second,0;')
    assert [o.type for o in objects]==["Version","Zone","Zone"]
    assert objects[1].values[0]=="Odd, Name"

@pytest.mark.parametrize("bad",["Zone,A",'Zone,"unterminated;'])
def test_parser_rejects_malformed_objects(bad):
    with pytest.raises(DataFormatError): get_objects_from_string(bad)

def test_bundled_idd_labels_are_associated():
    parser=LegacyIDDParser(); objects=parser.parse("tests/fixtures/energyplus/minimal.idf")
    material=next(o for o in objects if o.type=="Material")
    assert material.field_names[:4]==("Name","Roughness","Thickness","Conductivity")
    labels=parse_idd("EP2BRCM/IDDFiles/V8-1-0-Energy+.idd")
    assert labels["buildingsurface:detailed"][:3]==("Name","Surface Type","Construction Name")

def test_one_zone_and_external_wall_normalization_and_sheets():
    model=normalized(snippet()); tables=generate_brcm_tables(model)
    assert [len(tables[k])-1 for k in ("zones","buildingelements","constructions","materials")]==[1,1,1,1]
    assert tables["zones"][1][:2]==["Z0001","Room"]
    assert tables["buildingelements"][1][3:5]==["AMB","Z0001"]
    assert float(tables["buildingelements"][1][6])==12

def test_two_zone_surface_adjacency_merges_pair_once():
    zones=ZONE+"Zone,Room2,0,0,0,0,1,1,3,30,10;"
    surfaces=wall("Side A","Room","Surface","Side B")+wall("Side B","Room2","Surface","Side A")
    tables=generate_brcm_tables(normalized(snippet(zones=zones,surfaces=surfaces)))
    assert len(tables["buildingelements"])==2
    assert tables["buildingelements"][1][3:5]==["Z0002","Z0001"]

@pytest.mark.parametrize(("boundary","expected"),[("Ground","GND"),("Adiabatic","ADB")])
def test_ground_and_adiabatic_boundaries(boundary,expected):
    tables=generate_brcm_tables(normalized(snippet(surfaces=wall(boundary=boundary))))
    assert tables["buildingelements"][1][3]==expected

def test_multilayer_and_nomass_material_layer():
    materials=MAT+"Material:NoMass,Insulation,Rough,2.5;"
    constructions="Construction,Wall Construction,Brick,Insulation;"
    tables=generate_brcm_tables(normalized(snippet(materials=materials,constructions=constructions)))
    assert tables["constructions"][1][2]=="M0001,M0002"
    assert tables["constructions"][1][3]=="0.1,0"
    assert tables["materials"][2][-1]=="2.5"

def test_infrared_transparent_becomes_brcm_nomass_construction():
    text=snippet(materials="Material:InfraredTransparent,IR;",constructions="Construction,Wall Construction,IR;")
    tables=generate_brcm_tables(normalized(text))
    assert tables["nomassconstructions"][1][0]=="NMC0001"
    assert tables["buildingelements"][1][2]=="NMC0001"

def test_window_parent_area_mapping_and_parameters():
    extra="""WindowMaterial:SimpleGlazingSystem,Glass,2.7,0.6,0.7;
Construction,Window Construction,Glass;
FenestrationSurface:Detailed,Win,Window,Window Construction,Wall,,0.5,,1,4,1,0,1,3,0,1,3,0,2,1,0,2;"""
    tables=generate_brcm_tables(normalized(snippet(extra=extra)))
    assert len(tables["windows"])==2 and tables["buildingelements"][1][5]=="W0001"
    assert float(tables["windows"][1][2])==2
    assert tables["windows"][1][4].startswith("UValue_Window_EPConstr_")

def test_internal_mass_generates_double_connected_half_area_element():
    extra="InternalMass,Furniture,Wall Construction,Room,8;"
    tables=generate_brcm_tables(normalized(snippet(extra=extra)))
    row=tables["buildingelements"][-1]
    assert row[3:5]==["Z0001","Z0001"] and float(row[6])==4

def test_relative_coordinates_apply_zone_rotation_and_translation():
    zone="Zone,Room,90,10,20,3,1,1,3,30,10;"
    model=normalized(snippet(coordinates="Relative",zones=zone))
    np.testing.assert_allclose(model.surfaces[0].vertices[0],[10,20,3],atol=1e-12)
    np.testing.assert_allclose(model.surfaces[0].vertices[1],[10,24,3],atol=1e-12)

def test_in_memory_and_file_conversion_roundtrip(tmp_path):
    result=convert_idf_to_brcm_data("tests/fixtures/energyplus/minimal.idf")
    data=ThermalModelData.from_tables(result.tables); model=generate_thermal_model(data)
    assert model.A.shape==(2,2) and np.isfinite(model.A).all()
    output=tmp_path/"converted"; convert_idf_to_brcm("tests/fixtures/energyplus/minimal.idf",output)
    loaded=ThermalModelData.from_directory(output)
    assert loaded.to_tables()==data.to_tables()

def test_unsupported_thermal_object_fails_clearly():
    with pytest.raises(ValidationError,match="Unsupported thermal"):
        normalized(snippet(extra="Material:RoofVegetation,GreenRoof,Rough;"))

def test_legacy_wall_exterior_uses_idd_labels_and_area(tmp_path):
    text=snippet(surfaces="Wall:Exterior,Old Wall,Wall Construction,Room,180,90,0,0,0,4,3;")
    path=tmp_path/"legacy.idf"; path.write_text(text)
    model=normalize_idf_objects(LegacyIDDParser().parse(path))
    assert model.surfaces[0].outside_boundary=="Outdoors"
    assert model.surfaces[0].area==12
    assert generate_brcm_tables(model)["buildingelements"][1][3]=="AMB"
