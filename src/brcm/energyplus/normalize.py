"""Normalize the explicitly supported legacy EnergyPlus thermal subset."""
from __future__ import annotations
import warnings
from .geometry import to_world
from .records import *
from ..exceptions import ValidationError

SUPPORTED_OBJECT_TYPES=(
 "Version","GlobalGeometryRules","Zone","Material","Material:NoMass","Material:AirGap","Material:InfraredTransparent",
 "Construction","Construction:InternalSource","InternalMass","BuildingSurface:Detailed","FenestrationSurface:Detailed",
 "WindowProperty:FrameAndDivider","SurfaceProperty:OtherSideCoefficients",
 "Wall:Exterior","Wall:Adiabatic","Wall:Underground","Wall:Interzone","Wall:Detailed","Roof","Ceiling:Adiabatic",
 "Ceiling:Interzone","Floor:GroundContact","Floor:Adiabatic","Floor:Interzone","Floor:Detailed","RoofCeiling:Detailed","Window",
)

def _num(value,default=None):
    if value is None or not str(value).strip() or str(value).casefold()=='autocalculate': return default
    try: return float(value)
    except ValueError as error: raise ValidationError(f"Expected numeric EnergyPlus value, got {value!r}") from error
def _at(o,n,default=''): return o.values[n].strip() if n<len(o.values) else default
def _field(o,name,index=None,default=''):
    value=o.field(name,default)
    return value if value!=default or index is None else _at(o,index,default)

def normalize_idf_objects(objects: list[IDFObject]) -> NormalizedEnergyPlusModel:
    version=next((_at(o,0) for o in objects if o.object_type.casefold()=='version'),None)
    if not version: raise ValidationError("Version object is required")
    rules=next((o for o in objects if o.object_type.casefold()=='globalgeometryrules'),None)
    coordinate=_at(rules,2,'Relative') if rules else 'Relative'
    model=NormalizedEnergyPlusModel(version,coordinate,raw_objects=list(objects)); by_type={}
    for o in objects: by_type.setdefault(o.object_type.casefold(),[]).append(o)
    for o in by_type.get('zone',[]):
        multiplier=_num(_at(o,6),1)
        if multiplier!=1: raise ValidationError("Zone multipliers other than one are unsupported")
        model.zones.append(EPZone(_at(o,0),_num(_at(o,1),0),(_num(_at(o,2),0),_num(_at(o,3),0),_num(_at(o,4),0)),_num(_at(o,7)),_num(_at(o,8)),_num(_at(o,9))))
    zone_map={z.name.casefold():z for z in model.zones}
    for kind in ('material','material:nomass','material:airgap','material:infraredtransparent'):
        for o in by_type.get(kind,[]):
            if kind=='material': model.materials.append(EPMaterial(_at(o,0),'Material',_num(_at(o,2)),_num(_at(o,3)),_num(_at(o,4)),_num(_at(o,5))))
            elif kind=='material:nomass': model.materials.append(EPMaterial(_at(o,0),'Material:NoMass',resistance=_num(_at(o,2))))
            elif kind=='material:airgap': model.materials.append(EPMaterial(_at(o,0),'Material:AirGap',resistance=_num(_at(o,1))))
            else: model.materials.append(EPMaterial(_at(o,0),'Material:InfraredTransparent'))
    for kind in ('construction','construction:internalsource'):
        for o in by_type.get(kind,[]):
            layers=list(o.values[1:] if kind=='construction' else o.values[5:]); layers=[x for x in layers if x]
            model.constructions.append(EPConstruction(_at(o,0),layers))
    def vertices(o,base,count_index,zone_name):
        count=int(_num(_at(o,count_index),0)); raw=o.values[base:base+3*count]
        if count<3 or len(raw)!=3*count: raise ValidationError(f"Malformed vertices for {_at(o,0)}")
        local=tuple(tuple(float(raw[3*i+j]) for j in range(3)) for i in range(count)); zone=zone_map.get(zone_name.casefold())
        if zone is None: raise ValidationError(f"Unknown zone {zone_name!r}")
        return to_world(local,zone.origin,zone.north,coordinate)
    for o in by_type.get('buildingsurface:detailed',[]):
        boundary=_at(o,4); outside=_at(o,5); allowed=('adiabatic','surface','zone','outdoors','ground','othersidecoefficients')
        if boundary.casefold() not in allowed: raise ValidationError(f"Unsupported outside boundary {boundary!r}")
        if boundary.casefold()=='othersidecoefficients':
            osc=next((x for x in by_type.get('surfaceproperty:othersidecoefficients',[]) if _at(x,0).casefold()==outside.casefold()),None)
            if osc is None: raise ValidationError(f"Unknown OtherSideCoefficients {outside!r}")
            coefficient=_num(_field(osc,'Combined Convective/Radiative Film Coefficient',1)); outside=f"{outside};Combined Convective/Radiative Film Coefficient[{coefficient:g}]"
        model.surfaces.append(EPSurface(_at(o,0),_at(o,1),_at(o,2),_at(o,3),boundary,outside,vertices(o,10,9,_at(o,3))))
    frames={_at(o,0).casefold():_num(_at(o,1),0) for o in by_type.get('windowproperty:frameanddivider',[])}
    parent_map={s.name.casefold():s for s in model.surfaces}
    for o in by_type.get('fenestrationsurface:detailed',[]):
        if _at(o,1).casefold()!='window': continue
        parent=parent_map.get(_at(o,3).casefold())
        if parent is None: raise ValidationError(f"Unknown fenestration parent {_at(o,3)!r}")
        verts=vertices(o,9,8,parent.zone); multiplier=_num(_at(o,7),1); frame=frames.get(_at(o,6).casefold(),0)
        area_points=list(verts); zs=[p[2] for p in area_points]; height=max(zs)-min(zs); from .geometry import polygon_area
        area=polygon_area(verts); width=area/height if height else 0; frame_area=(frame*2*(height+width)+4*frame**2)*multiplier
        model.windows.append(EPWindow(_at(o,0),_at(o,2),parent.name,verts,frame_area,area*multiplier))
    for o in by_type.get('internalmass',[]): model.internal_masses.append(EPInternalMass(_at(o,0),_at(o,1),_at(o,2),_num(_at(o,3))))
    legacy={
      'wall:exterior':('Wall','Outdoors'),'wall:adiabatic':('Wall','Adiabatic'),'wall:underground':('Wall','Ground'),'wall:interzone':('Wall','Surface'),
      'roof':('Roof','Outdoors'),'ceiling:adiabatic':('Ceiling','Adiabatic'),'ceiling:interzone':('Ceiling','Surface'),
      'floor:groundcontact':('Floor','Ground'),'floor:adiabatic':('Floor','Adiabatic'),'floor:interzone':('Floor','Surface'),
    }
    for kind,(surface_type,boundary) in legacy.items():
        for o in by_type.get(kind,[]):
            length=_num(_field(o,'Length'),None); dimension=_num(_field(o,'Height'),None)
            if dimension is None: dimension=_num(_field(o,'Width'),None)
            if length is None or dimension is None: raise ValidationError(f"Cannot determine area for legacy surface {_at(o,0)!r}")
            outside=_field(o,'Outside Boundary Condition Object') or _field(o,'Outside Boundary Condition')
            model.surfaces.append(EPSurface(_field(o,'Name',0),surface_type,_field(o,'Construction Name',1),_field(o,'Zone Name',2),boundary,outside,area=length*dimension))
    for kind,surface_type in (('wall:detailed','Wall'),('floor:detailed','Floor'),('roofceiling:detailed','Roof')):
        for o in by_type.get(kind,[]):
            count=int(_num(_field(o,'Number of Vertices'),0)); base=next((i for i,n in enumerate(o.field_names) if n.casefold().startswith('vertex 1 x-')),9)
            raw=o.values[base:base+3*count]
            if count<3 or len(raw)!=3*count: raise ValidationError(f"Malformed vertices for {_at(o,0)}")
            zone=_field(o,'Zone Name',2); local=tuple(tuple(float(raw[3*i+j]) for j in range(3)) for i in range(count)); z=zone_map.get(zone.casefold())
            if z is None: raise ValidationError(f"Unknown zone {zone!r}")
            verts=to_world(local,z.origin,z.north,coordinate)
            model.surfaces.append(EPSurface(_field(o,'Name',0),surface_type,_field(o,'Construction Name',1),zone,_field(o,'Outside Boundary Condition',3),_field(o,'Outside Boundary Condition Object',4),verts))
    # The old Window object contributes only areas; its coordinates are relative
    # to the parent and were not retained by MATLAB's normalized record.
    for o in by_type.get('window',[]):
        multiplier=_num(_field(o,'Multiplier'),1); height=_num(_field(o,'Height')); length=_num(_field(o,'Length'))
        parent=_field(o,'Building Surface Name',2); frame_name=_field(o,'Frame and Divider Name')
        frame=frames.get(frame_name.casefold(),0); frame_area=(frame*2*(height+length)+4*frame**2)*multiplier if frame_name else 0
        model.windows.append(EPWindow(_field(o,'Name',0),_field(o,'Construction Name',1),parent,(),frame_area,height*length*multiplier))
    thermal_prefixes=('material','construction','zone','buildingsurface','fenestrationsurface','wall:','floor:','ceiling:','roof','internalmass','window')
    known={x.casefold() for x in SUPPORTED_OBJECT_TYPES}|{'building','timestep','simulationcontrol','runperiod'}
    ignored_prefixes=('windowmaterial:','windowproperty:','shading:','materialproperty:')
    ignored=sorted({o.object_type for o in objects if o.object_type.casefold().startswith(ignored_prefixes) and o.object_type.casefold() not in known})
    model.ignored_object_types=tuple(ignored)
    if ignored: warnings.warn(f"Ignoring MATLAB-unsupported EnergyPlus objects: {ignored}",UserWarning,stacklevel=2)
    unsupported=sorted({o.object_type for o in objects if o.object_type.casefold().startswith(thermal_prefixes) and o.object_type.casefold() not in known and not o.object_type.casefold().startswith(ignored_prefixes)})
    if unsupported: raise ValidationError(f"Unsupported thermal EnergyPlus objects: {unsupported}")
    return model

convertIDFObjects=normalize_idf_objects
