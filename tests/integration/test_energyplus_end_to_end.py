from pathlib import Path

import numpy as np
import pytest

import brcm
from brcm import BuildingModel,ThermalModelData,generate_thermal_model,simulate_tm
from brcm.energyplus import audit_conversion,conversion_to_thermal_model_data,convert_idf_to_brcm_data
from brcm.energyplus.geometry import polygon_area

FIXTURES=Path(__file__).parents[1]/"fixtures"/"energyplus"

CASES={
    "single_zone_enclosure.idf":(1,4,0,4,5),
    "two_zone_interzone.idf":(2,4,0,3,5),
    "external_window.idf":(1,1,1,1,2),
    "ground_contact.idf":(1,1,0,1,2),
    "adiabatic.idf":(1,1,0,1,2),
    "multilayer.idf":(1,1,0,1,3),
    "nomass_airgap.idf":(1,1,0,1,2),
    "internal_mass.idf":(1,1,0,2,3),
    "relative_coordinates.idf":(1,1,0,1,2),
    "representative_multizone.idf":(2,6,1,6,8),
}
AREAS={
    "single_zone_enclosure.idf":[12,12,16,16],"two_zone_interzone.idf":[12,12,12,12],
    "external_window.idf":[12],"ground_contact.idf":[16],"adiabatic.idf":[12],"multilayer.idf":[12],
    "nomass_airgap.idf":[12],"internal_mass.idf":[12],"relative_coordinates.idf":[12],
    "representative_multizone.idf":[12,12,12,12,16,16],
}

def pipeline(name):
    result=convert_idf_to_brcm_data(FIXTURES/name)
    data=conversion_to_thermal_model_data(result)
    return result,data,generate_thermal_model(data)

@pytest.mark.parametrize("name,expected",CASES.items())
def test_fixture_pipeline_structure_and_determinism(name,expected):
    result,data,model=pipeline(name); zones,surfaces,windows,elements,states=expected
    assert (len(result.normalized_model.zones),len(result.normalized_model.surfaces),len(result.normalized_model.windows))==(zones,surfaces,windows)
    assert len(result.tables["buildingelements"])-1==elements
    assert [_surface_area(item) for item in result.normalized_model.surfaces]==pytest.approx(AREAS[name])
    assert [row[0] for row in result.tables["zones"][1:]]==[f"Z{i:04d}" for i in range(1,zones+1)]
    assert [row[0] for row in result.tables["buildingelements"][1:]]==[f"B{i:04d}" for i in range(1,elements+1)]
    assert len(model.state_identifiers)==len(model.heat_flux_identifiers)==states
    assert model.A.shape==model.Bq.shape==model.Xcap.shape==(states,states)
    assert np.isfinite(model.A).all() and np.isfinite(model.Bq).all() and np.isfinite(model.Xcap).all()
    assert np.all(np.diag(model.Xcap)>0)
    # Loading the generated schemas exercises every reference and identifier.
    assert ThermalModelData.from_tables(result.tables).to_tables()==data.to_tables()
    again=generate_thermal_model(conversion_to_thermal_model_data(convert_idf_to_brcm_data(FIXTURES/name)))
    assert model.state_identifiers==again.state_identifiers
    assert model.heat_flux_identifiers==again.heat_flux_identifiers
    np.testing.assert_array_equal(model.A,again.A)
    np.testing.assert_array_equal(model.Bq,again.Bq)
    np.testing.assert_array_equal(model.Xcap,again.Xcap)

def _surface_area(surface):
    return surface.area if surface.area is not None else polygon_area(surface.vertices)

def test_geometry_vertex_order_window_parent_and_relative_transform():
    result,_,_=pipeline("external_window.idf")
    wall=result.normalized_model.surfaces[0]; window=result.normalized_model.windows[0]
    assert wall.vertices==((0.,0.,0.),(4.,0.,0.),(4.,0.,3.),(0.,0.,3.))
    assert window.parent_surface==wall.name and window.glass_area==2
    rotated,_,_=pipeline("relative_coordinates.idf")
    np.testing.assert_allclose(rotated.normalized_model.surfaces[0].vertices,((10,20,3),(10,24,3),(10,24,6),(10,20,6)),atol=1e-12)

def test_topology_and_table_ordering():
    interzone,data,model=pipeline("two_zone_interzone.idf")
    assert [row[0] for row in interzone.tables["zones"][1:]]==["Z0001","Z0002"]
    assert [row[0] for row in interzone.tables["buildingelements"][1:]]==["B0001","B0002","B0003"]
    pair=interzone.tables["buildingelements"][2]
    assert pair[3:5]==["Z0002","Z0001"]
    assert "x_Z0001" in model.state_identifiers and "x_Z0002" in model.state_identifiers
    combined,_,_=pipeline("representative_multizone.idf")
    audit=audit_conversion(combined)
    assert (audit.ambient_boundaries,audit.ground_boundaries,audit.adiabatic_boundaries,audit.interzone_boundaries)==(2,1,1,2)
    assert any(row[3]=="GND" for row in combined.tables["buildingelements"][1:])
    assert any(row[3]=="ADB" for row in combined.tables["buildingelements"][1:])
    internal,_,_=pipeline("internal_mass.idf")
    assert internal.tables["buildingelements"][-1][3:5]==["Z0001","Z0001"]
    assert float(internal.tables["buildingelements"][-1][6])==4

def _write_case(tmp_path,name,material,vertices="0,0,0,4,0,0,4,0,3,0,0,3",extra_material="",layers="Mass"):
    text=f"""Version,8.1;
GlobalGeometryRules,UpperLeftCorner,CounterClockWise,World;
{material}
{extra_material}
Construction,Wall,{layers};
Zone,Room,0,0,0,0,1,1,3,30,10;
BuildingSurface:Detailed,Wall,Wall,Wall,Room,Outdoors,,SunExposed,WindExposed,0.5,4,{vertices};
"""
    path=tmp_path/name; path.write_text(text); return path

def test_insulation_mass_and_area_scaling(tmp_path):
    mass="Material,Mass,Rough,0.1,0.5,1800,840;"
    plain=brcm.from_energyplus(_write_case(tmp_path,"plain.idf",mass))
    insulated=brcm.from_energyplus(_write_case(tmp_path,"insulated.idf",mass,extra_material="Material:NoMass,Insulation,Rough,3;",layers="Insulation,Mass"))
    assert insulated.boundary_conditions["ambient"][0].value < plain.boundary_conditions["ambient"][0].value

    heavy=brcm.from_energyplus(_write_case(tmp_path,"heavy.idf","Material,Mass,Rough,0.1,0.5,3600,840;"))
    np.testing.assert_allclose(heavy.Xcap.diagonal()[1],2*plain.Xcap.diagonal()[1])

    doubled=brcm.from_energyplus(_write_case(tmp_path,"wide.idf",mass,"0,0,0,8,0,0,8,0,3,0,0,3"))
    np.testing.assert_allclose(doubled.Xcap.diagonal()[1],2*plain.Xcap.diagonal()[1])
    np.testing.assert_allclose(doubled.boundary_conditions["ambient"][0].value,2*plain.boundary_conditions["ambient"][0].value)

def test_window_reduces_opaque_thermal_mass_and_boundary_types():
    _,_,plain=pipeline("minimal.idf"); _,_,windowed=pipeline("external_window.idf")
    np.testing.assert_allclose(windowed.Xcap.diagonal()[1],plain.Xcap.diagonal()[1]*10/12)
    _,_,ground=pipeline("ground_contact.idf"); _,_,adiabatic=pipeline("adiabatic.idf")
    assert len(ground.boundary_conditions["ground"])==1 and not ground.boundary_conditions["ambient"]
    assert len(adiabatic.boundary_conditions["adiabatic"])==1 and not adiabatic.boundary_conditions["ambient"]
    # No applied external flux: the adiabatic model conserves a uniform temperature.
    np.testing.assert_allclose(adiabatic.A@np.full(2,20.),0,atol=1e-14)

def test_interzone_wall_couples_the_correct_zone_states():
    _,_,model=pipeline("two_zone_interzone.idf")
    z1,z2=(model.state_identifiers.index("x_Z0001"),model.state_identifiers.index("x_Z0002"))
    partition=next(i for i,name in enumerate(model.state_identifiers) if "B0002" in name)
    assert model.A[z1,partition]>0 and model.A[z2,partition]>0
    assert model.A[partition,z1]>0 and model.A[partition,z2]>0

def test_thermal_simulations_are_finite_directional_conservative_and_repeatable():
    _,_,ambient=pipeline("minimal.idf"); nx=len(ambient.state_identifiers); x0=np.full(nx,20.)
    bc=ambient.boundary_conditions["ambient"][0]; state_index=ambient.state_identifiers.index(bc.identifier_1)
    def weather(x,_time,_ids):
        q=np.zeros((nx,1)); q[state_index]=bc.value*(30-x[state_index,0]); return q
    first=simulate_tm(ambient,1/60,x0,60,weather); second=simulate_tm(ambient,1/60,x0,60,weather)
    assert np.isfinite(first.X_full).all() and first.X_full[0,-1]>20
    assert np.max(first.X_full)<=30+1e-10
    np.testing.assert_array_equal(first.X_full,second.X_full)

    _,_,adiabatic=pipeline("adiabatic.idf")
    conserved=simulate_tm(adiabatic,1/60,np.full(2,20.),12,lambda *_:np.zeros((2,1)))
    np.testing.assert_allclose(conserved.X_full,20,atol=1e-12)
    heated=simulate_tm(adiabatic,1/60,np.full(2,20.),12,lambda *_:np.array([[100.],[0.]]))
    assert heated.X_full[0,-1]>20 and np.isfinite(heated.X_full).all()

def test_convenience_api_building_model_and_audit():
    path=FIXTURES/"representative_multizone.idf"
    thermal=brcm.from_energyplus(path)
    building=BuildingModel(thermal,[]); building.discretize(0.25)
    assert building.Ad.shape==(8,8) and building.Bdu.shape==(8,0)
    result=convert_idf_to_brcm_data(path); audit=audit_conversion(result,thermal)
    assert (audit.energyplus_version,audit.zones,audit.surfaces,audit.windows,audit.building_elements,audit.rc_states)==("8.1",2,6,1,6,8)
    assert audit.ignored_object_types==("WindowMaterial:SimpleGlazingSystem",)
    assert len(audit.warnings)==1
