import json
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[3]
SCRIPTS = REPO / "ci" / "quality-gates" / "scripts"
CONFIG = REPO / "ci" / "quality-gates" / "config" / "quality-gates.json"


class QualityGateScriptTests(unittest.TestCase):
    def test_qor_summary_script_generates_expected_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            reports = Path(tmp) / "reports"
            cmd = ["python3", str(SCRIPTS / "generate_qor_summary.py"), "--config", str(CONFIG), "--reports-dir", str(reports)]
            subprocess.run(cmd, cwd=REPO, check=True)

            data = json.loads((reports / "qor_summary.json").read_text())
            self.assertIn("designs", data)
            self.assertTrue(any(d["design"] == "nanocgra_lite" for d in data["designs"]))
            self.assertTrue(all("timing" in d and "area" in d and "power" in d for d in data["designs"]))

    def test_cdc_reset_script_runs_and_writes_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            reports = Path(tmp) / "reports"
            cmd = ["python3", str(SCRIPTS / "run_cdc_reset_heuristics.py"), "--config", str(CONFIG), "--reports-dir", str(reports)]
            subprocess.run(cmd, cwd=REPO, check=False)

            report = reports / "cdc_reset_report.json"
            self.assertTrue(report.exists())
            data = json.loads(report.read_text())
            self.assertIn("limitations", data)
            self.assertIn("files_scanned", data)


if __name__ == "__main__":
    unittest.main()
