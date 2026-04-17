from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="traveller", description="Weekly DUB deal scanner")
    parser.add_argument(
        "--config-dir",
        default="config",
        help="Path to config directory (default: ./config)",
    )
    parser.add_argument(
        "--history",
        default="history/observations.jsonl",
        help="Path to JSONL history (default: history/observations.jsonl)",
    )
    parser.add_argument(
        "--reports-dir",
        default="reports",
        help="Path to reports output dir (default: reports)",
    )
    parser.add_argument(
        "--state",
        default="state/rotation.json",
        help="Rotation state path (default: state/rotation.json)",
    )
    parser.add_argument(
        "--email-output",
        default="output/email.json",
        help="Email envelope output path (default: output/email.json)",
    )
    sub = parser.add_subparsers(dest="command", required=False)
    sub.add_parser("run", help="Execute one weekly scan")
    args = parser.parse_args(argv)

    # Default command is "run" if none given
    if args.command in (None, "run"):
        from traveller.orchestrator import run_scan

        report, envelope = run_scan(
            config_dir=Path(args.config_dir),
            history_path=Path(args.history),
            reports_dir=Path(args.reports_dir),
            state_path=Path(args.state),
            email_output_path=Path(args.email_output),
        )
        deals = [o for o in report.outcomes if o.flag and o.flag.is_deal]
        print(f"Scan complete. {len(deals)} deal(s); envelope at {envelope}")
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
