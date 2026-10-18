#!/usr/bin/env python3
"""Checks the generated schemas are valid JSON Schema, and that each one still rejects something.

A schema that accepts everything is worse than no schema, because it looks like a control. So as
well as the meta-schema check, each package schema is given an instance carrying a field the model
does not have, and must reject it.

Needs jsonschema, which the other scripts do not:

    python3 -m venv .venv && .venv/bin/pip install jsonschema
    .venv/bin/python scripts/validate_schemas.py
"""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCHEMAS = ROOT / "schemas"

try:
    from jsonschema import Draft202012Validator
except ImportError:
    print("jsonschema is not installed; skipping (see the docstring)", file=sys.stderr)
    sys.exit(0)


def main():
    files = sorted(f for f in SCHEMAS.glob("*.json") if f.name != "build-report.json")
    failures = []
    for f in files:
        schema = json.loads(f.read_text())
        try:
            Draft202012Validator.check_schema(schema)
        except Exception as e:
            failures.append((f.name, f"not valid draft 2020-12: {str(e)[:120]}"))
            continue
        v = Draft202012Validator(schema)
        if not list(v.iter_errors({"thisFieldIsNotInTheWcoDataModel": True})):
            failures.append((f.name, "accepts a field the model does not have"))

    print(f"{len(files)} schemas checked")
    if failures:
        print(f"\n{len(failures)} failed:")
        for name, why in failures:
            print(f"  {name}: {why}")
        return 1
    print("all valid, and all reject an unknown field")
    return 0


if __name__ == "__main__":
    sys.exit(main())
