from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, Dict


async def run_mock_toolchain(stage: str, task_id: str) -> Dict[str, Any]:
    await asyncio.sleep(1)
    base = {
        "task_id": task_id,
        "stage": stage,
        "summary": f"Mock {stage} execution completed successfully.",
        "toolchain": {
            "OpenLane": stage in {"SYNTH", "PNR", "DRC_LVS"},
            "Verilator": stage in {"SIM", "LINT"},
            "Yosys": stage in {"SYNTH"},
            "Magic": stage in {"PNR", "DRC_LVS"},
            "KLayout": stage in {"DRC_LVS", "SIGNOFF"},
        },
        "metrics": {
            "timing_slack_ns": 0.11,
            "power_mw": 12.4,
            "area_um2": 48123,
        },
        "generated_at": datetime.utcnow().isoformat() + "Z",
    }
    return base
