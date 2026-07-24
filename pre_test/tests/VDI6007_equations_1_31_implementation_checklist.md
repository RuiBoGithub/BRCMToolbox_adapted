# VDI 6007 Part 1 — Equations (1)–(31) implementation checklist

Scope: implementation of the thermal-response / RC-parameter derivation up to Equation (31).  
Excluded here: exterior heat exchange and equivalent outdoor temperature from Equation (32) onward.

---

## 0. Core symbols

### Geometry and material properties
- \(A\) — surface area of the building component \([\mathrm{m^2}]\)
- \(s\) — layer thickness \([\mathrm{m}]\)
- \(\lambda\) — thermal conductivity \([\mathrm{W/(m\,K)}]\)
- \(\rho\) — density \([\mathrm{kg/m^3}]\)
- \(c\) — specific heat capacity \([\mathrm{J/(kg\,K)}]\)

### Per-unit-area layer properties
- \(R = s/\lambda\) — thermal resistance per unit area \([\mathrm{m^2K/W}]\)
- \(C = c\rho s\) — heat capacity per unit area \([\mathrm{J/(m^2K)}]\)

### Dynamic quantities
- \(\vartheta\) — temperature
- \(q\) — heat flux
- \(\omega\) — angular frequency \([\mathrm{s^{-1}}]\)
- \(T_{BT}\) — characteristic period for an individual building component, in days
- \(T_{RA}\) — characteristic period for room-level aggregation, in days

### Equivalent-network quantities
- \(R_1,R_2,R_3\) — equivalent resistances of one building component
- \(C_1,C_2\) — equivalent capacitances of one building component
- \(C_{1,\mathrm{korr}}\) — corrected capacitance for asymmetrically loaded components
- \(R_w=R_1+R_2+R_3\) — total resistance of the equivalent component

### Grouping notation
- \(BT\) — individual building component
- \(AW\) — asymmetrically loaded overall building component
- \(IW\) — symmetrically loaded overall building component
- \(AF\) — exterior window
- \(IF\) — interior window
- \(RA\) — room-level aggregate
- \(\mu,\nu\) — component / layer indices

---

# A. Individual layer transfer matrix — Equations (1)–(9)

## [ ] Eq. (1) — Layer state relation

For each homogeneous layer \(\nu\):

\[
\begin{pmatrix}
\vartheta(x=0)\\
q(x=0)
\end{pmatrix}_{\nu}
=
A_{\nu}
\begin{pmatrix}
\vartheta(x)\\
q(x)
\end{pmatrix}_{\nu}
\]

**Implementation task**
- Represent each layer by a complex \(2\times2\) chain matrix \(A_\nu\).
- Preserve layer order from room side outward.

---

## [ ] Eq. (2) — Chain matrix structure

\[
A_{\nu}=
\begin{pmatrix}
a_{11} & a_{12}\\
a_{21} & a_{22}
\end{pmatrix}_{\nu}
\]

The standard expands the complex matrix into real and imaginary parts.

**Implementation recommendation**
- Use native complex numbers:
  ```python
  A = np.array([[a11, a12],
                [a21, a22]], dtype=complex)
  ```

---

## [ ] Eq. (3) — Real part of \(a_{11}\) and \(a_{22}\)

\[
\Re(a_{11})=\Re(a_{22})
=
\cosh\!\left(\sqrt{\frac{1}{2}\omega_{BT}RC}\right)
\cos\!\left(\sqrt{\frac{1}{2}\omega_{BT}RC}\right)
\]

---

## [ ] Eq. (4) — Imaginary part of \(a_{11}\) and \(a_{22}\)

\[
\Im(a_{11})=\Im(a_{22})
=
\sinh\!\left(\sqrt{\frac{1}{2}\omega_{BT}RC}\right)
\sin\!\left(\sqrt{\frac{1}{2}\omega_{BT}RC}\right)
\]

---

## [ ] Eq. (5) — Real part of \(a_{12}\)

Let

\[
\xi=\sqrt{\frac{1}{2}\omega_{BT}RC}.
\]

Then

\[
\Re(a_{12})
=
R\sqrt{\frac{1}{2\omega_{BT}RC}}
\left[
\cosh(\xi)\sin(\xi)
+
\sinh(\xi)\cos(\xi)
\right]
\]

---

## [ ] Eq. (6) — Imaginary part of \(a_{12}\)

\[
\Im(a_{12})
=
R\sqrt{\frac{1}{2\omega_{BT}RC}}
\left[
\cosh(\xi)\sin(\xi)
-
\sinh(\xi)\cos(\xi)
\right]
\]

---

## [ ] Eq. (7) — Real part of \(a_{21}\)

\[
\Re(a_{21})
=
-\frac{1}{R}
\sqrt{\frac{1}{2}\omega_{BT}RC}
\left[
\cosh(\xi)\sin(\xi)
-
\sinh(\xi)\cos(\xi)
\right]
\]

---

## [ ] Eq. (8) — Imaginary part of \(a_{21}\)

\[
\Im(a_{21})
=
\frac{1}{R}
\sqrt{\frac{1}{2}\omega_{BT}RC}
\left[
\cosh(\xi)\sin(\xi)
+
\sinh(\xi)\cos(\xi)
\right]
\]

---

## [ ] Eq. (9) — Angular frequency

\[
\omega=
\frac{2\pi}{86400\,T}
\]

For individual building components:

\[
\omega_{BT}=\frac{2\pi}{86400\,T_{BT}}
\]

**Implementation note**
- \(T\) is in days.
- Default trial values for component derivation: \(T_{BT}=2\) and \(7\) days.

---

# B. Select component period — Equations (10a)–(10e)

## [ ] Eq. (10a) — First 2-day criterion

Define:

\[
R_{1,\mathrm{rel}}
=
\frac{R_1(T_{BT}=2)}
     {R_1(T_{BT}=7)}
\]

\[
C_{1,\mathrm{rel}}
=
\frac{C_1(T_{BT}=2)}
     {C_1(T_{BT}=7)}
\]

Select \(T_{BT}=2\) if:

\[
R_{1,\mathrm{rel}}>0.99
\quad\text{and}\quad
C_{1,\mathrm{rel}}<0.95
\]

---

## [ ] Eq. (10b) — Second 2-day criterion

Also select \(T_{BT}=2\) if:

\[
R_{1,\mathrm{rel}}<0.95,
\qquad
C_{1,\mathrm{rel}}<0.95,
\]

and

\[
\left|R_{1,\mathrm{rel}}-C_{1,\mathrm{rel}}\right|>0.30
\]

---

## [ ] Eq. (10c) — Selected period

If Eq. (10a) or Eq. (10b) is satisfied:

\[
T_{BT}=2
\]

---

## [ ] Eq. (10d) — Otherwise

\[
T_{BT}=7
\]

**Implementation task**
- Evaluate each building component independently.
- Recompute the final component equivalent parameters using the selected \(T_{BT}\).

---

## [ ] Eq. (10e) — Room aggregation period

For combining individual building components into room-level aggregates:

\[
T_{RA}=5
\]

\[
\omega_{RA}=
\frac{2\pi}{86400\cdot5}
\]

**Important**
- Do not confuse \(T_{BT}\) with \(T_{RA}\).
- \(T_{BT}\): individual component derivation.
- \(T_{RA}\): aggregation of like-loaded components.

---

# C. Multilayer wall assembly — Equation (11)

## [ ] Eq. (11) — Multiply layer matrices

\[
A_{1,n}
=
A_1A_2A_3\cdots A_{n-1}A_n
\]

**Critical implementation rule**
- Multiplication starts with the layer facing the room.
- Layer sequence must not be reversed.

Suggested test:
```python
assert not np.allclose(A1 @ A2, A2 @ A1)
```
for a representative asymmetric multilayer wall.

---

# D. Convert one multilayer component to equivalent \(3R2C\) — Equations (12)–(16)

Let \(a_{ij}\) denote the elements of \(A_{1,n}\).

## [ ] Eq. (12) — \(R_1\)

\[
R_1
=
\frac{1}{A}
\frac{
(\Re a_{22}-1)\Re a_{12}
+
\Im a_{22}\Im a_{12}
}{
(\Re a_{22}-1)^2+(\Im a_{22})^2
}
\]

---

## [ ] Eq. (13) — \(R_2\)

\[
R_2
=
\frac{1}{A}
\frac{
(\Re a_{11}-1)\Re a_{12}
+
\Im a_{11}\Im a_{12}
}{
(\Re a_{11}-1)^2+(\Im a_{11})^2
}
\]

---

## [ ] Eq. (14) — \(C_1\)

\[
C_1
=
A
\frac{
(\Re a_{22}-1)^2+(\Im a_{22})^2
}{
\omega
\left[
\Re a_{12}\Im a_{22}
-
(\Re a_{22}-1)\Im a_{12}
\right]
}
\]

---

## [ ] Eq. (15) — \(C_2\)

\[
C_2
=
A
\frac{
(\Re a_{11}-1)^2+(\Im a_{11})^2
}{
\omega
\left[
\Re a_{12}\Im a_{11}
-
(\Re a_{11}-1)\Im a_{12}
\right]
}
\]

---

## [ ] Eq. (16) — \(R_3\)

\[
R_3
=
\left(
\frac{1}{A}
\sum_{\nu=1}^{n}\frac{s_\nu}{\lambda_\nu}
\right)
-R_1-R_2
\]

Validation:

\[
R_1+R_2+R_3
=
\frac{1}{A}
\sum_{\nu=1}^{n}\frac{s_\nu}{\lambda_\nu}
\]

---

# E. Reduction by loading condition — Equations (17)–(18)

## [ ] Eq. (17) — Corrected capacitance for asymmetric loading

For an asymmetrically loaded building component:

\[
R_w=R_1+R_2+R_3
\]

and the corrected storage capacitance \(C_{1,\mathrm{korr}}\) is calculated from the chain-matrix terms according to Eq. (17).

Implementation requirement:
- Implement Eq. (17) exactly from the standard.
- Unit test against at least one worked numerical construction.
- Keep this as a dedicated function, e.g.
  ```python
  corrected_capacity_asymmetric(...)
  ```

**Model interpretation**
- Symmetric loading: component reduces to \(R_1\) and \(C_1\).
- Asymmetric loading: use the reduced asymmetric equivalent model with \(R_1\), \(C_{1,\mathrm{korr}}\), and remaining through-component resistance.

---

## [ ] Eq. (18) — Surface heat-transfer resistance

\[
R_\alpha
=
\frac{1}{\alpha}
\frac{1}{A}
\]

where:
- \(\alpha\) — surface heat-transfer coefficient \([\mathrm{W/(m^2K)}]\)
- \(A\) — surface area \([\mathrm{m^2}]\)

Used for:
- convection between wall surface and room air,
- radiation between surfaces.

---

# F. Combine identically loaded components — Equations (19)–(24)

These equations are used to combine multiple equivalent components into one room-level IW or AW aggregate.

## [ ] Eq. (19) — Complex impedance of one equivalent component

For component \(\mu\):

\[
Z_{1;IW_\mu}
=
R_{1;IW_\mu}
+
\frac{1}{j\omega_{RA}C_{1;IW_\mu}}
\]

The same principle applies to AW components.

---

## [ ] Eq. (20) — Recover combined-equivalent resistance

\[
R_{1;IW_\mu}
=
\Re\left(Z_{1;IW_\mu}\right)
\]

---

## [ ] Eq. (21) — Recover combined-equivalent capacitance

\[
C_{1;IW_\mu}
=
\frac{1}
{\omega_{RA}\,\Im\left(Z_{1;IW_\mu}\right)}
\]

**Implementation note**
- Confirm sign convention of the imaginary part in code against the standard's \(j\)-convention.

---

## [ ] Eq. (22) — Parallel connection of complex impedances

For \(m\) interior components:

\[
Z_{1;IW}
=
\frac{1}
{
\displaystyle
\sum_{\mu=1}^{m}
\frac{1}{Z_{1;IW_\mu}}
}
\]

Same approach for AW components.

Recommended implementation:
```python
Z_eq = 1.0 / sum(1.0 / Z_i for Z_i in Z_components)
```

---

## [ ] Eq. (23) — Closed-form resistance for two components

For two interior components, calculate the combined real part \(R_{1;IW}\) using Eq. (23).

**Implementation recommendation**
- Prefer the generic complex-impedance calculation from Eq. (22).
- Use Eq. (23) as a regression check against the two-component analytical form.

---

## [ ] Eq. (24) — Closed-form capacitance for two components

For two interior components, calculate the combined \(C_{1;IW}\) using Eq. (24).

**Implementation recommendation**
- Prefer Eq. (22) + Eqs. (20)–(21) generically.
- Use Eq. (24) as a two-component verification test.

**For more than two components**
- Either repeatedly apply Eqs. (23)–(24), or preferably use Eq. (22) directly with complex arithmetic.

---

# G. Windows — Equations (25)–(26)

Windows are included in the asymmetrically loaded AW group but have practically zero storage capacity.

## [ ] Eq. (25) — Equivalent \(R_1\) for an exterior window

\[
R_{1;AF_\nu}
=
\frac{R_{AF_\nu}}{6}
\]

Key point:
- Window heat capacity is taken as approximately zero.
- Window resistance is added later in parallel with the wall-side \(R_1\) contribution.
- The wall heat capacity remains unchanged by the window parallel connection.

---

## [ ] Eq. (26) — Exterior-window thermal resistance

\[
R_{AF_\nu}
=
\left(
\frac{1}{U_{AF_\nu}}
-
\frac{1}{\alpha_{I_\nu}}
-
\frac{1}{\alpha_{A_\nu}}
\right)
\frac{1}{A_{AF_\nu}}
\]

where:
- \(U_{AF_\nu}\) — window U-value \([\mathrm{W/(m^2K)}]\)
- \(\alpha_{I_\nu}\) — internal surface heat-transfer coefficient
- \(\alpha_{A_\nu}\) — external surface heat-transfer coefficient
- \(A_{AF_\nu}\) — window area

Interior windows \(IF_\nu\) are treated analogously.

---

# H. Combined AW resistance — Equations (27)–(28c)

## [ ] Eq. (27) — Total resistance of combined asymmetric components

For combined exterior/asymmetric components:

\[
R_{\mathrm{ges};AW}
=
\frac{1}{
\displaystyle
\sum_{\nu=1}^{n}
U_{AW_\nu}A_{AW_\nu}
+
\sum_{\nu=1}^{n}
U_{AF_\nu}A_{AF_\nu}
}
\]

Includes:
- exterior walls,
- roofs,
- exterior windows,
- non-adiabatic interior components assigned to AW.

---

## [ ] Eq. (28) — Remaining AW resistance

\[
R_{\mathrm{Rest};AW}
=
R_{\mathrm{ges};AW}
-
R_{1;AW}
-
\frac{1}{
\displaystyle
\frac{1}{R_{\alpha;\mathrm{kon};AW}}
+
\frac{1}{R_{\alpha;\mathrm{str};AW/IW}}
}
\]

Interpretation:
- \(R_{\mathrm{Rest};AW}\) is the residual resistance required to preserve the total AW resistance after subtracting the room-side equivalent branch.

---

## [ ] Eq. (28a) — Lower-bound correction condition

If the calculated total AW resistance is smaller than the applicable outside surface resistance:

\[
R_{\mathrm{Rest};AW}
=
R_{\alpha,\mathrm{ges};AW;A}
\]

Implement the exact condition from the standard before assigning this correction.

---

## [ ] Eq. (28b) — Recalculate \(R_{1;AW}\)

When the correction in Eq. (28a) is applied:

\[
R_{1;AW}
=
R_{\mathrm{ges};AW}
-
R_{\mathrm{Rest};AW}
-
\frac{1}{
\displaystyle
\frac{1}{R_{\alpha;\mathrm{kon};AW}}
+
\frac{1}{R_{\alpha;\mathrm{str};AW/IW}}
}
\]

---

## [ ] Eq. (28c) — Numerical floor for \(R_{1;AW}\)

If:

\[
R_{1;AW}<10^{-10}
\]

set:

\[
R_{1;AW}=10^{-10}
\]

**Implementation reason**
- Prevent zero/negative resistance and numerical singularities.

---

# I. Combined long-wave radiative resistance — Equations (29)–(31)

## [ ] Eq. (29) — Combined AW/IW radiative resistance

\[
R_{\alpha;\mathrm{str};AW/IW}
=
\frac{1}{
\displaystyle
\sum_{\nu=1}^{n}
\frac{1}{R_{\alpha;\mathrm{str};AW_\nu}}
+
\sum_{\nu=1}^{n}
\frac{1}{R_{\alpha;\mathrm{str};AF_\nu}}
}
\]

Use this form where the combined IW area is sufficient relative to the AW area.

---

## [ ] Eq. (30) — Radiative heat-transfer coefficient

\[
\alpha_{\mathrm{str}}
=
5.0\ \mathrm{W/(m^2K)}
\]

Also:

\[
\alpha_{\mathrm{kon}}
=
\alpha_{\mathrm{ges}}
-
\alpha_{\mathrm{str}}
\]

Therefore ensure:

\[
\alpha_{\mathrm{ges}}>5.0\ \mathrm{W/(m^2K)}
\]

---

## [ ] Eq. (31) — Alternative combined radiative resistance

If the combined IW surface area is smaller than the combined AW area, including surfaces to adjacent spaces with different temperatures and/or different radiation conditions:

\[
R_{\alpha;\mathrm{str};AW/IW}
=
\frac{1}{
\displaystyle
\sum_{\nu=1}^{n}
\frac{1}{R_{\alpha;\mathrm{str};IW_\nu}}
+
\sum_{\nu=1}^{n}
\frac{1}{R_{\alpha;\mathrm{str};IF_\nu}}
}
\]

**Implementation task**
- Determine which side, AW or IW, limits the effective radiative exchange area.
- Select Eq. (29) or Eq. (31) accordingly.

---

# J. Suggested implementation order

## Phase 1 — Component physics
- [ ] Implement material-layer object.
- [ ] Implement \(R=s/\lambda\), \(C=c\rho s\).
- [ ] Implement \(\omega(T)\).
- [ ] Implement Eqs. (3)–(8).
- [ ] Implement Eq. (11) matrix multiplication.
- [ ] Implement Eqs. (12)–(16).
- [ ] Implement Eqs. (10a)–(10d) period selection.
- [ ] Implement Eq. (17).
- [ ] Implement Eq. (18).

## Phase 2 — Classification
- [ ] Classify each component as symmetric \(IW\) or asymmetric \(AW\).
- [ ] Treat windows as AW components with negligible capacitance.
- [ ] Preserve component orientation and boundary conditions.

## Phase 3 — Room aggregation
- [ ] Set \(T_{RA}=5\) days.
- [ ] Implement Eqs. (19)–(22) with complex impedance.
- [ ] Validate against Eqs. (23)–(24).
- [ ] Implement window parallel resistance, Eqs. (25)–(26).
- [ ] Implement combined AW resistance, Eq. (27).
- [ ] Implement Eqs. (28)–(28c).
- [ ] Implement radiative resistance Eqs. (29)–(31).

## Phase 4 — Final 7R2C network output
Expected room-level parameters after Eq. (31):

### AW branch
- [ ] \(R_{\mathrm{Rest};AW}\)
- [ ] \(R_{1;AW}\)
- [ ] \(C_{1;AW}\)
- [ ] room-side convective/radiative resistance terms

### IW branch
- [ ] \(R_{1;IW}\)
- [ ] \(C_{1;IW}\)
- [ ] room-side radiative resistance terms

### Air branch
- [ ] ventilation/air coupling resistance handled separately in the room equations

---

# K. Minimum validation tests

- [ ] Single homogeneous layer: compare chain-matrix coefficients against hand calculation.
- [ ] Multilayer wall: verify matrix multiplication order.
- [ ] Check \(R_1+R_2+R_3=R_{\mathrm{steady}}\).
- [ ] Verify automatic \(T_{BT}=2/7\) selection.
- [ ] Symmetric component: verify reduction to \(R_1,C_1\).
- [ ] Asymmetric component: verify \(C_{1,\mathrm{korr}}\).
- [ ] Window: verify \(C\approx0\) and Eq. (25)/(26) resistance.
- [ ] Two identical walls: compare Eq. (22) with closed forms Eqs. (23)–(24).
- [ ] More than two components: verify order-independent complex parallel aggregation.
- [ ] Verify Eq. (27) against direct \(UA\) summation.
- [ ] Check positivity and numerical floor from Eq. (28c).
- [ ] Verify Eq. (29)/(31) branch selection based on AW/IW area.

---

## Boundary of this checklist

Stop after Equation (31).

Not included:
- Eq. (32)+ equivalent outdoor temperature,
- solar/long-wave environmental boundary calculations,
- room heat-gain allocation,
- HVAC equations,
- time integration / solver implementation.
