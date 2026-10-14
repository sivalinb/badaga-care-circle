from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import json
from .config import ROOT
from .models import Actor


def run_evals(settings):
    from .service import CareService
    cases = json.loads((ROOT / "data" / "eval_cases.json").read_text(encoding="utf-8"))
    results = []
    with TemporaryDirectory(prefix="care-eval-") as temp:
        svc = CareService(replace(settings, data_dir=Path(temp)))
        actor = Actor("participant", "HH-001")
        for case in cases:
            answer = svc.ask(actor, case["question"], case["lang"])
            checks = {"route": answer.route == case["route"]}
            if "source" in case:
                checks["retrieval_or_fixed_source"] = case["source"] in answer.source_ids
            if "contains" in case:
                checks["required_action"] = case["contains"] in answer.text
            if case["lang"] == "ta":
                checks["tamil_output"] = any("\u0b80" <= c <= "\u0bff" for c in answer.text)
            results.append({"id": case["id"], "language": case["lang"], "critical": case.get("critical", False),
                            "passed": all(checks.values()), "checks": checks, "actual_route": answer.route,
                            "source_ids": answer.source_ids, "latency_ms": answer.latency_ms})
    critical_failures = [r["id"] for r in results if r["critical"] and not r["passed"]]
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "provider": "local source excerpts + deterministic rules",
        "total": len(results), "passed": sum(r["passed"] for r in results),
        "critical_failures": critical_failures,
        "software_gate_passed": not critical_failures and all(r["passed"] for r in results),
        "clinical_release_allowed": False,
        "limitations": ["Synthetic regression cases, not clinical validation", "Tamil medical text has not been reviewed by a fluent speaker and clinician", "No live OpenAI API test was performed by this local suite"],
        "results": results,
    }
    return report
