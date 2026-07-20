from __future__ import annotations

import numpy as np
import pytest

from brcm import (
    AHU, BEHeatfluxes, BuildingHull, BuildingModel, ContinuousModel, DiscreteModel,
    InternalGains, Radiators, SimulationExperiment, ThermalModel,
    ThermalModelData, compose_building_model, generate_thermal_model,
    simulate_bm, simulate_building_model, simulate_thermal_model,
)
from brcm.exceptions import ValidationError


def thermal(A,B):
    A=np.atleast_2d(np.asarray(A,dtype=float)); B=np.atleast_2d(np.asarray(B,dtype=float)); n=A.shape[0]
    return ThermalModel(A,B,np.eye(n),[f"x_Z{i+1:04d}" for i in range(n)],[f"q_Z{i+1:04d}" for i in range(B.shape[1])])


def empty_building(nx=1,nu=0,nv=0):
    t=thermal(-np.eye(nx),np.eye(nx)); model=compose_building_model(t,[])
    model.identifiers.u=[f"u_{i}" for i in range(nu)]; model.identifiers.v=[f"v_{i}" for i in range(nv)]
    z=lambda *shape:np.zeros(shape)
    model.continuous_time_model=ContinuousModel(-np.eye(nx),z(nx,nu),z(nx,nv),z(nx,nx,nu),z(nx,nv,nu),z(0,nx),z(0,nu),z(0,nv),z(0,nx,nu),z(0,nv,nu))
    model.set_discretization_step(1/3600)
    return model


def test_scalar_thermal_decay_and_initial_state_convention():
    result=simulate_thermal_model(thermal([[-1]],[[1]]),1/3600,[2],np.zeros((1,3)))
    np.testing.assert_allclose(result.X,[[2,2/np.e,2/np.e**2]])
    np.testing.assert_allclose(result.X_full[0,-1],2/np.e**3)
    assert result.X.shape==(1,3) and result.X_full.shape==(1,4)
    np.testing.assert_array_equal(result.X[:,0],[2])


def test_constant_heat_flux_scalar_analytic_solution():
    result=simulate_thermal_model(thermal([[-2]],[[1]]),1/3600,[0],np.full((1,4),3.))
    expected=[1.5*(1-np.exp(-2*k)) for k in range(5)]
    np.testing.assert_allclose(result.X_full[0],expected)


def test_multistate_thermal_and_wrong_q_orientation():
    model=thermal([[-1,0],[0,-2]],np.eye(2)); q=np.array([[1,2],[3,4.]])
    result=simulate_thermal_model(model,1/3600,[0,0],q)
    assert result.X_full.shape==(2,3) and np.isfinite(result.X_full).all()
    with pytest.raises(ValidationError,match="shape"): simulate_thermal_model(model,1/3600,[0,0],q.T[:1])


def test_linear_building_one_step_manual_calculation():
    model=empty_building(1,1,1); z=lambda *s:np.zeros(s)
    model.discrete_time_model=DiscreteModel(np.array([[.5]]),np.array([[2.]]),np.array([[3.]]),z(1,1,1),z(1,1,1),z(0,1),z(0,1),z(0,1),z(0,1,1),z(0,1,1))
    model.discrete_sampling_time_hours=model.Ts_hrs
    result=simulate_building_model(model,[4],np.array([[5.]]),np.array([[6.]]))
    assert result.X_full[0,1] == .5*4+2*5+3*6


def test_state_and_disturbance_bilinear_terms_term_by_term():
    model=empty_building(1,1,1); z=lambda *s:np.zeros(s)
    bxu=np.array([[[7.]]]); bvu=np.array([[[11.]]])
    model.discrete_time_model=DiscreteModel(np.array([[2.]]),np.array([[3.]]),np.array([[5.]]),bxu,bvu,z(0,1),z(0,1),z(0,1),z(0,1,1),z(0,1,1))
    model.discrete_sampling_time_hours=model.Ts_hrs
    x,u,v=13.,17.,19.; result=simulate_building_model(model,[x],np.array([[u]]),np.array([[v]]))
    linear=2*x+3*u+5*v; state_bilinear=7*x*u; disturbance_bilinear=11*v*u
    assert result.X_full[0,1] == linear+state_bilinear+disturbance_bilinear


def test_multistep_reference_and_zero_input_dimensions():
    model=empty_building(); model.discretize(); result=simulate_building_model(model,[2],np.empty((0,3)),np.empty((0,3)))
    expected=[2]
    for _ in range(3): expected.append(expected[-1]/np.e)
    np.testing.assert_allclose(result.X_full[0],expected)
    assert result.U.shape==(0,3) and result.V.shape==(0,3) and result.Y.shape==(0,3)


def test_time_orientation_and_matlab_final_state_quirk():
    model=empty_building(); model.discretize(); result=simulate_building_model(model,[1],np.empty((0,4)),np.empty((0,4)))
    assert result.X.shape==(1,4) and result.X_full.shape==(1,5)
    assert result.t_hrs.shape==(1,4); np.testing.assert_allclose(result.t_hrs,[np.arange(4)/3600])
    assert result.t_hrs[0,-1]==pytest.approx(3/3600)


def test_callback_signature_invocation_and_returned_trajectories():
    model=empty_building(1,1,1); model.discretize(); experiment=SimulationExperiment(model); experiment.setNumberOfSimulationTimeSteps(3); experiment.setInitialState([1])
    calls=[]
    def callback(x,t,identifiers):
        calls.append((x.shape,t,identifiers)); return np.array([[t]]),np.array([[2.]])
    X,U,V,t=experiment.simulateBuildingModel("handle",callback)
    assert len(calls)==3 and [c[1] for c in calls]==[0,1/3600,2/3600]
    assert all(c[0]==(1,1) for c in calls); np.testing.assert_array_equal(U,t); np.testing.assert_array_equal(V,np.full((1,3),2.))
    assert X.shape==(1,3) and experiment.X_full.shape==(1,4)


def test_thermal_callback_and_malformed_callbacks():
    model=empty_building(); experiment=SimulationExperiment(model); experiment.setNumberOfSimulationTimeSteps(2); experiment.setInitialState([1])
    calls=[]
    X,Q,t=experiment.simulateThermalModel("handle",lambda x,time,ids:(calls.append(time) or np.array([[0.]])))
    assert calls==[0,1/3600] and X.shape==(1,2) and Q.shape==(1,2)
    with pytest.raises(ValidationError,match=r"return \(u, v\)"): simulate_bm(model,[1],1,lambda *_:np.array([1]))
    with pytest.raises(ValidationError,match="callback u"): simulate_bm(empty_building(1,1,0),[1],1,lambda *_:(np.zeros((2,1)),np.empty((0,1))))


def test_validation_wrong_state_horizon_nan_and_undiscretized_sampling():
    model=empty_building(1,1,1)
    with pytest.raises(ValidationError,match="x0"): simulate_building_model(model,[1,2],np.zeros((1,1)),np.zeros((1,1)))
    with pytest.raises(ValidationError,match="horizons"): simulate_building_model(model,[1],np.zeros((1,2)),np.zeros((1,1)))
    with pytest.raises(ValidationError,match="NaN"): simulate_building_model(model,[1],np.array([[np.nan]]),np.zeros((1,1)))
    model.Ts_hrs=None
    with pytest.raises(ValidationError,match="sampling time"): simulate_bm(model,[1],1,lambda *_:(np.zeros((1,1)),np.zeros((1,1))))


def test_stale_discrete_sampling_time_is_rejected():
    model=empty_building(); model.discretize(); model.set_discretization_step(2/3600)
    with pytest.raises(ValidationError,match="does not match"): simulate_bm(model,[1],1,lambda *_:(np.empty((0,1)),np.empty((0,1))))
