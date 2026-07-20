from __future__ import annotations
import math
import numpy as np
from ..exceptions import ValidationError

def polygon_area(vertices):
    points=np.asarray(vertices,dtype=float)
    if points.shape[0]<3 or points.shape[1]!=3: raise ValidationError("A surface requires at least three 3-D vertices")
    total=np.zeros(3)
    for a,b in zip(points,np.roll(points,-1,axis=0)): total+=np.cross(a,b)
    return float(np.linalg.norm(total)/2)

def to_world(vertices,origin=(0,0,0),north_degrees=0,coordinate_system="World"):
    points=np.asarray(vertices,dtype=float)
    normalized=coordinate_system.casefold().replace('coordinatesystem','')
    if normalized in ('world','absolute'): return tuple(map(tuple,points))
    if normalized!='relative': raise ValidationError(f"Unknown coordinate system {coordinate_system!r}")
    angle=math.radians(north_degrees); c,s=math.cos(angle),math.sin(angle); rotation=np.array([[c,-s,0],[s,c,0],[0,0,1.]])
    return tuple(map(tuple,(points@rotation.T+np.asarray(origin))))
