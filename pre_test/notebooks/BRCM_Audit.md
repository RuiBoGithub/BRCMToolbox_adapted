# EnergyPlus 23.2 ↔ BRCM model-formulation audit

Scope: `BRCM_EnergyPlus_23_2_Best_Current.ipynb`, `BRCM_EnergyPlus_23_2_G3b_template.ipynb`, `BRCM_EnergyPlus_23_2_G5_template.ipynb`, and the BRCM generation/composition/simulation modules. No implementation or parameter was changed.

## 1. Package model reconstructed

Let `x` contain all zone-air and massive-layer temperatures [°C], and let `q` contain one heat-flow channel [W] per state. The generated thermal model is

`dx/dt = A_th x + Bq q`, with `A_th = Xcap⁻¹ Abar` and `Bq = Xcap⁻¹`.

- `Xcap = diag(C_i)` [J/K]. Zone capacity is `ρ_air cp_air V`; a massive material layer has `C = A d ρ cp`.
- `Abar` [W/K] contains symmetric conductance links. Consequently `A_th` is [s⁻¹], `Bq` is [K/J], and `Bq q` is [K/s].
- This case has two states: zone air `x_Z0001` and the one massive adiabatic-floor layer `x_B0005_L1_s1_ADBZ0001`. The five ambient opaque surfaces are massless and have no state. Windows also have no state.
- A massive material layer creates one centered capacitance; half-layer resistances connect it to neighboring nodes. A no-mass or fully massless construction creates only a series boundary conductance.

Code: `src/brcm/thermal_generation.py:94-203`, `src/brcm/thermal_model.py:12-36`.

EHF models define

`q = Aq x + Bq_u u + Bq_v v + Σ_i[(Bq_xu,i x + Bq_vu,i v)u_i]`.

Composition gives

`dx/dt = (A_th + Bq Aq)x + Bq Bq_u u + Bq Bq_v v + Σ_i[Bq Bq_xu,i x + Bq Bq_vu,i v]u_i`.

Code: `src/brcm/ehf.py:13-14,61-113`; `src/brcm/building_model.py:84-111`.

### BuildingHull equations

| Term | Heat-flow equation and injection | Dimensions |
|---|---|---|
| Ambient/ground boundary | `q_i += G(T_boundary − x_i)`, injected into the state-side `q_i` | `[W/K][K]=[W]` |
| Window conduction | `q_zone += UA(T_amb − T_zone)` | `[W/m²K][m²][K]=[W]` |
| Window solar | `Qwin = Awin·SHGC·Iwin`; primary part is distributed to massive interior-face `q` channels by net area and secondary part to `q_zone` | `[m²][-][W/m²]=[W]` |
| Opaque solar in package | `Qsol = Anet·absorptance·I`; injected at the outer massive-layer heat-flow channel | `[m²][-][W/m²]=[W]` |
| Infiltration | `q_zone += Ginf(Tamb−Tzone)`, `Ginf = ACH·V·ρ·cp/3600` | `[1/h][m³][kg/m³][J/kgK]/[s/h]=[W/K]` |
| Internal gains | Notebook converts EP `[W]` to `[W/m²]`; `InternalGains` multiplies by zone floor area and injects `q_zone` | `[W/m²][m²]=[W]` |

Code: `src/brcm/ehf.py:244-275,303-358` and `src/brcm/ehf.py:140-160`.

Opaque solar through `BuildingHull` requires a massive exterior state. Therefore the original model cannot use that route for this case's massless walls/roof; the notebooks add notebook-local equivalents directly to the zone equation.

## 2. Original/template formulation

The original model is the composed package model with `BuildingHull + InternalGains`:

`dx/dt = A0 x + Bv,0 v`.

For each massless ambient surface `s`, `A0/Bv,0` contain the fixed term `G_s(Tamb−Tzone)`. Window conduction is `U_original Awin(Tamb−Tzone)`. Window solar is `Awin g_original Iwin`; the notebook configures `secondary_gains_fraction=1`, so all of it enters `q_zone` and none is distributed to the massive floor face. Opaque solar and explicit long-wave are absent. Infiltration is configured as zero ACH. Internal gains are zero in the audited EnergyPlus case.

Initial conditions are uniform at the first EP zone-air temperature for both states. Massless surfaces have no initial condition.

Notebook locations: G3b/G5 template cells 3, 7, 9, 11, 13 and 15. Package implementation locations are listed above.

## 3. Best_Current formulation

Best Current first creates corrected window data from the EP `FenestrationAssembly` record. It retains corrected window conduction, removes calculated BRCM window solar once,

`Bq_v[q_zone,Iwin] ← Bq_v[q_zone,Iwin] − Awin g_EP`,

and adds exact EP transmitted window heat rate with unit coefficient:

`q_zone += Qwin,EP`.

The subtraction and replacement are at notebook cell 10, JSON lines 799-810. `Awin g_EP` is `[m²]`; multiplying irradiance `[W/m²]` would have produced `[W]`. The replacement coefficient is dimensionless because its disturbance is already `[W]`. No window-solar double count remains for this uncontrolled case.

For every massless ambient opaque surface, Best Current cancels the original fixed path in `A/Bv` and applies a time-varying algebraic surface balance:

`Ts = (hA Tair + Qsolar + QLW + Gin Tzone)/(hA + Gin)`

`Geq = Gin hA/(hA + Gin)`

`q_zone,s = −Geq Tzone + Gin(hA Tair + Qsolar + QLW)/(hA + Gin)`.

Here `Gin` and `hA` are [W/K], the numerator of `Ts` is [W], `Ts` is [K or °C on the same affine scale], `Geq` is [W/K], and `q_zone,s` is [W]. It enters the zone row directly as `−Geq/Czone` in `A` and `+Q/Czone` in the derivative forcing. The fixed-path cancellation is at notebook lines 845-856; the dynamic balance is at lines 869-872.

Long-wave is reconstructed as

`Qsky = hsky A(Tsky−Ts,EP)`, `Qground = hground A(Tground−Ts,EP)`, `QLW = Qsky+Qground+Qair,EP`.

Each coefficient is [W/m²K], area is [m²], and temperature difference is [K], hence [W]. `Qair,EP` is already a total surface heat-transfer rate [W] and is correctly not multiplied by area. `Qsolar,EP` is also already a total heat-gain rate [W] and is correctly not multiplied by area. Code: notebook line 864.

Best Current initializes zone air directly from EP. Its one massive floor-layer state is resistance-weighted between EP inside/outside surface temperatures. Code: notebook lines 813-837 and 877-903. Massless surfaces receive no state.

## 4. G3b and G5 formulations

G3b and G5 are mathematically identical; only labels, identifiers, and notebook filenames differ. Both use the same corrected window construction and exactly-once EP window-solar replacement as Best Current.

They retain the original fixed ambient term `G_s(Tamb−Tzone)` and add, for each massless opaque surface,

`α_s = G_s/(h_ext,s A_s)`

`q_add,s = α_s(Qsolar,s + Qsky,s + Qground,s + Qair,s)`.

`α` is dimensionless: `[W/K]/([W/m²K][m²])`. Every `Q` is already [W], so `q_add` is [W]. The notebook divides by `Czone` only when adding this heat rate to `dx_zone/dt`, giving [K/s]. G3b code: cell 17, notebook lines 2303-2333. G5 code: cell 17, notebook lines 2297-2327.

G3b/G5 do not replace fixed convection, do not create an exterior state, and do not alter `A` each step. They initialize both existing states uniformly at first EP zone temperature. Thus their initialization differs from Best Current as well as their exterior equation.

## 5. Discrete time

For a fixed continuous system and zero-order-held inputs over `Δt`,

`x[k+1] = Ad x[k] + Bd,w w[k]`,

`Ad = exp(A Δt)`, `Bd = ∫₀^Δt exp(Aτ)B dτ`.

The code uses `Bd = A⁻¹(Ad−I)B` when numerically suitable and an augmented matrix exponential when `A` is singular. Sampling time is supplied in hours and multiplied by 3600 exactly once. The notebooks use `TS_HRS=0.25`, hence `Δt=900 s`. Code: `src/brcm/building_model.py:122-159`; simulation update: `src/brcm/simulation.py:73-101,173-177`.

Best Current recomputes an exact ZOH for its new `A_step` each timestep. G3b/G5 keep constant `A` but also call the same ZOH each step in their notebook-local loop; this is redundant computationally, not mathematically different.

The generic package supports `x·u` and `v·u` bilinear terms. Its discretization treats their coefficient matrices as held forcing channels and multiplies them by `u[k]` after discretization. That is not the exact exponential solution of a general bilinear system with `A+Σu_iA_i`; however this case has no control inputs (`u` is empty), so the issue is inactive.

All seasonal notebook loops use the first EP sample as `x[0]` and forcing samples `[1:]` for subsequent intervals. Best Current likewise reads dynamic exterior terms at `k+1`. This interval-end convention is internally consistent, though it should remain explicit.

## 6. Comparison

| Component | Original BRCM | Best_Current | G3b | G5 | Difference / concern |
|---|---|---|---|---|---|
| RC states | Zone + one massive floor layer | Same | Same | Same | No exterior wall/roof state |
| Massless exterior | Fixed series `G(Tamb−Tzone)` | Fixed path removed; instantaneous algebraic surface | Fixed path retained | Same as G3b | Intentional major model-form difference |
| Exterior convection | Fixed converted `h_ext` | EP time-varying `h_conv` | Fixed converted `h_ext` | Same | Best Current transmits more bandwidth |
| Opaque solar | Absent | EP total rate in algebraic balance | `α Qsolar,EP` to zone | Same | EP-fed; already W, no area multiplication |
| Long-wave | Absent | EP coefficients/rates in algebraic balance | `α( Qsky+Qground+Qair )` | Same | EP surface temperature makes it diagnostic-equivalent |
| Window conduction | Original converted U × gross area | EP assembly U × gross area | Same corrected equation | Same | Frame/divider represented only in lumped assembly value |
| Window solar | BRCM `A g I` | Removed once; EP transmitted rate added once | Same | Same | No active double count found |
| Solar injection | Massive-face distribution + zone secondary | Exact transmitted solar directly to zone; opaque via exterior balance | Exact transmitted solar directly to zone; opaque directly to zone after `α` | Same | Distribution changes when replacing BRCM term |
| Infiltration | `ρcp·ACH·V/3600`, but ACH=0 | Same | Same | Same | No issue in this case |
| Initial massive state | Uniform zone temperature | EP resistance-weighted surface temperature | Uniform zone temperature | Uniform | Accidental comparison confound unless standardized |
| Discretization | Fixed exact ZOH, 900 s | Per-step exact ZOH | Same exact result with constant A | Same | No timestep-factor error found |
| Independence | Weather/converted properties | EP-fed diagnostic | EP-fed diagnostic | EP-fed diagnostic | None of the corrected forms is independently predictive |

## 7. Findings and concerns

1. **No demonstrated solar double count:** corrected variants subtract `Awin g_EP` once from the same zone heat-flow coefficient created by `BuildingHull`, then add `Qwin,EP` once. This is exact for the notebook's uncontrolled window with `secondary_gains_fraction=1`; the method is not generic for blinds or a fraction below one, where some calculated solar is injected into massive-face channels too.
2. **Already-net/total EP quantities:** `Surface Outside Face Solar Radiation Heat Gain Rate`, `Surface Outside Face Thermal Radiation to Air Heat Transfer Rate`, and `Surface Window Transmitted Solar Radiation Rate` are consumed as total [W]. Multiplying them by area again would be wrong; the notebooks do not do so.
3. **Sign convention:** positive EP surface solar is treated as heat into the exterior balance. Sky/ground terms use `hA(T_reference−T_surface)`; colder sky therefore produces negative heat input. `Qair,EP` is added with its reported sign. These signs are internally coherent but depend on EnergyPlus output sign definitions and deserve an automated one-step balance assertion.
4. **Celsius versus Kelvin:** only temperature differences enter reconstructed long-wave linearization, so °C differences equal K differences. Conductive affine terms use a consistent Celsius reference. No absolute-temperature Stefan–Boltzmann calculation occurs.
5. **Fragile surface/BC matching:** notebooks recover `G_total` by choosing the numerically closest ambient boundary condition rather than matching a stable element identifier. Equal or similar conductances could associate the wrong surface accidentally.
6. **Initialization differs accidentally across notebooks:** Best Current resistance-weights the floor state; G3b/G5 use uniform zone temperature. Model-form comparisons should use one declared initialization for every variant.
7. **G3b and G5 are duplicates:** there is no mathematical difference. Maintaining both creates drift risk.
8. **G3b/G5 fixed-path injection is a steady equivalent approximation:** `α=G/(hA)` attenuates EP surface heat rates through the original series path, but it is not derived from a new dynamic surface balance. It is dimensionally correct and empirically robust, yet should be labelled as such.
9. **Best Current exterior terms are internally complete but bandwidth-sensitive:** fixed convection is cancelled before dynamic convection is added, so there is no obvious fixed/dynamic convection double count. Its EP-fed `h`, surface temperature, and heat rates make it a diagnostic reference rather than a deployable model.

## 8. Recommended clean baseline before further experiments

Use one canonical notebook/model family, not separate G3b and G5 copies:

1. Keep **Original BRCM (G0)** unchanged as the independent regression baseline.
2. Define a single **diagnostic G5** with corrected assembly U/SHGC, exactly-once EP transmitted-window replacement, fixed original exterior conductance, and the coupled opaque-solar plus reconstructed-long-wave injection. Retire the duplicate G3b label.
3. Keep **Best Current dynamic exterior** only as a separately named C4 diagnostic reference; do not mix its dynamic convection equation into G5.
4. Standardize initialization across every comparison. Prefer the template uniform initialization for strict model-form ablations, and report resistance-weighted initialization as a separate initialization experiment.
5. Replace nearest-conductance surface matching with an explicit element-to-boundary mapping before more variants are tested.
6. Add automated dimensional/multiplicity assertions: window calculated-solar coefficient removed once, EP window rate added once, all EP rate inputs declared `[W]`, irradiances `[W/m²]`, and every area multiplication recorded.
7. The deployable target should retain G5 topology but replace EP transmitted solar and EP long-wave reconstruction with independent weather/geometry/construction calculations. Until then, G0 remains the clean predictive baseline and G5 remains the robust diagnostic formulation.
