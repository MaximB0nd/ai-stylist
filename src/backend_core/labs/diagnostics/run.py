"""Diagnose retry classification without contacting external dependencies."""

import gc
import importlib.util
import json
import platform
import sys
import tracemalloc
from pathlib import Path

ROOT = next(
    p for p in Path(__file__).resolve().parents if (p / "src/backend_core").is_dir()
)
sys.path.insert(0, str(ROOT / "src/backend_core"))
from dotenv import load_dotenv

load_dotenv(ROOT / "src/backend_core/.env.test")
from sqlalchemy.exc import IntegrityError, ProgrammingError, OperationalError
from app.services.ai_core_client import AICoreError
from app.services import retry_policy as original

BASE = Path(__file__).parent
spec = importlib.util.spec_from_file_location(
    "policy_before", BASE / "policy_before.py"
)
before = importlib.util.module_from_spec(spec)
spec.loader.exec_module(before)
module = original
original = before
cases = [
    ("AI503", AICoreError("unavailable", status_code=503), True),
    ("AI400", AICoreError("bad request", status_code=400), False),
    ("DBIntegrity", IntegrityError("insert", {}, Exception("constraint")), False),
    ("DBProgramming", ProgrammingError("select", {}, Exception("syntax")), False),
    ("DBOperational", OperationalError("select", {}, Exception("connection")), True),
]
result = {"python": platform.python_version(), "versions": {}}
for name, m in [("before", original), ("after", module)]:
    rows = []
    tracemalloc.start()
    gc.collect()
    start = tracemalloc.get_traced_memory()[0]
    for _ in range(200):
        for label, error, expected in cases:
            m.is_retryable_delivery_error(error)
    gc.collect()
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    for label, error, expected in cases:
        actual = m.is_retryable_delivery_error(error)
        rows.append(
            dict(
                case=label, expected=expected, actual=actual, passed=expected == actual
            )
        )
    result["versions"][name] = {
        "cases": rows,
        "retained_delta": current - start,
        "peak_bytes": peak,
    }
    print(name, rows, "retained_delta", current - start, "peak", peak)
# This regression is a genuine failure against the unmodified policy.
regression_before = not original.is_retryable_delivery_error(cases[2][1])
regression_after = not module.is_retryable_delivery_error(cases[2][1])
assert not regression_before and regression_after
result["regression"] = {"before": regression_before, "after": regression_after}
(BASE / "local-diagnostic.json").write_text(json.dumps(result, indent=2))
if len(sys.argv) > 1:
    target = original if sys.argv[1] == "before" else module
    assert not target.is_retryable_delivery_error(cases[2][1]), (
        "Permanent integrity violation must not be retried unchanged"
    )
