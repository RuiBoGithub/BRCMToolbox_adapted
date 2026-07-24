# Shared 5R1C/BRCM workflow experiment

This prototype parses an EnergyPlus IDF once through `brcm`, derives a common
physical data object, and passes that same object to:

- `generate_5R1C()` for the fixed ISO 13790/ETHlib topology;
- `generate_BRCM()` for the detailed multi-node BRCM thermal network.

The existing JSON convention is retained as an overlay for assumptions that
cannot yet be obtained reliably from the IDF, including ventilation/control
defaults and corrected glazing performance. IDF-derived geometry and fabric
remain the default source.

Run from the repository root:

```bash
PYTHONPATH=src:. python3 brcm_5r1c_workflow/example.py
```

The audit is written to `outputs/model_pair_audit.json`.

The companion notebook `BRCM_5R1C_Workflow.ipynb` documents the provenance of
every shared parameter and maintains an explicit ETHlib substitution register.

## Implemented

1. One EnergyPlus/IDD parse for zones, surfaces, constructions, materials,
   windows and schedule inventory.
2. Common normalized structure with areas, volumes, envelope conductance,
   material heat capacity, air-change assumptions and boundary counts.
3. Fixed 5R1C parameter aggregation matching the coefficients used by
   `RC_br/ETHlib/building_physics.py`.
4. Detailed BRCM thermal-model generation from the same conversion result.
5. Machine-readable topology and parameter audit.

## Next integration boundary

Weather, solar gains, internal gains, controls and HVAC must be represented as
one explicit forcing contract before simulation comparisons are meaningful.
BRCM requires its EHF mappings while ETHlib currently builds gains and controls
inside its annual loop. The next step is therefore a shared hourly
`ForcingFrame` adapter feeding both solvers. Calibration and ECM comparisons
should be added only after that forcing-equivalence test passes.
