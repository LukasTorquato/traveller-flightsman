"""Convert observations.jsonl to an Excel workbook with two sheets."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import openpyxl


def main(src: Path, dst: Path) -> int:
    if not src.is_file():
        print(f"source file not found: {src}", file=sys.stderr)
        return 2
    observations: list[dict] = []
    run_metadata: list[dict] = []
    for line in src.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("kind") == "run_metadata":
            run_metadata.append(row)
        else:
            observations.append(row)
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for sheet_name, rows in (("observations", observations), ("run_metadata", run_metadata)):
        ws = wb.create_sheet(sheet_name)
        if not rows:
            continue
        headers = list(rows[0].keys())
        ws.append(headers)
        for r in rows:
            ws.append([_coerce(r.get(h)) for h in headers])
    wb.save(dst)
    return 0


def _coerce(v):
    if isinstance(v, list):
        return json.dumps(v)
    return v


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("usage: jsonl_to_xlsx.py <src.jsonl> <dst.xlsx>", file=sys.stderr)
        sys.exit(2)
    sys.exit(main(Path(sys.argv[1]), Path(sys.argv[2])))
