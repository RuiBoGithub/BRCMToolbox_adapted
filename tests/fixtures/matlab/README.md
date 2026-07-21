# MATLAB reference fixtures

This directory intentionally contains no fabricated reference values.

Generate the fixtures from the repository root with:

```matlab
addpath(fullfile(pwd, 'origin_matlab', 'parity'))
export_brcm_reference()
```

Or from a shell using a MATLAB release with `-batch` support:

```bash
matlab -batch "addpath(fullfile(pwd,'origin_matlab','parity')); export_brcm_reference()"
```

The exporter writes numeric MATLAB v7 MAT files plus JSON metadata and loaded
thermal-model data. It never saves BRCM MATLAB class instances.
