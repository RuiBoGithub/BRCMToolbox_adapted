# MATLAB end-to-end validation

This folder runs the original BRCM MATLAB implementation through the same conceptual workflow as `notebooks/BRCM_EnergyPlus_End_to_End.ipynb`.

The directly comparable Python exporter is `notebooks/BRCM_Python_MATLAB_Comparable_Validation.ipynb`. Both are pinned by default to the same IDF:

```text
tests/fixtures/energyplus/representative_multizone.idf
```

The validation code is additive. It does not modify the original MATLAB toolbox.

## Default run

From the repository root:

```bash
matlab -batch "addpath('matlab_validation'); run_brcm_end_to_end()"
```

The default IDF is:

```text
tests/fixtures/energyplus/representative_multizone.idf
```

The default output directory is:

```text
matlab_validation/outputs/
```

## Explicit paths

```bash
matlab -batch "addpath('matlab_validation'); run_brcm_end_to_end('tests/fixtures/energyplus/representative_multizone.idf','matlab_validation/outputs')"
```

Absolute paths are also accepted.

## Workflow

```text
EnergyPlus IDF
  → convertIDFToBRCM
  → load and export seven BRCM tables
  → generate ThermalModel and empty-EHF BuildingModel
  → discretize at 1/60 hour
  → run deterministic 60-step thermal simulation
  → repeat simulation to verify determinism
  → write manifest and portable outputs
```

The IDF does not contain BRCM EHF declarations, so the generated BuildingModel has zero `u`, `v`, `y`, and constraint dimensions. Its matrices are still exported. EHF parity requires separate, identical MATLAB and Python declaration files.

## Simulation convention

The validation uses:

- initial temperature: `20 °C`
- ambient temperature: `30 °C`
- direct zone heating: `0 W`
- sample time: `1/60 h`
- steps: `60`

For every ambient boundary:

```text
q = G × (Tamb − T_boundary_state)
```

Although the `BoundaryCondition.m` property comment says “Resistance,” `generateThermalModel.m` assigns `value = 1 / total_resistance` and inserts it directly into the conductance matrix. Therefore the stored value used here is conductance `G` in W/K.

MATLAB's simulation engine returns `X` with `N` columns. The validation also exports reconstructed `X_full` with `N+1` columns using the same final discrete update.

## Outputs

```text
outputs/
├── manifest.json
├── model_config/
│   ├── metadata.json
│   ├── identifiers.json
│   ├── boundary_conditions.json
│   ├── matrix_axes.json
│   ├── constraint_identifiers.json
│   ├── initial_state.mat
│   ├── generated_brcm/       # Direct convertIDFToBRCM output
│   └── tables/               # Seven semicolon-delimited CSV tables
├── matrices/
│   ├── thermal_model.mat
│   ├── building_continuous.mat
│   ├── building_discrete.mat
│   └── constraints_cost.mat
└── simulation/
    ├── simulation_config.json
    ├── simulation_inputs.mat
    ├── simulation_results.mat
    └── simulation_summary.json
```

`manifest.json` records stage PASS/FAIL status, MATLAB and EnergyPlus versions, IDD choice, dimensions, output filenames, warnings, errors, and simulation settings.

## Current compatibility notes

- Building north rotation is ignored by the original MATLAB EP2BRCM conversion.
- Zone origin and zone north are applied for relative coordinates.
- EnergyPlus 8.x versions newer than 8.1 use the bundled 8.1 IDD with a warning.
- Exact MATLAB-vs-Python parity is established only after these outputs are compared with matching Python exports.
