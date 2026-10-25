"""Actual Google Harness² core, with deterministic editors and fictive MaaS ledgers."""
import json
from pathlib import Path
from harness2.core.schedule import run_domain
from harness2.demo import DemoAdapter, DemoProposer

root = Path("/artifacts/harness2")
adapter = DemoAdapter(root)
fixtures = {"ledger-1": ("amount\n12.00\n-2.00\n", "Total: 10.00\n"), "ledger-2": ("amount\n3.00\n-0.15\n", "Total: 2.85\n")}
for task, (source, _) in fixtures.items():
    (adapter.task_files(task) / "ledger.csv").write_text(source)
proposer = DemoProposer(adapter.spec.channels["proposer"])
result = run_domain("accounting", adapter.tasks(), 1, adapter=adapter, prop=proposer, runs_root=adapter.spec.runs_root, library_root=root / "library/k1", modes=("agg", "seq"))
assert result["failed"] == 0, result
for task, (_, expected) in fixtures.items():
    summary = json.loads((adapter.spec.runs_root / "demo-oc-agg1" / task / "summary.json").read_text())
    for mode in ("agg", "seq"):
        chosen = Path(summary["selections"][mode]["chosen_run_dir"])
        assert adapter.deliverable_text(chosen) == expected
report = {"status": "passed", "upstream": "google-research/harness2", "commit": "1cfe254e8d25b15f37048c3730134686abe60335", "editors": "deterministic_test_double_no_LLM", "modes": ["parallel", "sequential"], "tasks": 2, "production_adoption": False, "result": result}
(root / "maas-report.json").write_text(json.dumps(report, indent=2))
print(json.dumps({k: v for k, v in report.items() if k != "result"}, indent=2))
