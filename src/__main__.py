"""CLI: python -m src --input data/sample_input.json [--dry-run] [--output out.json]"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .discovery_engine import ROOT, load_dotenv, run


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(
        description="Analyze Google Photos search feedback with structured IR/UX taxonomy."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=ROOT / "data" / "sample_input.json",
        help="Path to feedback posts JSON array",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Write validated analysis JSON to this path",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate sample output against schema (no API call)",
    )
    args = parser.parse_args()

    try:
        result = run(args.input, dry_run=args.dry_run, output_path=args.output)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if not args.output:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
