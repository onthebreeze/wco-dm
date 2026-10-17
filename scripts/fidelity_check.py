#!/usr/bin/env python3
"""Reads the two workbooks again, independently of extract.py, and checks that nothing was lost on
the way to the intermediate. A pipeline that only compares its own output to itself proves nothing.

    python3 scripts/fidelity_check.py
"""
import json
import pathlib
import sys

import openpyxl

ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW, INT = ROOT / "raw-data", ROOT / "intermediate"


def main():
    failures = []

    wb = openpyxl.load_workbook(RAW / "1.1 WCO DM LIB V4.3.0.xlsx", read_only=True, data_only=True)
    ws = wb["DataSet 1.2, 1.3, 1.4"]
    raw_rows = [r for r in ws.iter_rows(min_row=3, values_only=True) if r[8]]
    raw_classes = {str(r[8]).strip() for r in raw_rows}
    raw_attrs = [r for r in raw_rows if r[9]]
    raw_dens = {str(r[19]).strip() for r in raw_rows if r[19]}
    raw_codelists = len([r for r in wb["DataSet 1.6"].iter_rows(min_row=3, values_only=True) if r[1]])
    wb.close()

    wb = openpyxl.load_workbook(RAW / "WCO DM OIS_V4.3.0.xlsx", read_only=True, data_only=True)
    raw_ois = len([r for r in wb["OIS"].iter_rows(min_row=4, values_only=True) if r[1]])
    wb.close()

    classes = json.loads((INT / "classes.json").read_text())
    attributes = json.loads((INT / "attributes.json").read_text())
    code_lists = json.loads((INT / "code-lists.json").read_text())
    ois = json.loads((INT / "ois-occurrences.json").read_text())

    def check(label, got, want):
        print(f"  {label}: {got} against {want}" + ("" if got == want else "   MISMATCH"))
        if got != want:
            failures.append(label)

    check("classes", len(classes), len(raw_classes))
    check("attributes", len(attributes), len(raw_attrs))
    check("code lists", len(code_lists), raw_codelists)
    check("OIS occurrences", len(ois), raw_ois)

    # Names, not just counts: every dictionary entry name in the workbook survives, either as an
    # attribute's own name or as the class row it belongs to. A class row's name is
    # "<Object Class>. Details", and the class is stored without the spaces, so both are compared
    # with whitespace removed.
    squash = lambda t: "".join((t or "").split())
    kept = {squash(a["dictionary_entry_name"]) for a in attributes if a.get("dictionary_entry_name")}
    class_names = {squash(c.get("class_name")) for c in classes}
    lost = {d for d in raw_dens
            if squash(d) not in kept and squash(d.split(".")[0]) not in class_names}
    print(f"  dictionary entry names carried through: {len(raw_dens) - len(lost)} of {len(raw_dens)}")
    if lost:
        failures.append("dictionary entry names")
        for d in sorted(lost)[:5]:
            print(f"      lost: {d}")

    # Every attribute still names its source row.
    untraceable = [a for a in attributes if not a.get("source", {}).get("row")]
    print(f"  attributes carrying a source row: {len(attributes) - len(untraceable)} of {len(attributes)}")
    if untraceable:
        failures.append("source rows")

    if failures:
        print(f"\nfidelity check failed: {', '.join(failures)}")
        return 1
    print("\nfidelity check passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
