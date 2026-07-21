Source IDF: _simp.idf
MATLAB SHA256: 2319b9c1033ad5cd5797e43a0a971d8ffa7f4410fe05fedd374eb36d7b668c37
Python SHA256: 2319b9c1033ad5cd5797e43a0a971d8ffa7f4410fe05fedd374eb36d7b668c37
Same input file: PASS

# `_simp.idf` Operational Parity

1. Seven-table parity: FAIL
   - zones: PASS
   - buildingelements: PASS
   - constructions: FAIL — row 3, column 'thickness': MATLAB='0.1015', Python='0.1014984'
   - materials: PASS
   - windows: PASS
   - parameters: FAIL — row 3, column 'description': MATLAB='Convective coefficient of ceiling to zone (default, considering thermal radiation)', Python='Convective coefficient of CeilingInt (default, considering thermal radiation)'
   - nomassconstructions: PASS
2. Identifier parity: PASS
3. Boundary parity: FAIL
4. A parity: FAIL
   - Shape equality: PASS; max abs: 1.5784572856680085e-09; max rel: 1.7780328168800527e-05; mismatches: 4; nonzero-pattern mismatches: 0
5. Bq parity: PASS
   - Shape equality: PASS; max abs: 3.5633150796408647e-13; max rel: 1.5763546798060153e-05; mismatches: 0; nonzero-pattern mismatches: 0
6. Xcap parity: FAIL
   - Shape equality: PASS; max abs: 697.3655689582229; max rel: 1.5763546797954203e-05; mismatches: 1; nonzero-pattern mismatches: 0
7. Simulation parity: FAIL
   - Maximum absolute trajectory error: 9.961595317520278e-07
   - Maximum per-state RMSE: 5.580384510658688e-07
   - Maximum final-state error: 9.961595317520278e-07
   - Time vector: PASS
   - Deterministic x0/Q/Ts/N: PASS
8. Overall FAIL

First mismatch: Table constructions: row 3, column 'thickness': MATLAB='0.1015', Python='0.1014984'
