import argparse
import json
from pathlib import Path
from .config import Settings
from .evals import run_evals


def main():
    parser = argparse.ArgumentParser(description="Badaga Care Circle developer commands")
    sub = parser.add_subparsers(dest="command", required=True)
    evaluation = sub.add_parser("eval", help="Run synthetic offline regression cases")
    evaluation.add_argument("--output", type=Path, default=Path("evaluation_report.json"))
    sub.add_parser("preflight", help="Check whether this release can be used for a clinical pilot")
    args = parser.parse_args()
    settings = Settings.from_env()
    if args.command == "eval":
        report = run_evals(settings)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2))
        print(f"{report['passed']}/{report['total']} software regression cases passed.")
        print("Clinical release remains blocked; see ROADMAP.md.")
        raise SystemExit(0 if report["software_gate_passed"] else 1)
    print(json.dumps({
        "clinical_release_allowed": False,
        "blockers": ["Source and Tamil medical-text approvals", "Validated clinical workflows and staffed referrals",
                     "Verified identity and server-side access control", "Encrypted clinical storage and retention policy",
                     "Bilingual usability and supervised field evaluation"],
    }, indent=2))
    raise SystemExit(2)


if __name__ == "__main__":
    main()
