"""Cardinality the workbooks do not state, taken from WCO's published XML schemas.

Applied in one place so that every artefact agrees: the JSON Schema, the browsable structure, the
XML schema and the pages. Each change records what the workbook said, so the correction is visible
rather than silent.
"""
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
_CACHE = {}


def table():
    if "data" not in _CACHE:
        path = ROOT / "docs" / "cardinality-overrides.json"
        _CACHE["data"] = json.loads(path.read_text()) if path.exists() else {}
    return _CACHE["data"]


def for_message(version, package_key, message_slug):
    entry = (table().get(version) or {}).get(f"{package_key}/{message_slug}")
    return (entry or {}).get("positions") or {}


def apply(version, package_key, message_slug, nodes):
    """Rewrite the occurrences of a message's nodes. Returns how many were changed.

    `nodes` is the path-keyed dict build_tree returns. The node is copied before it is changed, so
    a caller holding the package's own records keeps the workbook's values.
    """
    changes = for_message(version, package_key, message_slug)
    if not changes:
        return 0
    n = 0
    for path, want in changes.items():
        node = nodes.get(path)
        if node is None:
            continue
        copy = dict(node)
        copy["min"] = want["min"]
        copy["max"] = want["max"]
        copy["cardinality_source"] = "WCO XML schema"
        copy["cardinality_workbook"] = f'{want["workbook"]["min"]}..{want["workbook"]["max"]}'
        nodes[path] = copy
        n += 1
    return n
