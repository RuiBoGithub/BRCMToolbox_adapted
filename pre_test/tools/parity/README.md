# Operational parity cases

A case name resolves to `pre_test/tests/fixtures/energyplus/<case>.idf` and
`pre_test/outputs/parity/<case>/`. Case names may contain letters, digits,
underscores, dots, and hyphens, but may not contain path separators.

From the repository root, export and compare one case with:

```matlab
addpath(fullfile(pwd, 'origin_matlab', 'parity'));
export_case_reference('_simp');
```

```bash
python pre_test/tools/parity/run_python_reference.py --case _simp
python pre_test/tools/parity/compare_parity.py --case _simp
```

The same commands accept any fixture stem, for example:

```matlab
export_case_reference('two_zone_interzone');
```

```bash
python pre_test/tools/parity/run_python_reference.py --case two_zone_interzone
python pre_test/tools/parity/compare_parity.py --case two_zone_interzone
```
