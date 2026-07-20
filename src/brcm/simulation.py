"""MATLAB-compatible thermal and bilinear building simulation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np

from .building_model import BuildingModel
from .exceptions import ValidationError
from .primitives import Identifier
from .thermal_model import ThermalModel


@dataclass(frozen=True)
class ThermalSimulationResult:
    X: np.ndarray          # MATLAB return: states at t[0] ... t[N-1]
    X_full: np.ndarray     # Python completeness: includes post-input state at t[N]
    Q: np.ndarray
    t_hrs: np.ndarray


@dataclass(frozen=True)
class BuildingSimulationResult:
    X: np.ndarray
    X_full: np.ndarray
    U: np.ndarray
    V: np.ndarray
    Y: np.ndarray
    t_hrs: np.ndarray


def _finite_matrix(value, shape: tuple[int, int], name: str) -> np.ndarray:
    array=np.asarray(value,dtype=float)
    if array.shape != shape: raise ValidationError(f"{name} must have shape {shape}, got {array.shape}; inputs are not transposed implicitly")
    if not np.isfinite(array).all(): raise ValidationError(f"{name} contains NaN or Inf")
    return array


def _column(value, length: int, name: str) -> np.ndarray:
    array=np.asarray(value,dtype=float)
    if array.shape == (length,): array=array.reshape(length,1)  # documented Python convenience
    if array.shape != (length,1): raise ValidationError(f"{name} must be a column vector with shape ({length}, 1)")
    if not np.isfinite(array).all(): raise ValidationError(f"{name} contains NaN or Inf")
    return array


def _thermal_discrete(model: ThermalModel, sampling_time_hours: float):
    if not np.isfinite(sampling_time_hours) or sampling_time_hours<=0: raise ValidationError("Sampling time must be positive finite hours")
    # Reuse Stage 5's MATLAB solve plus exact singular fallback.
    return BuildingModel._zoh(model.A,model.Bq,float(sampling_time_hours)*3600)


def simulate_tm(model: ThermalModel, sampling_time_hours: float, x0, n_steps: int, generator: Callable):
    """Low-level thermal engine; callback is ``q = f(x_column,t_hours,identifiers)``."""
    if not isinstance(n_steps,(int,np.integer)) or isinstance(n_steps,bool) or n_steps<=0: raise ValidationError("Number of simulation steps must be a positive integer")
    nx,nq=len(model.state_identifiers),len(model.heat_flux_identifiers); state=_column(x0,nx,"x0")
    ad,bd=_thermal_discrete(model,sampling_time_hours); times=np.arange(n_steps,dtype=float)*sampling_time_hours
    full=np.empty((nx,n_steps+1)); full[:,0]=state[:,0]; q_values=np.empty((nq,n_steps)); ids=Identifier(x=list(model.state_identifiers),q=list(model.heat_flux_identifiers))
    for k,time in enumerate(times):
        q=_column(generator(state.copy(),float(time),ids),nq,"callback q")
        q_values[:,k]=q[:,0]; state=ad@state+bd@q; full[:,k+1]=state[:,0]
    return ThermalSimulationResult(full[:,:-1].copy(),full,q_values,times.reshape(1,-1))


def simulate_bm(model: BuildingModel, x0, n_steps: int, generator: Callable):
    """Low-level full engine; callback is ``(u,v) = f(x_column,t_hours,identifiers)``."""
    if model.Ts_hrs is None: raise ValidationError("BuildingModel sampling time is not set")
    if not isinstance(n_steps,(int,np.integer)) or isinstance(n_steps,bool) or n_steps<=0: raise ValidationError("Number of simulation steps must be a positive integer")
    if model.discrete_time_model is None: model.discretize()
    elif model.discrete_sampling_time_hours != model.Ts_hrs:
        raise ValidationError("Discrete model sampling time does not match BuildingModel Ts_hrs")
    md=model.discrete_time_model; nx,nu,nv,ny=map(len,(model.identifiers.x,model.identifiers.u,model.identifiers.v,model.identifiers.y))
    state=_column(x0,nx,"x0"); times=np.arange(n_steps,dtype=float)*model.Ts_hrs
    full=np.empty((nx,n_steps+1)); full[:,0]=state[:,0]; U=np.empty((nu,n_steps)); V=np.empty((nv,n_steps)); Y=np.empty((ny,n_steps))
    for k,time in enumerate(times):
        returned=generator(state.copy(),float(time),model.identifiers)
        if not isinstance(returned,(tuple,list)) or len(returned)!=2: raise ValidationError("Building callback must return (u, v)")
        u=_column(returned[0],nu,"callback u"); v=_column(returned[1],nv,"callback v")
        U[:,k]=u[:,0]; V[:,k]=v[:,0]
        y=md.C@state+md.Du@u+md.Dv@v
        next_state=md.A@state+md.Bu@u+md.Bv@v
        for i in range(nu):
            y += (md.Dvu[:,:,i]@v+md.Dxu[:,:,i]@state)*u[i,0]
            next_state += (md.Bvu[:,:,i]@v+md.Bxu[:,:,i]@state)*u[i,0]
        if not np.isfinite(next_state).all() or not np.isfinite(y).all(): raise ValidationError(f"Simulation produced NaN or Inf at step {k}")
        Y[:,k]=y[:,0]; state=next_state; full[:,k+1]=state[:,0]
    return BuildingSimulationResult(full[:,:-1].copy(),full,U,V,Y,times.reshape(1,-1))


class SimulationExperiment:
    """Stateful wrapper preserving the two MATLAB simulation modes."""
    INPUT_TRAJECTORY="inputTrajectory"; HANDLE="handle"
    def __init__(self, building_model: BuildingModel):
        if not isinstance(building_model,BuildingModel): raise ValidationError("SimulationExperiment requires a BuildingModel")
        if building_model.Ts_hrs is None: raise ValidationError("BuildingModel must have a sampling time")
        self.building_model=building_model; self.Ts_hrs=building_model.Ts_hrs; self.n_simulation_time_steps=None; self.x0=None
        self.X=self.X_full=self.Q=self.U=self.V=self.Y=self.t_hrs=None

    def set_number_of_simulation_time_steps(self,n_steps: int):
        if not isinstance(n_steps,(int,np.integer)) or isinstance(n_steps,bool) or n_steps<=0: raise ValidationError("Number of steps must be a positive integer")
        self.n_simulation_time_steps=int(n_steps)
    setNumberOfSimulationTimeSteps=set_number_of_simulation_time_steps

    def set_initial_state(self,x0): self.x0=_column(x0,len(self.building_model.identifiers.x),"x0")
    setInitialState=set_initial_state
    def get_identifiers(self): return self.building_model.identifiers
    getIdentifiers=get_identifiers
    def get_sampling_time(self): return self.Ts_hrs
    getSamplingTime=get_sampling_time

    def _requirements(self):
        if self.n_simulation_time_steps is None: raise ValidationError("n_simulation_time_steps has not been set")
        if self.x0 is None: raise ValidationError("x0 has not been set")

    def simulate_thermal_model(self,sim_mode: str,*args):
        self._requirements(); n=self.n_simulation_time_steps; thermal=self.building_model.thermal_submodel
        if sim_mode.lower()==self.INPUT_TRAJECTORY.lower() and len(args)==1:
            q=_finite_matrix(args[0],(len(thermal.heat_flux_identifiers),n),"Q")
            generator=lambda _x,t,_ids:q[:,int(round(t/self.Ts_hrs))].reshape(-1,1)
        elif sim_mode.lower()==self.HANDLE and len(args)==1 and callable(args[0]): generator=args[0]
        else: raise ValidationError("Supported thermal modes are 'inputTrajectory' and 'handle'")
        result=simulate_tm(thermal,self.Ts_hrs,self.x0,n,generator)
        self.X,self.X_full,self.Q,self.t_hrs=result.X,result.X_full,result.Q,result.t_hrs
        return self.X,self.Q,self.t_hrs
    simulateThermalModel=simulate_thermal_model

    def simulate_building_model(self,sim_mode: str,*args):
        self._requirements(); n=self.n_simulation_time_steps; nu,nv=len(self.building_model.identifiers.u),len(self.building_model.identifiers.v)
        if sim_mode.lower()==self.INPUT_TRAJECTORY.lower() and len(args)==2:
            U=_finite_matrix(args[0],(nu,n),"U"); V=_finite_matrix(args[1],(nv,n),"V")
            def generator(_x,t,_ids):
                k=int(round(t/self.Ts_hrs)); return U[:,k].reshape(-1,1),V[:,k].reshape(-1,1)
        elif sim_mode.lower()==self.HANDLE and len(args)==1 and callable(args[0]): generator=args[0]
        else: raise ValidationError("Supported building modes are 'inputTrajectory' and 'handle'")
        result=simulate_bm(self.building_model,self.x0,n,generator)
        self.X,self.X_full,self.U,self.V,self.Y,self.t_hrs=result.X,result.X_full,result.U,result.V,result.Y,result.t_hrs
        return self.X,self.U,self.V,self.t_hrs
    simulateBuildingModel=simulate_building_model


simulateTM=simulate_tm
simulateBM=simulate_bm


def simulate_thermal_model(model,sampling_time_hours,x0,Q):
    Q=np.asarray(Q,dtype=float); n=Q.shape[1] if Q.ndim==2 else 0
    return simulate_tm(model,sampling_time_hours,x0,n,lambda _x,t,_ids:Q[:,int(round(t/sampling_time_hours))])


def simulate_building_model(model,x0,U,V):
    U=np.asarray(U,dtype=float); V=np.asarray(V,dtype=float); n=U.shape[1] if U.ndim==2 else 0
    if V.ndim!=2 or V.shape[1]!=n: raise ValidationError("U and V horizons must match")
    return simulate_bm(model,x0,n,lambda _x,t,_ids:(U[:,int(round(t/model.Ts_hrs))],V[:,int(round(t/model.Ts_hrs))]))
