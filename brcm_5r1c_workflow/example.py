"""Generate both models from the repository's EnergyPlus 23.2 example."""

from pathlib import Path
import sys

ROOT = next(parent for parent in (Path.cwd(), *Path.cwd().parents) if (parent / "src" / "brcm").is_dir())
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]

from brcm_5r1c_workflow.workflow import generate_model_pair, write_audit

HERE = ROOT / "brcm_5r1c_workflow"
pair = generate_model_pair(
    ROOT / "_E+" / "1ZoneUncontrolled1.idf",
    idd_path=ROOT / "_E+" / "idd" / "23.2" / "Energy+.idd",
    defaults_json=HERE / "config" / "5r1c_defaults.json",
)
output = write_audit(pair, HERE / "outputs" / "model_pair_audit.json")
print(f"Wrote {output}")
print(f"5R1C: C={pair.five_r1c.c_m_j_k:.3g} J/K, envelope H={pair.five_r1c.h_tr_em_w_k + pair.five_r1c.h_tr_w_w_k:.3g} W/K")
print(f"BRCM: {len(pair.brcm_model.state_identifiers)} states: {pair.brcm_model.state_identifiers}")
