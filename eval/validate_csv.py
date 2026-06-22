#!/usr/bin/env python3
"""Validate an ablation_result CSV against eval/schema/ablation_result.schema.json.

stdlib-only (no jsonschema dependency required) so it runs in any environment and
in CI before the Python toolchain is fully provisioned. Enforces required keys,
no extra keys (additionalProperties:false), and enum constraints. Exits non-zero
on the first batch of violations.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCHEMA = ROOT / "eval" / "schema" / "ablation_result.schema.json"


def validate(csv_path: Path, schema_path: Path = DEFAULT_SCHEMA) -> list[str]:
    schema = json.loads(Path(schema_path).read_text())
    required = set(schema["required"])
    props = schema["properties"]
    allowed = set(props)
    enums = {k: set(v["enum"]) for k, v in props.items() if "enum" in v}
    errors: list[str] = []

    with Path(csv_path).open(newline="") as f:
        reader = csv.DictReader(f)
        headers = set(reader.fieldnames or [])
        if missing := required - headers:
            errors.append(f"header: missing columns {sorted(missing)}")
        if extra := headers - allowed:
            errors.append(f"header: unexpected columns {sorted(extra)}")
        if errors:
            return errors  # header broken: row checks would be noise

        for i, rrow in enumerate(reader, start=2):  # line 2 = first data row
            keys = {k for k, v in rrow.items() if v is not None}
            if missing := required - keys:
                errors.append(f"row {i}: missing {sorted(missing)}")
            for col, vals in enums.items():
                if rrow.get(col) not in vals:
                    errors.append(f"row {i}: {col}={rrow.get(col)!r} not in {sorted(vals)}")
            for col, spec in props.items():  # schema-driven non-empty (minLength>=1)
                if spec.get("minLength", 0) >= 1 and not (rrow.get(col) or "").strip():
                    errors.append(f"row {i}: {col} is empty")
    return errors


def main(argv=None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if not args:
        print("usage: validate_csv.py <ablation_result.csv> [schema.json]", file=sys.stderr)
        return 2
    csv_path = Path(args[0])
    schema_path = Path(args[1]) if len(args) > 1 else DEFAULT_SCHEMA
    errs = validate(csv_path, schema_path)
    if errs:
        print(f"INVALID: {csv_path} ({len(errs)} error(s))", file=sys.stderr)
        for e in errs:
            print(f"  - {e}", file=sys.stderr)
        return 1
    print(f"OK: {csv_path} conforms to {schema_path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
