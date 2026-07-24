# BRCM notebook outputs

This directory contains the files produced or consumed by
`BRCM_EnergyPlus_23_2_Best_Current.ipynb`.

## Export inventory

`1ZoneUncontrolled1/brcm_export/` is the explicit EnergyPlus-to-BRCM export:

| File | Exported information | Rows |
| --- | --- | ---: |
| `zones.csv` | Zone identifier, name, floor area, volume, group | 1 |
| `buildingelements.csv` | Surface mapping, construction, adjacency/boundary, window link, area, 3-D vertices | 6 |
| `constructions.csv` | Material layers, thicknesses, inside/outside convection parameter links | 3 |
| `materials.csv` | Heat capacity, thermal resistivity, density, or resistance | 3 |
| `windows.csv` | Parent surface, glass/frame areas, U-value and SHGC parameter links | 1 |
| `parameters.csv` | Default convection coefficients and window-property parameters | 7 |
| `nomassconstructions.csv` | No-mass construction U-values | 0 |

The converted geometry is complete for this case: one zone, four walls, one
floor, one roof, and one 10 m² window. Every building element has an area and
polygon vertices. The zone has an area of 232.2576 m² and a volume of
1061.881747 m³.

The fabric export includes the massive concrete floor and the resistance-only
wall and roof layers. It produces two RC states: zone air and one concrete-floor
layer state. The massless wall and roof layers correctly do not create storage
states.

## Information located outside the seven core tables

- `1ZoneUncontrolled1/ehf/` contains the notebook-created building-hull and
  internal-gain mappings.
- `1ZoneUncontrolled1/1ZoneUncontrolled1/` contains the main EnergyPlus output,
  including time-series CSV/MTR results, diagnostics, geometry DXF and the EIO
  component summary.
- `1ZoneUncontrolled1/seasonal/` contains the January, April, July and October
  EnergyPlus comparison runs.
- Plot and table results are embedded in the executed notebook.

## Important limitation

The core converter cannot derive detailed glazing-system performance from the
EnergyPlus construction and therefore exports placeholder window parameters
(`U=1 W/m²K`, `SHGC=0.5`). The best-current notebook locates the effective
assembly values in `eplusout.eio` and uses `U=3.798 W/m²K` and `SHGC=0.684`
during its comparison. These corrected values are diagnostic adjustments in the
notebook, not replacements in the canonical seven exported tables.

No EnergyPlus object types were ignored and the conversion emitted no warnings
for this model.
