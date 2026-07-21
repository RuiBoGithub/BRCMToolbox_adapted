# EnergyPlus 23.2 ↔ BRCM best-current comparison report

Notebook: `BRCM_EnergyPlus_23_2_Best_Current_Comparison.ipynb`

This configuration contains only changes supported by the controlled ablation study. No parameters were calibrated, no inferred ground-radiant temperature was used, and no `src/brcm` behavior was overwritten.

## Result

| Season | RMSE [K] | CVRMSE [%] | NMBE [%] | MAE [K] | Maximum absolute error [K] |
|---|---:|---:|---:|---:|---:|
| January | 2.133 | 36.783 | 31.980 | 1.855 | 6.899 |
| April | 1.469 | 13.805 | 4.233 | 1.130 | 5.517 |
| July | 1.182 | 5.839 | 2.472 | 0.933 | 3.038 |
| October | 1.927 | 10.988 | 8.042 | 1.602 | 4.095 |

The notebook now presents only this single best-current formulation. Historical baseline and ablation variants are intentionally omitted from its executable comparison and plots.

## Implemented checklist

- [x] Preserve the validated IDF, EPW, 15-minute timestep, four five-day seasonal periods, and weather-only EnergyPlus runs.
- [x] Preserve the EnergyPlus initial zone-air temperature.
- [x] Use EnergyPlus FenestrationAssembly U-value: 3.798 W/m²K.
- [x] Use EnergyPlus FenestrationAssembly SHGC/g-value: 0.684.
- [x] Represent frame/divider effects only through the lumped assembly U/SHGC supported by the Python BRCM window representation.
- [x] Replace calculated transmitted-window solar with **EnergyPlus-equivalent transmitted window solar**.
- [x] Label transmitted-window solar as diagnostic-equivalence forcing, not an independent prediction.
- [x] Replace the fixed algebraic ambient pathway for all five massless exterior opaque elements.
- [x] Use an algebraic exterior-surface balance with no arbitrary surface capacitance.
- [x] Apply dynamic exterior convection at the exterior balance.
- [x] Apply EnergyPlus-reported opaque absorbed solar at the exterior balance.
- [x] Apply reconstructed sky, ground, and air long-wave exchange at the exterior balance.
- [x] Pass only the resulting inward conduction through the BRCM zone/RC pathway.
- [x] Avoid direct exterior heat-flow injection into zone air.
- [x] Use `Site Ground Temperature` as an available, explicitly limited ground reference.
- [x] Avoid M5, inferred temperatures, fitted ground temperatures, and parameter tuning.
- [x] Initialize the represented concrete-floor state by resistance-weighted interpolation between EnergyPlus inside/outside surface temperatures.
- [x] Avoid inventing states for massless elements.
- [x] Confirm internal convective gain, internal radiant gain, outdoor-air transfer, interzone transfer, and system-air transfer are all exactly 0 W.
- [x] Produce four clean exact-datetime plots containing outdoor, EnergyPlus-zone, best-current BRCM-zone, transmitted-window-solar, and opaque-solar trajectories.
- [x] Keep all changes notebook-local.

## Best-current equations

For each massless exterior element:

```text
q_sky    = h_sky A (T_sky - T_surface,EP)
q_ground = h_ground A (T_ground,available - T_surface,EP)
q_lw     = q_sky + q_ground + q_air,EP

T_surface =
    [h_conv A T_air + q_solar + q_lw + G_in T_inner]
    / [h_conv A + G_in]

q_inward = G_in (T_surface - T_inner)
```

The EnergyPlus surface temperature in the long-wave reconstruction makes this a diagnostic-equivalence comparison. It is not a fully independent weather-to-temperature prediction.

## Assumptions retained

- [x] EnergyPlus `Site Ground Temperature` is used because it is exported and available.
- [x] It is **not** asserted to equal EnergyPlus's effective exterior ground-radiant reference.
- [x] EnergyPlus time-varying exterior convection coefficients are diagnostic inputs.
- [x] EnergyPlus opaque absorbed-solar rates are diagnostic inputs.
- [x] EnergyPlus transmitted-window solar is a diagnostic input.
- [x] EnergyPlus surface temperature is used to reconstruct exterior long-wave components.
- [x] The window remains a lumped U/SHGC model; unsupported frame/divider dynamics are not invented.

## Unresolved limitations

- [ ] Identify EnergyPlus's effective exterior ground/surroundings radiant temperature and view-factor treatment.
- [ ] Reconcile wall sky/ground/air components exactly against the reported net exterior radiation rate.
- [ ] Reproduce EnergyPlus exterior convection and radiation independently from weather and geometry.
- [ ] Replace EnergyPlus-equivalent transmitted solar with independently calculated, orientation-specific window solar while retaining parity.
- [ ] Quantify frame/divider heat transfer beyond the supported lumped assembly representation.
- [ ] Compare EnergyPlus inside-face conduction and convection against BRCM inward heat flow for each surface.
- [ ] Audit internal RC state placement and resistance splitting against EnergyPlus conduction-transfer-function behavior.
- [ ] Test whether the concrete-floor state initialization or internal node placement explains early thermal decay differences.
- [ ] Repeat the best-current comparison for January, July, and October without changing physical parameters.
- [ ] Establish MATLAB-toolbox parity separately from EnergyPlus 23.2 parity.
- [ ] Promote a model variant into `src/brcm` only after its API, equations, and regression behavior are independently validated.

## Current interpretation

The ablation evidence shows that window equivalence and the exterior heat-flow pathway materially improve parity. The algebraic and 1–1000 J/K exterior-node experiments are nearly identical, so arbitrary exterior capacitance is not responsible for the remaining error. The residual is most likely shared between unresolved exterior-boundary/window model-form details and internal RC topology/state placement. The current evidence does not justify calibrating either category.
