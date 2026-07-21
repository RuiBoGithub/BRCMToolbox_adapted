Source IDF: _simp.idf
MATLAB SHA256: 2319b9c1033ad5cd5797e43a0a971d8ffa7f4410fe05fedd374eb36d7b668c37
Python SHA256: 6002f5da51bcd7ee390db08f7df2276e5f0ddee81c01f78f7f140bdb008bcebc
Same input file: FAIL

# `_simp.idf` Operational Parity

1. Seven-table parity: FAIL
   - zones: FAIL
   - buildingelements: FAIL
   - constructions: FAIL
   - materials: FAIL
   - windows: FAIL
   - parameters: FAIL
   - nomassconstructions: FAIL
2. Identifier parity: FAIL
3. Boundary parity: FAIL
4. A parity: FAIL
5. Bq parity: FAIL
6. Xcap parity: FAIL
7. Simulation parity: FAIL
8. Overall FAIL

## Traced construction thickness

- Source: `Material, C5 - 4 IN HW CONCRETE`, `Thickness` (line 223): `0.1014984 m`
- MATLAB normalized: `0.1014984`; written/reloaded: `0.1015`
- Python generated/reloaded: `0.1015`
- Classification: workflow quantization (bare MATLAB `num2str(value)` in construction-sheet generation)
- RC matrices affected before fix: YES

First mismatch: Source IDF SHA-256 differs
