# BRCM one-surface worked example: `Zn001:Wall001` / `B0001`

This is a numerical reconstruction from the current IDF conversion and BRCM matrices. No package or notebook code was modified. `Wall001` is used for the exterior pathway; the massive floor is also shown because the current exterior walls and roof are massless and therefore cannot demonstrate massive-layer state generation.

## Physical diagram

```text
Original BRCM, Wall001 opaque part

Tamb ── [1/(h_ext A)] ── [R13/A] ── [1/(h_int A)] ── Tzone(Czone)
                                                           │
                                                           └── floor link ── Tfloor(Cfloor)

Window occupying 10 m² of Wall001

Tamb ── [1/(Uwin Awin)] ── Tzone
Iwindow ── [Awin·SHGC] ── q_zone

G5 extra heat path

Qsolar + Qsky + Qground + Qair ── [α = Gwall/(h_ext A)] ── q_zone

Best Current/C4

Tamb, Qsolar, QLW ── algebraic outside-face balance Ts ── Gin ── Tzone
```

## 1. Input data

### Exterior wall `B0001`

| Quantity | Converted value | Unit |
|---|---:|---|
| EnergyPlus surface | `Zn001:Wall001` | – |
| Gross wall area | 69.67728 | m² |
| Window gross area | 10.00000 | m² |
| Opaque net area `A` | 59.67728 | m² |
| Construction | `C0001`, `R13WALL` | – |
| Material | `M0002`, `R13LAYER` | – |
| Material areal resistance | 2.290965 | m²K/W |
| Thickness/conductivity/density/cp | not defined; no-mass R-value material | – |
| Exterior coefficient `h_ext` | 12.5 | W/m²K |
| Interior coefficient `h_int` | 7.0 | W/m²K |
| Boundary | `AMB ↔ Z0001` | – |
| Original window U | 1.0 | W/m²K |
| Original window SHGC | 0.5 | – |
| Corrected EP assembly U | 3.798 | W/m²K |
| Corrected EP assembly SHGC | 0.684 | – |

The wall is read at `src/brcm/thermal_generation.py:107-121`. Window area is subtracted at lines 109-112. Film coefficients are selected at lines 83-91 and 155-170.

Wall resistance and conductance are

`R_ext = 1/(h_ext A) = 1/(12.5·59.67728) = 0.001340544 K/W`

`R_layer = R''/A = 2.290965/59.67728 = 0.038389233 K/W`

`R_int = 1/(h_int A) = 1/(7·59.67728) = 0.002393828 K/W`

`R_total = R_ext + R_layer + R_int = 0.042123605 K/W`

`G_wall = 1/R_total = 23.7396588 W/K`

The equivalent assembly U-value including these films is

`U_wall = G_wall/A = 0.39780 W/m²K`.

The zone-side conductance used by Best Current after eliminating the exterior side is

`G_in = 1/(R_layer + R_int) = 24.5199840 W/K`.

The massless boundary conductance is generated at `src/brcm/thermal_generation.py:166-177` and stored as an ambient `BoundaryCondition` at lines 179-197.

### Massive floor `B0005` supporting the RC-state example

| Quantity | Value | Unit |
|---|---:|---|
| Area | 232.2576 | m² |
| Thickness `d` | 0.1015 | m |
| Specific thermal resistance `1/k` | 0.5781760511 | mK/W |
| Conductivity `k` | 1.72958 | W/mK |
| Density `ρ` | 2242.585 | kg/m³ |
| Specific heat `cp` | 836.8 | J/kgK |
| Zone-side film `h` | 5.0 | W/m²K |
| Boundary | `ADB ↔ Z0001` | – |

For the centered floor state:

`R_layer = d(1/k)/A = 0.1015·0.5781760511/232.2576 = 2.52671470×10⁻⁴ K/W`

`R_half = R_layer/2 = 1.26335735×10⁻⁴ K/W`

`R_film,zone = 1/(hA) = 1/(5·232.2576) = 8.6111×10⁻⁴ K/W`

`G_floor-zone = 1/(R_half + R_film,zone) = 1012.7109726 W/K`

`C_floor = ρ cp d A = 44,239,128.281 J/K`.

The state is created because `R_value` is empty for this material. Formulas and state naming are implemented at `src/brcm/thermal_generation.py:122-149`; capacitance is line 131 and half resistance is line 134.

## 2. RC network generation before EHF

The actual state and heat-flow vectors are

`x = [Tzone, Tfloor]ᵀ = [x_Z0001, x_B0005_L1_s1_ADBZ0001]ᵀ`

`q = [q_zone, q_floor]ᵀ`.

The zone-air capacity generated as `ρ_air cp_air V` is

`C_zone = 1,293,955.1533 J/K`.

Before EHF composition, all exterior boundary conductances remain in `boundary_conditions`; only the zone–floor internal link is in `Abar`:

```text
Abar [W/K] = [[-1012.71097262,  1012.71097262],
              [ 1012.71097262, -1012.71097262]]

Xcap [J/K] = [[ 1293955.15330145,        0          ],
               [       0,          44239128.28099874]]
```

Therefore

```text
A_th = Xcap⁻¹ Abar [s⁻¹]
     = [[-7.82647660e-4,  7.82647660e-4],
        [ 2.28917479e-5, -2.28917479e-5]]

Bq = Xcap⁻¹ [K/J]
   = [[7.72824311e-7, 0],
      [0, 2.26044237e-8]]
```

The pre-EHF equations are exactly

`C_zone dTzone/dt = 1012.7109726(Tfloor−Tzone) + q_zone`

`C_floor dTfloor/dt = 1012.7109726(Tzone−Tfloor) + q_floor`.

Matrix assembly and normalization are at `src/brcm/thermal_generation.py:151-203`. Matrix units are declared at `src/brcm/thermal_model.py:13-18`.

## 3. Original BuildingHull contribution

`BuildingHull` converts every ambient boundary into

`q_i += G(Tamb−Ti)`.

For the opaque part of `Wall001`, with zone index `0`, heat-flow index `0`, local hull disturbance indices `v_Tamb=0`, `v_solGlobFac_B0001=1`:

`Aq[0,0] += −23.7396588 W/K`

`Bq_v[0,0] += +23.7396588 W/K`.

There is no package opaque-solar coefficient for this wall because `_outer_q` finds no massive wall state. Package facade solar would otherwise enter an outer massive-layer `q` channel at `src/brcm/ehf.py:327-331`.

For the original 10 m² window:

`UA = 1.0·10 = 10 W/K`

`q_window,cond = 10(Tamb−Tzone) W`

`Awin·SHGC = 10·0.5 = 5 m²`

`q_window,solar = 5 Iwindow W`.

The notebook sets `secondary_gains_fraction=1`, so this solar coefficient is injected entirely at `q_zone`; it is not distributed to the floor. Window conduction and solar are implemented at `src/brcm/ehf.py:333-354`.

The complete original `BuildingHull` matrices for this case are

```text
Aq = [[-157.92031674, 0],
      [0, 0]]                         [W/K]

Bq_v, local columns [Tamb, Iwindow] =
     [[157.92031674, 5.0],
      [0, 0]]

Bq_u  = shape (2,0)
Bq_xu = shape (2,2,0)
Bq_vu = shape (2,2,0)
```

`157.92031674 W/K` is the sum of five opaque ambient paths, including `Wall001=23.7396588 W/K`, plus original window `UA=10 W/K`. Infiltration is configured at zero ACH, so its coefficient is zero. The general infiltration equation is at `src/brcm/ehf.py:355-358`.

There are no `u` controls, hence all bilinear tensors are empty.

## 4. Composition into the original full continuous model

Composition is implemented at `src/brcm/building_model.py:99-111`:

`A_full = A_th + Bq Aq`

`Bv_full = Bq Bq_v`.

The selected wall's marginal contribution to the zone row is

`ΔA_full[0,0] = −G_wall/C_zone = −1.83465855×10⁻⁵ s⁻¹`

`ΔBv_full[0,Tamb] = +G_wall/C_zone = +1.83465855×10⁻⁵ K/(s·°C)`.

After all hull paths, the window, and internal-gain mapping, the actual full matrices are

```text
A_full [s⁻¹] =
[[-9.04692320e-4,  7.82647660e-4],
 [ 2.28917479e-5, -2.28917479e-5]]

Bv_full, columns [IG W/m², Tamb °C, Iwindow W/m²] =
[[1.79494320e-4, 1.22044660e-4, 3.86412156e-6],
 [0,             0,             0]]
```

The internal-gain coefficient is `zone_area/C_zone`; the notebook first converts EP total watts to W/m², and `InternalGains` multiplies by zone area at `src/brcm/ehf.py:148-160`.

## 5. Exact 900-second discretization

For `Ts=0.25 h=900 s`, BRCM computes

`Ad = exp(A_full·900)`

`Bd = ∫₀⁹⁰⁰ exp(A_full τ)B dτ`.

The solve and singular fallback are implemented at `src/brcm/building_model.py:129-159`. Hours are multiplied by 3600 exactly once at line 150. Simulation applies the matrices at `src/brcm/simulation.py:89-100`.

For the original full model:

```text
Ad = [[0.44725286, 0.47742567],
      [0.01396428, 0.98516315]]

Bd_v = [[1.10777289e-1, 7.53214729e-2, 2.38479362e-3],
        [1.28332354e-3, 8.72577951e-4, 2.76271593e-5]]
```

One explicit original timestep is therefore

`Tzone[k+1] = 0.44725286 Tzone[k] + 0.47742567 Tfloor[k]`

`                 + 0.110777289 IG[k] + 0.0753214729 Tamb[k]`

`                 + 0.00238479362 Iwindow[k]`,

where `IG` and `Iwindow` are W/m². The input coefficients already contain the 900-second state response and have the corresponding K-per-input units.

Heat from `Wall001` affects the floor within the same ZOH interval through the zone–floor coupling; this is why the second row of `Bd_v` is nonzero even though hull heat enters only `q_zone`.

## 6. Window replacement in Best Current, G3b, and G5

The corrected window conduction is

`UA = 3.798·10 = 37.98 W/K`.

The corrected BRCM solar coefficient would be

`Awin g = 10·0.684 = 6.84 m²`.

The notebooks construct the corrected hull, subtract `6.84` once from `Bq_v[q_zone,Iwindow]`, and create a new disturbance already in watts:

`q_zone += 1·Qwindow,transmitted,EP`.

Best Current: notebook cell 10, JSON lines 799-810. G3b: cell 17, lines 2303-2309. G5: cell 17, lines 2297-2303. Because `secondary_gains_fraction=1`, the coefficient being removed exists wholly at `q_zone`; no primary massive-face term is left behind and no double count is present.

## 7. Same massless surface under three formulations

### Original BRCM

`q_wall = 23.7396588(Tamb−Tzone) W`.

No opaque solar or explicit long-wave term is present.

### G3b/G5

The fixed path is retained and

`α = G_wall/(h_ext A) = 23.7396588/(12.5·59.67728) = 0.0318240494`.

Thus

`q_wall = 23.7396588(Tamb−Tzone)`

`       + 0.0318240494(Qsolar+Qsky+Qground+Qair) W`.

The EP quantities are already total surface heat rates [W]. There is deliberately no further area multiplication. The resulting heat rate is divided by `C_zone` and enters the zone derivative. G3b implementation: cell 17, lines 2315-2333. G5: cell 17, lines 2309-2327.

For the corrected G5 whole model, exposing the selected wall's aggregate `Qwall=Qsolar+QLW` as a separate input, exact ZOH gives

```text
Ad_G5 = [[0.43866400, 0.47341183],
         [0.01384687, 0.98513174]]

Bd_G5, columns [IG, Tamb, Qwindow_EP, Qwall] =
[[1.09849502e-1, 8.79241720e-2, 4.72964079e-4, 1.50516322e-5],
 [1.27608119e-3, 1.02138271e-3, 5.49424945e-6, 1.74849266e-7]]
```

The selected-wall part of the G5 timestep is therefore

`Tzone[k+1] ... + 1.50516322×10⁻⁵ Qwall[k]`, with `Qwall` in W.

Other opaque surfaces have separate `α_s Q_s` inputs and are omitted from this one-wall display, not from the notebook simulation.

### Best Current dynamic algebraic surface

Best Current cancels the original wall contribution from `A/Bv` and uses

`Ts = (hA Tamb + Qsolar + QLW + Gin Tzone)/(hA+Gin)`

`q_wall = Gin(Ts−Tzone)`

`       = Geq(Tamb−Tzone) + β(Qsolar+QLW)`

with

`Geq = Gin hA/(Gin+hA)`, `β = Gin/(Gin+hA)`.

The cancellation is at Best Current cell 10, lines 845-856; reconstruction and injection are at lines 864-872.

At the second April interval (`k=1`), the available surface values are:

| Quantity | Value |
|---|---:|
| EP exterior `h` | 2.96593037 W/m²K |
| `hA` | 176.998657 W/K |
| Outdoor dry bulb | 3.85 °C |
| EP outside-face temperature | 2.70382259 °C |
| Sky temperature | −2.88405552 °C |
| Ground reference | 19.12 °C |
| `h_sky` | 1.47110126 W/m²K |
| `h_ground` | 2.15803748 W/m²K |
| `Qsolar` | 0 W |
| `Qsky` | −490.567204 W |
| `Qground` | +2114.170652 W |
| `Qair` | −42.454651 W |
| `QLW` | +1581.148797 W |

The currently retained seasonal CSV was last produced by the G5 template and does not contain the surface-local outdoor dry-bulb column requested by Best Current. The displayed 3.85 °C is therefore the actual site outdoor dry bulb at that interval; Best Current uses the surface-local output. The algebraic coefficients `hA`, `Geq`, `β`, and all reported surface radiation/solar values are unaffected by this substitution, while the numerical `Geq·Tamb` forcing would need the local value if it differs from the site value.

Consequently

`Geq = 21.5364902 W/K`, `β = 0.121676009`,

and the wall equation at this interval is

`q_wall = 21.5364902(Tamb−Tzone) + 0.121676009(Qsolar+QLW) W`.

For comparison, G5 uses the larger fixed conductance `23.7396588 W/K` but attenuates the reported heat rates much more strongly: `α=0.0318240` rather than `β=0.1216760`.

If only `Wall001` is switched to this actual dynamic coefficient while the other surfaces remain on their original paths, and corrected window logic is retained, the isolated exact-ZOH matrices are

```text
Ad = [[0.43933426, 0.47372613],
      [0.01385607, 0.98513421]]

Bd, columns [IG, Tamb, Qwindow_EP, Qwall] =
[[1.09922152e-1, 8.69396131e-2, 4.73276880e-4, 5.75864419e-5],
 [1.27664912e-3, 1.00972714e-3, 5.49669469e-6, 6.68815872e-7]]
```

This last matrix is an isolated one-wall attribution. The full Best Current notebook performs the same replacement for all five ambient opaque surfaces, so its complete timestep matrix is recomputed with all five dynamic `Geq,s` values.

## 8. Causal pathway from one wall to zone temperature

```text
IDF surface + construction
  → net opaque area after subtracting window
  → massless series resistance and Gwall
  → ambient BoundaryCondition (no wall state)
  → BuildingHull Aq/Bq_v entries at q_zone
  → Bq = 1/Czone converts W to K/s
  → BuildingModel adds Bq·Aq and Bq·Bq_v
  → exact 900 s ZOH
  → Tzone[k+1]
  → zone–floor conductance also transfers part of the heat to Tfloor[k+1]
```

For G5, EP `Qsolar/Qsky/Qground/Qair` join at the `q_zone` step through `α`. For Best Current, they first enter the algebraic exterior-face balance and then reach `q_zone` through `Gin/(Gin+hA)`.

## 9. Dimensional and implementation checks

- `Abar`: W/K; `Xcap`: J/K; `A`: s⁻¹; `Bq`: K/J; all `q` channels: W.
- Irradiance is W/m² and is multiplied by area once. EP surface/window heat-rate outputs are already W and are not multiplied by area.
- `hA(T1−T2)`, `G(T1−T2)`, and every reconstructed long-wave term are W.
- Celsius differences equal Kelvin differences. No absolute-temperature Stefan–Boltzmann expression is evaluated in these notebooks.
- `0.25 h` is converted to `900 s` once inside discretization.
- No bilinear input is active because `u` is empty; `Bq_u`, `Bq_xu`, and `Bq_vu` have zero-width dimensions.
- No solar/window double count is present for this case's `secondary_gains_fraction=1` configuration.
- The very large positive `Qground` above follows from using `Site Ground Temperature=19.12 °C` as the effective radiant reference. The notebooks already flag that this may not be EnergyPlus's exact effective ground-radiant reference; it is a formulation uncertainty, not a dimensional error.

## Exact source locations

- State/capacity/resistance generation: `src/brcm/thermal_generation.py:94-203`
- Thermal-model units and identifier contract: `src/brcm/thermal_model.py:12-40`
- EHF equation and matrix sizing: `src/brcm/ehf.py:13-14,61-113`
- BuildingHull boundary, opaque solar, window, infiltration: `src/brcm/ehf.py:244-359`
- Full-model composition: `src/brcm/building_model.py:84-111`
- Exact ZOH: `src/brcm/building_model.py:122-159`
- State update and bilinear terms: `src/brcm/simulation.py:73-101`
- Best Current window replacement and dynamic exterior: notebook cell 10, JSON lines 799-872
- G3b fixed-path formulation: notebook cell 17, JSON lines 2303-2333
- G5 fixed-path formulation: notebook cell 17, JSON lines 2297-2327
