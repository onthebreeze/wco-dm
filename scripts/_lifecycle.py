"""The union of every release, with each term carrying when it appeared and when it stopped.

The vocabulary is not versioned and its terms are. A term is published once, at one address, and
says for itself which release introduced it and which release dropped it, so a document written
against 4.1.0 still resolves every identifier it used even where 4.3.0 no longer has the term.

Identity is the WCO identifier, not the name. Attribute 429 is called "Traveller status code" in
4.1.0 and "Traveler status code" in 4.2.0; keyed by name that is a removal and an addition, keyed by
identifier it is a rename, which is what it was. Earlier names are kept as alternate labels.
"""
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
INT = ROOT / "intermediate"


def releases():
    """Every extracted release, oldest first."""
    index = INT / "releases.json"
    if index.exists():
        return [r["version"] for r in json.loads(index.read_text())["releases"]]
    found = sorted(p.name.lstrip("v") for p in INT.glob("v*") if p.is_dir())
    return sorted(found, key=lambda v: tuple(int(n) for n in v.split(".")))


def load(version, name):
    path = INT / f"v{version}" / f"{name}.json"
    return json.loads(path.read_text()) if path.exists() else []


def lifecycle(versions_present, all_versions):
    """Where a term sits in the lifecycle, from the releases it appears in.

    A term absent from the newest release is deprecated rather than deleted, and names the release
    that dropped it. A term that is absent in the middle and present again later is active, and the
    gap is visible in the list of releases it appears in.
    """
    present = [v for v in all_versions if v in versions_present]
    if not present:
        return {}
    last = present[-1]
    out = {"introducedIn": present[0], "lastSeenIn": last, "presentIn": present}
    if last == all_versions[-1]:
        out["termStatus"] = "active"
    else:
        out["termStatus"] = "deprecated"
        out["deprecatedIn"] = all_versions[all_versions.index(last) + 1]
    return out


def merge(key_of, name_of, records_by_version, all_versions, carry=()):
    """Merge one kind of record across releases.

    The newest record a term has wins, so definitions and tags are those of the release that last
    carried it. `carry` names fields that should be gathered from every release rather than taken
    from the newest, for the handful where the history is the point.
    """
    merged = {}
    for version in all_versions:
        for record in records_by_version.get(version, []):
            key = key_of(record)
            if key is None:
                continue
            entry = merged.get(key)
            if entry is None:
                entry = merged[key] = {"_key": key, "_versions": [], "_names": [], "_record": record}
            entry["_versions"].append(version)
            entry["_record"] = record          # the newest wins
            name = name_of(record)
            if name and name not in entry["_names"]:
                entry["_names"].append(name)
            for field in carry:
                if record.get(field):
                    entry.setdefault(f"_{field}", [])
                    if record[field] not in entry[f"_{field}"]:
                        entry[f"_{field}"].append(record[field])

    out = []
    for entry in merged.values():
        record = dict(entry["_record"])
        record.update(lifecycle(entry["_versions"], all_versions))
        current = name_of(entry["_record"])
        record["formerNames"] = [n for n in entry["_names"] if n != current]
        for field in carry:
            if f"_{field}" in entry:
                record[f"all_{field}"] = entry[f"_{field}"]
        out.append(record)
    return out


def union(all_versions=None):
    """Classes, attributes, code lists and data types, merged across every release."""
    vs = all_versions or releases()
    by = {v: {name: load(v, name) for name in
              ("classes", "attributes", "code-lists", "data-types")} for v in vs}

    def pick(name):
        return {v: by[v][name] for v in vs}

    classes = merge(
        lambda c: c.get("class_id") or c.get("class_name"),
        lambda c: c.get("class_name"),
        pick("classes"), vs)
    attributes = merge(
        lambda a: ((a.get("class_id") or a.get("class_name")), a.get("attr_id")),
        lambda a: a.get("attr_name"),
        pick("attributes"), vs)
    code_lists = merge(
        lambda c: c.get("name"),
        lambda c: c.get("name"),
        pick("code-lists"), vs)
    data_types = merge(
        lambda d: (d.get("name"), d.get("attribute")),
        lambda d: d.get("attribute"),
        pick("data-types"), vs)
    return {"versions": vs, "classes": classes, "attributes": attributes,
            "code-lists": code_lists, "data-types": data_types}
