"""Composition and zero-order-hold discretization of the full BRCM model."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
from scipy.linalg import expm

from .ehf import EHFModelBaseClass, EHF_REGISTRY
from .exceptions import ValidationError
from .primitives import Identifier
from .thermal_data import ThermalModelData
from .thermal_generation import generate_thermal_model
from .thermal_model import ThermalModel


@dataclass
class ContinuousModel:
    """Full continuous model; tensor axes are ``Bxu[x,x,u]``, ``Bvu[x,v,u]``."""
    A: np.ndarray
    Bu: np.ndarray
    Bv: np.ndarray
    Bxu: np.ndarray
    Bvu: np.ndarray
    C: np.ndarray
    Du: np.ndarray
    Dv: np.ndarray
    Dxu: np.ndarray
    Dvu: np.ndarray


@dataclass
class DiscreteModel:
    """Zero-order-hold matrices with the same axes as :class:`ContinuousModel`."""
    A: np.ndarray
    Bu: np.ndarray
    Bv: np.ndarray
    Bxu: np.ndarray
    Bvu: np.ndarray
    C: np.ndarray
    Du: np.ndarray
    Dv: np.ndarray
    Dxu: np.ndarray
    Dvu: np.ndarray

    @property
    def Ad(self): return self.A
    @property
    def Bdu(self): return self.Bu
    @property
    def Bdv(self): return self.Bv
    @property
    def Bdxu(self): return self.Bxu
    @property
    def Bdvu(self): return self.Bvu


class BuildingModel:
    """Thermal model plus one or more EHF models in common identifier order.

    Construct directly as ``BuildingModel(thermal_model, ehf_models)`` when a
    thermal model has already been generated.  EHF input (``u``), disturbance
    (``v``), state (``x``), and heat-flux (``q``) identifiers determine matrix
    row order.  Inputs shared by two EHF instances are rejected; repeated
    disturbances are merged and sorted.  Set the sampling time in hours with
    :meth:`set_discretization_step` or :meth:`discretize` before simulation.
    """
    def __init__(self, thermal_submodel: ThermalModel, ehf_submodels: Sequence[EHFModelBaseClass]):
        self.thermal_submodel = thermal_submodel
        self.EHF_submodels = list(ehf_submodels)
        self.identifiers = self._merge_identifiers()
        self.continuous_time_model = self._compose()
        self.discrete_time_model: DiscreteModel | None = None
        self.discrete_sampling_time_hours: float | None = None
        self.Ts_hrs: float | None = None
        self.model_exists = True
        self.is_dirty = False
        self.Fx = self.Fu = self.Fv = self.g = self.cu = None
        self._validate_model(self.continuous_time_model)

    def _merge_identifiers(self) -> Identifier:
        result = Identifier(x=list(self.thermal_submodel.state_identifiers), q=list(self.thermal_submodel.heat_flux_identifiers))
        for model in self.EHF_submodels:
            if model.identifiers.x != result.x or model.identifiers.q != result.q:
                raise ValidationError(f"{model.EHF_identifier} thermal identifiers do not match the ThermalModel")
            repeated_u = sorted(set(result.u).intersection(model.identifiers.u))
            repeated_c = sorted(set(result.constraints).intersection(model.identifiers.constraints))
            if repeated_u: raise ValidationError(f"Duplicate input identifiers are forbidden by MATLAB: {repeated_u}")
            if repeated_c: raise ValidationError(f"Duplicate constraint identifiers: {repeated_c}")
            result.u.extend(model.identifiers.u)
            result.v.extend(model.identifiers.v)
            result.v = sorted(set(result.v))  # MATLAB unique(cellstr) sorts lexically.
            result.constraints.extend(model.identifiers.constraints)
        return result

    def _compose(self) -> ContinuousModel:
        nx, nq, nu, nv, ny = map(len, (self.identifiers.x,self.identifiers.q,self.identifiers.u,self.identifiers.v,self.identifiers.y))
        aq=np.zeros((nq,nx)); bqu=np.zeros((nq,nu)); bqv=np.zeros((nq,nv)); bqxu=np.zeros((nq,nx,nu)); bqvu=np.zeros((nq,nv,nu))
        for model in self.EHF_submodels:
            ai,bui,bvi,bxui,bvui=model.get_prescribed_size_system_matrices(self.identifiers)
            aq+=ai; bqu+=bui; bqv+=bvi; bqxu+=bxui; bqvu+=bvui
        bq=self.thermal_submodel.Bq
        bxu=np.zeros((nx,nx,nu)); bvu=np.zeros((nx,nv,nu))
        for i in range(nu): bxu[:,:,i]=bq@bqxu[:,:,i]; bvu[:,:,i]=bq@bqvu[:,:,i]
        return ContinuousModel(
            self.thermal_submodel.A+bq@aq,bq@bqu,bq@bqv,bxu,bvu,
            np.zeros((ny,nx)),np.zeros((ny,nu)),np.zeros((ny,nv)),np.zeros((ny,nx,nu)),np.zeros((ny,nv,nu)),
        )

    def _validate_model(self, model: ContinuousModel | DiscreteModel) -> None:
        nx,nu,nv,ny=map(len,(self.identifiers.x,self.identifiers.u,self.identifiers.v,self.identifiers.y))
        expected={"A":(nx,nx),"Bu":(nx,nu),"Bv":(nx,nv),"Bxu":(nx,nx,nu),"Bvu":(nx,nv,nu),
                  "C":(ny,nx),"Du":(ny,nu),"Dv":(ny,nv),"Dxu":(ny,nx,nu),"Dvu":(ny,nv,nu)}
        for name,shape in expected.items():
            value=np.asarray(getattr(model,name))
            if value.shape != shape: raise ValidationError(f"{name} shape {value.shape} != {shape}")
            if not np.isfinite(value).all(): raise ValidationError(f"{name} contains NaN or Inf")

    def set_discretization_step(self, sampling_time_hours: float) -> None:
        if isinstance(sampling_time_hours,bool) or not np.isscalar(sampling_time_hours) or not np.isfinite(sampling_time_hours) or sampling_time_hours<=0:
            raise ValidationError("Discretization step must be a positive finite number of hours")
        self.Ts_hrs=float(sampling_time_hours)

    setDiscretizationStep = set_discretization_step

    @staticmethod
    def _zoh(A: np.ndarray, B: np.ndarray, seconds: float) -> tuple[np.ndarray,np.ndarray]:
        """MATLAB solve path, with an augmented-exponential fallback for singular A."""
        ad=expm(A*seconds)
        if B.shape[1] == 0: return ad, np.zeros_like(B)
        try:
            if np.linalg.cond(A) > 1/np.finfo(float).eps: raise np.linalg.LinAlgError
            bd=np.linalg.solve(A,(ad-np.eye(A.shape[0]))@B)
        except np.linalg.LinAlgError:
            # Exact integral exp([[A,B],[0,0]]dt); avoids choosing a nonunique A\ RHS solution.
            n,m=B.shape; augmented=np.zeros((n+m,n+m)); augmented[:n,:n]=A; augmented[:n,n:]=B
            exponential=expm(augmented*seconds); ad=exponential[:n,:n]; bd=exponential[:n,n:]
        return ad,bd

    def discretize(self, sampling_time_hours: float | None = None) -> DiscreteModel:
        if sampling_time_hours is not None: self.set_discretization_step(sampling_time_hours)
        if self.Ts_hrs is None: raise ValidationError("Discretization time step Ts_hrs is not defined")
        c=self.continuous_time_model; nu,nv,nx=len(self.identifiers.u),len(self.identifiers.v),len(self.identifiers.x)
        pieces=[c.Bu,c.Bv]
        for i in range(nu): pieces.extend((c.Bvu[:,:,i],c.Bxu[:,:,i]))
        block=np.concatenate(pieces,axis=1) if pieces else np.zeros((nx,0))
        ad,bd=self._zoh(c.A,block,self.Ts_hrs*3600.0)
        cursor=0; bdu=bd[:,cursor:cursor+nu]; cursor+=nu; bdv=bd[:,cursor:cursor+nv]; cursor+=nv
        bdvu=np.zeros((nx,nv,nu)); bdxu=np.zeros((nx,nx,nu))
        for i in range(nu):
            bdvu[:,:,i]=bd[:,cursor:cursor+nv]; cursor+=nv
            bdxu[:,:,i]=bd[:,cursor:cursor+nx]; cursor+=nx
        self.discrete_time_model=DiscreteModel(ad,bdu,bdv,bdxu,bdvu,c.C.copy(),c.Du.copy(),c.Dv.copy(),c.Dxu.copy(),c.Dvu.copy())
        self.discrete_sampling_time_hours=self.Ts_hrs
        self._validate_model(self.discrete_time_model)
        return self.discrete_time_model

    def get_constraints_matrices(self, parameters: Mapping[str,Mapping[str,Any]]):
        blocks=[]
        for model in self.EHF_submodels:
            local=dict(parameters.get(model.EHF_identifier,{})); local["identifiers_fullModel"]=self.identifiers
            blocks.append(model.get_prescribed_size_constraints_matrices(self.identifiers,local))
        nx,nu,nv=len(self.identifiers.x),len(self.identifiers.u),len(self.identifiers.v)
        fx=np.vstack([b[0] for b in blocks]) if blocks else np.zeros((0,nx)); fu=np.vstack([b[1] for b in blocks]) if blocks else np.zeros((0,nu))
        fv=np.vstack([b[2] for b in blocks]) if blocks else np.zeros((0,nv)); g=np.vstack([b[3] for b in blocks]) if blocks else np.zeros((0,1))
        names=[name for b in blocks for name in b[4]]
        if len(names)!=len(set(names)) or sorted(names)!=sorted(self.identifiers.constraints): raise ValidationError("Constraint identifier assembly is inconsistent")
        permutation=[names.index(name) for name in self.identifiers.constraints]
        self.Fx,self.Fu,self.Fv,self.g=fx[permutation],fu[permutation],fv[permutation],g[permutation]
        return self.Fx,self.Fu,self.Fv,self.g,list(self.identifiers.constraints)

    getConstraintsMatrices = get_constraints_matrices

    def get_cost_vector(self, parameters: Mapping[str,Mapping[str,Any]]) -> np.ndarray:
        if self.Ts_hrs is None: raise ValidationError("Ts_hrs must be set before generating costs")
        result=np.zeros((len(self.identifiers.u),1))
        for model in self.EHF_submodels:
            local=dict(parameters.get(model.EHF_identifier,{})); local["identifiers_fullModel"]=self.identifiers; local["Ts_hrs"]=self.Ts_hrs
            result += model.get_prescribed_size_cost_vector(self.identifiers,local)
        self.cu=result
        return result

    getCostVector = get_cost_vector

    # Direct matrix conveniences requested by the staged API.
    def __getattr__(self, name: str):
        continuous={"A","Bu","Bv","Bxu","Bvu","C","Du","Dv","Dxu","Dvu"}
        discrete={"Ad":"A","Bdu":"Bu","Bdv":"Bv","Bdxu":"Bxu","Bdvu":"Bvu"}
        if name in continuous: return getattr(self.continuous_time_model,name)
        if name in discrete:
            if self.discrete_time_model is None: raise AttributeError(f"{name} unavailable before discretize()")
            return getattr(self.discrete_time_model,discrete[name])
        raise AttributeError(name)


def compose_building_model(thermal_model: ThermalModel, ehf_models: Sequence[EHFModelBaseClass]) -> BuildingModel:
    return BuildingModel(thermal_model,ehf_models)


def generate_building_model(data: ThermalModelData, declarations: Sequence[tuple[str,str,str|Path]], sampling_time_hours: float | None=None) -> BuildingModel:
    """Generate thermal and declared EHF models without dynamic dispatch.

    Each declaration is ``(registry_name, EHF_identifier, source_file)`` where
    ``registry_name`` is one of ``InternalGains``, ``Radiators``,
    ``BEHeatfluxes``, ``BuildingHull``, or ``AHU``.  This convenience function
    generates a new ThermalModel; use :class:`BuildingModel` directly to retain
    an already-generated instance.
    """
    thermal=generate_thermal_model(data); models=[]
    for class_name,identifier,source in declarations:
        try: cls=EHF_REGISTRY[class_name]
        except KeyError as error: raise ValidationError(f"Unknown EHF model class {class_name!r}") from error
        models.append(cls(data,thermal,identifier,source))
    result=BuildingModel(thermal,models)
    if sampling_time_hours is not None: result.discretize(sampling_time_hours)
    return result


generateBuildingModel = generate_building_model
