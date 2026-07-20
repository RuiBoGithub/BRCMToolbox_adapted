"""Generate the seven Stage 2 tables using MATLAB EP2BRCM identifiers."""
from __future__ import annotations
import re
from .geometry import polygon_area
from .records import NormalizedEnergyPlusModel
from ..constants import Constants,matlab_number
from ..exceptions import ValidationError

def _s(value): return matlab_number(value) if isinstance(value,(int,float)) else str(value)
def _area(surface): return surface.area if surface.area is not None else polygon_area(surface.vertices)
def _conv(surface,side):
    types={'wall':('Wall','Wall'),'floor':('Ceiling','Floor'),'ceiling':('Floor','Ceiling'),'roof':('Roof','Ceiling')}
    try: type_a,type_b=types[surface.surface_type.casefold()]
    except KeyError as error: raise ValidationError(f"Unknown surface type {surface.surface_type!r}") from error
    if side=='B': return f"convCoeff_{type_b}Int"
    boundary=surface.outside_boundary.casefold()
    suffix={'outdoors':'Ext','surface':'Int','zone':'Int','adiabatic':'ADB','ground':'GND'}.get(boundary)
    if boundary=='othersidecoefficients':
        match=re.search(r'\[([^]]+)\]',surface.outside_object); coefficient=float(match.group(1)) if match else 0
        encoded=format(max(coefficient,0),'.10g').replace('.','p'); suffix=f"{'TBCwFC' if coefficient>0 else 'TBCwoFC'}_FilmCoeff_{encoded}"
    if suffix is None: raise ValidationError(f"Unsupported boundary {surface.outside_boundary}")
    return f"convCoeff_{type_a}{suffix}"

def _parameter(identifier):
    if identifier=='UValue_IRTransparent': return ('UValue of Infrared Partition (usually used to model two parts of the same room)','100')
    if identifier=='convCoeff_UNKNOWN': return ('Convective coefficient of unknown surface (corresponding construction unused in building elements)','0')
    if identifier=='convCoeff_InternalMass': return ('Convective Coefficient of Internal Mass (default, considering thermal radiation)','6')
    if identifier.startswith('UValue_Window_EPConstr_'): return ('UValue of Window with EP Construction'+identifier.split('UValue_Window_EPConstr_',1)[1]+' (default value)','1')
    if identifier.startswith('GValue_Window_EPConstr_'): return ('GValue of Window with EP Construction'+identifier.split('GValue_Window_EPConstr_',1)[1]+' (default value)','0.5')
    if 'ADB' in identifier: return ('Convective coefficient of a ground contact surface (unused, set to 0)','0')
    if 'GND' in identifier: return ('Convective coefficient of a adiabatic surface (unused, set to 0)','0')
    if 'TBCwFC' in identifier:
        match=re.search(r'FilmCoeff_(.+)',identifier); return ('Convective coefficient of OtherSideCoefficients boundary condition',str(float(match.group(1).replace('p','.'))))
    if 'TBCwoFC' in identifier: return ('Convective coefficient of OtherSideCoefficients boundary condition (unused, set to 0)','0')
    if identifier.endswith('Ext'): return ('Convective coefficient of a surface to ambient air (default)','12.5')
    defaults={'CeilingInt':8,'RoofInt':8,'FloorInt':5,'WallInt':7}
    for ending,value in defaults.items():
        if identifier.endswith(ending): return (f'Convective coefficient of {ending} (default, considering thermal radiation)',str(value))
    return ('empty_description','NaN')

def generate_brcm_tables(model: NormalizedEnergyPlusModel) -> dict[str,list[list[str]]]:
    tables={name:[list(header)] for name,header in Constants.TABLE_SCHEMAS.items()}
    zone_map={}
    for i,zone in enumerate(model.zones,1):
        walls=[s for s in model.surfaces if s.zone.casefold()==zone.name.casefold() and s.surface_type.casefold()=='wall']
        floors=[s for s in model.surfaces if s.zone.casefold()==zone.name.casefold() and s.surface_type.casefold()=='floor']
        height=zone.height if zone.height else (sum(max(p[2] for p in s.vertices)-min(p[2] for p in s.vertices) for s in walls)/len(walls) if walls else None)
        area=zone.area if zone.area else (sum(_area(s) for s in floors) if floors else None)
        volume=zone.volume if zone.volume else (height*area if height and area else None)
        if area is None or volume is None: raise ValidationError(f"Cannot determine area/volume for zone {zone.name!r}")
        zid=f"Z{i:04d}"; zone_map[zone.name.casefold()]=zid; tables['zones'].append([zid,zone.name,_s(area),_s(volume),''])
    material_map={}
    for material in model.materials:
        if material.kind=='Material:InfraredTransparent': continue
        mid=f"M{len(tables['materials']):04d}"; material_map[material.name.casefold()]=mid
        if material.kind=='Material': row=[mid,material.name,_s(material.specific_heat),_s(1/material.conductivity),_s(material.density),'']
        else: row=[mid,material.name,'','','',_s(material.resistance)]
        tables['materials'].append(row)
    surface_construction={}; internal_construction={}; required=[]
    materials={m.name.casefold():m for m in model.materials}
    for construction in model.constructions:
        uses=[s for s in model.surfaces if s.construction.casefold()==construction.name.casefold()]
        internal_uses=[im for im in model.internal_masses if im.construction.casefold()==construction.name.casefold()]
        # Window-only constructions are represented by the windows table and
        # may legitimately reference glazing objects ignored by this RC layer.
        if not uses and not internal_uses: continue
        layers=[]
        for name in construction.layers:
            material=materials.get(name.casefold())
            if material is None: raise ValidationError(f"Construction {construction.name!r} references unknown material {name!r}")
            layers.append(material)
        if layers and all(m.kind=='Material:InfraredTransparent' for m in layers):
            nid=f"NMC{len(tables['nomassconstructions']):04d}"; tables['nomassconstructions'].append([nid,construction.name,'UValue_IRTransparent']); required.append('UValue_IRTransparent')
            for s in model.surfaces:
                if s.construction.casefold()==construction.name.casefold(): surface_construction[s.name.casefold()]=nid
            continue
        usable=[m for m in layers if m.kind!='Material:InfraredTransparent']
        if not usable: continue
        mids=','.join(material_map[m.name.casefold()] for m in usable); thickness=','.join(_s(m.thickness if m.kind=='Material' else 0) for m in usable)
        pairs=sorted({(_conv(s,'A'),_conv(s,'B')) for s in uses}) or [('convCoeff_UNKNOWN','convCoeff_UNKNOWN')]
        for ca,cb in pairs:
            cid=f"C{len(tables['constructions']):04d}"; tables['constructions'].append([cid,construction.name,mids,thickness,ca,cb]); required.extend((ca,cb))
            for s in uses:
                if (_conv(s,'A'),_conv(s,'B'))==(ca,cb): surface_construction[s.name.casefold()]=cid
        if internal_uses:
            cid=f"C{len(tables['constructions']):04d}"; tables['constructions'].append([cid,construction.name,mids,thickness,'convCoeff_InternalMass','convCoeff_InternalMass']); required.extend(('convCoeff_InternalMass','convCoeff_InternalMass'))
            for im in model.internal_masses:
                if im.construction.casefold()==construction.name.casefold(): internal_construction[im.name.casefold()]=cid
    # MATLAB groups windows by concatenated parent surface + construction and sorts groups.
    window_map={}; window_groups={}
    for window in model.windows: window_groups.setdefault((window.parent_surface+window.construction).casefold(),[]).append(window)
    for key in sorted(window_groups):
        windows=window_groups[key]; first=windows[0]; cleaned=re.sub('[^a-zA-Z0-9]','',first.construction); wid=f"W{len(tables['windows']):04d}"
        glass=sum(w.glass_area if w.glass_area is not None else polygon_area(w.vertices) for w in windows); frame=sum(w.frame_area for w in windows); u=f"UValue_Window_EPConstr_{cleaned}"; g=f"GValue_Window_EPConstr_{cleaned}"
        tables['windows'].append([wid,f"EP Surface:{first.parent_surface}/EP Construction:{first.construction}",_s(glass),_s(frame),u,g]); required.extend((u,g)); window_map[first.parent_surface.casefold()]=wid
    merged=set(); surfaces_by_name={s.name.casefold():s for s in model.surfaces}
    for surface in model.surfaces:
        if surface.name.casefold() in merged: continue
        boundary=surface.outside_boundary.casefold(); description='EP Surface Names:'+surface.name
        if boundary=='outdoors': adjacent_a='AMB'
        elif boundary=='ground': adjacent_a='GND'
        elif boundary=='adiabatic' or surface.outside_object.casefold()==surface.name.casefold(): adjacent_a='ADB'
        elif boundary=='zone': adjacent_a=zone_map.get(surface.outside_object.casefold())
        elif boundary=='surface':
            other=surfaces_by_name.get(surface.outside_object.casefold())
            if other is None: raise ValidationError(f"Unknown adjacent surface {surface.outside_object!r}")
            adjacent_a=zone_map[other.zone.casefold()]; merged.add(other.name.casefold()); description+=','+other.name
        elif boundary=='othersidecoefficients':
            coefficient=float(re.search(r'\[([^]]+)\]',surface.outside_object).group(1)); name=surface.outside_object.split(';',1)[0]; adjacent_a=('TBCwFC' if coefficient>0 else 'TBCwoFC')+name
        else: raise ValidationError(f"Unsupported boundary {surface.outside_boundary}")
        if adjacent_a is None: raise ValidationError(f"Unknown adjacent zone {surface.outside_object}")
        adjacent_b=zone_map[surface.zone.casefold()]; construction=surface_construction.get(surface.name.casefold())
        if construction is None: raise ValidationError(f"No converted construction for surface {surface.name}")
        vertices=','.join(f"({_s(x)},{_s(y)},{_s(z)})" for x,y,z in surface.vertices)
        bid=f"B{len(tables['buildingelements']):04d}"; tables['buildingelements'].append([bid,description,construction,adjacent_a,adjacent_b,window_map.get(surface.name.casefold(),''),_s(_area(surface)),vertices])
    for im in model.internal_masses:
        cid=internal_construction.get(im.name.casefold())
        if cid is None: raise ValidationError(f"No converted construction for internal mass {im.name}")
        bid=f"B{len(tables['buildingelements']):04d}"; zid=zone_map[im.zone.casefold()]
        tables['buildingelements'].append([bid,im.name,cid,zid,zid,'',_s(im.area/2),''])
    for identifier in sorted(set(required)):
        description,value=_parameter(identifier); tables['parameters'].append([identifier,description,value])
    return tables

genZoneSheet=lambda model:generate_brcm_tables(model)['zones']
genMaterialSheet=lambda model:generate_brcm_tables(model)['materials']
genConstructionAndNoMassConstructionSheet=lambda model:(generate_brcm_tables(model)['constructions'],generate_brcm_tables(model)['nomassconstructions'])
genWindowSheet=lambda model:generate_brcm_tables(model)['windows']
genBuildingElementSheet=lambda model:generate_brcm_tables(model)['buildingelements']
genParameterSheet=lambda model:generate_brcm_tables(model)['parameters']
