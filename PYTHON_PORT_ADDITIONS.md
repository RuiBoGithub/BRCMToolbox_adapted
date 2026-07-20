# Python Port Additions

The original MATLAB BRCM Toolbox remains unchanged. A Python implementation and validation layer have been added around it.

## What was added

- Thermal-data records, CSV/Excel loading, validation, and parameter expressions
- Thermal RC generation: `A`, `Bq`, `Xcap`, state identifiers, and boundaries
- Five EHF models: Internal Gains, Radiators, TABS, Building Hull, and AHU
- Full `BuildingModel` composition, constraints, costs, and discretization
- Thermal and bilinear building simulation
- Legacy EnergyPlus IDF/IDD parsing and conversion to the seven BRCM tables
- Direct in-memory API: `brcm.from_energyplus(...)`
- Conversion audit reports and deterministic IDF fixtures
- MATLAB parity hooks, unit/integration tests, and an operator notebook

Current validation status:

```text
116 passed, 15 skipped
```

The skipped tests require MATLAB-generated reference fixtures. MATLAB numerical parity and EnergyPlus predictive equivalence are not yet claimed.

## Python-related folders

```text
BRCMToolbox_v1.03/
├── src/
│   └── brcm/                  # Main Python package
│       ├── energyplus/        # IDF parsing, normalization, conversion and audits
│       ├── ehf/               # External Heat Flux models
│       ├── building_model.py  # Full model composition and discretization
│       ├── simulation.py      # Thermal and BuildingModel simulation
│       ├── thermal_data.py    # Seven-table data repository
│       ├── thermal_generation.py
│       └── thermal_model.py
├── tests/
│   ├── unit/                  # Focused Python unit tests
│   ├── integration/           # End-to-end EnergyPlus → RC tests
│   ├── parity/                # Optional MATLAB comparison tests
│   └── fixtures/
│       ├── energyplus/        # Deterministic IDF fixtures
│       └── matlab/            # MATLAB references when generated
├── notebooks/
│   └── BRCM_EnergyPlus_End_to_End.ipynb
│                              # Operator walkthrough
├── export_brcm_reference.m    # Exports portable MATLAB reference fixtures
└── PYTHON_PORT_ADDITIONS.md   # This summary
```

## Basic use

```python
import brcm

thermal_model = brcm.from_energyplus("building.idf")
```

For conversion details and warnings:

```python
result = brcm.convert_idf_to_brcm_data("building.idf")
model = brcm.from_energyplus("building.idf")
audit = brcm.audit_conversion(result, model)
```

Run tests:

```bash
PYTHONPATH=src pytest -q
```

Open the operator notebook:

```bash
jupyter lab notebooks/BRCM_EnergyPlus_End_to_End.ipynb
```

## Important notes

- Building north rotation is ignored to match the original MATLAB behavior.
- Zone north rotation and zone-origin translation are applied for relative coordinates.
- Identifier and table ordering must be preserved.
- Supported IDDs are EnergyPlus 7.0–8.1; later 8.x files use the 8.1 IDD with a warning.
- Unsupported thermal EnergyPlus objects fail explicitly.
- Sparse optimization and modern EnergyPlus feature expansion have not been added.
