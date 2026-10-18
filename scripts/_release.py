"""Which WCO release is being built, and where its workbooks are.

raw-data holds one directory per release. The file names differ between releases - 4.2.0 calls the
metadata package "Section 3.1. WCO DM MDIP_V4.2.0.xlsx" and 4.3.0 calls it "3.1. WCO DM
MDIP_V4.3.0.xlsx" - so the workbooks are found by what they are rather than by name, and a release
that renames its files again still builds.

    python3 scripts/extract.py                      # the newest release in raw-data/
    WCO_RELEASE=v4.2.0 python3 scripts/extract.py   # a named one
"""
import json
import os
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW = ROOT / "raw-data"

# What each workbook is, as a pattern over its name. The boundary is "not a letter" rather than
# \b, because \b treats the underscore in MDIP_V4.2.0 as a word character and would not match.
WORKBOOKS = {
    "library": r"(?<![A-Z])LIB(?![A-Z])",
    "ois": r"(?<![A-Z])OIS(?![A-Z])",
    "mdip": r"(?<![A-Z])MDIP(?![A-Z])",
    "aip": r"(?<![A-Z])AIP(?![A-Z])",
    "bip-dec": r"BIP\s*DEC",
    "bip-lpco": r"BIP\s*LPCO",
}


def releases():
    """Every release directory, oldest first, by version number rather than by name."""
    def key(p):
        return tuple(int(n) for n in re.findall(r"\d+", p.name))
    return sorted((p for p in RAW.glob("v*") if p.is_dir()), key=key)


def release_dir():
    named = os.environ.get("WCO_RELEASE")
    if named:
        path = RAW / named
        if not path.is_dir():
            raise SystemExit(f"no such release: {path}")
        return path
    found = releases()
    if not found:
        raise SystemExit(f"no release directories in {RAW}; expected raw-data/v4.3.0/ or similar")
    return found[-1]


def version(path=None):
    return (path or release_dir()).name.lstrip("v")


def workbooks(path=None):
    """Name each workbook of the release. Missing ones are left out rather than guessed at, so the
    caller fails on the file it actually needs."""
    path = path or release_dir()
    found = {}
    for name in sorted(p.name for p in path.glob("*.xlsx") if not p.name.startswith("~$")):
        for key, pattern in WORKBOOKS.items():
            if key in found:
                continue
            if re.search(pattern, name, re.IGNORECASE):
                found[key] = name
                break
    return found


def workbook(key, path=None):
    path = path or release_dir()
    found = workbooks(path)
    if key not in found:
        raise SystemExit(f"{path.name} has no {key} workbook; found {sorted(found)}")
    return path / found[key]


def built_version():
    """The release the intermediate was extracted from.

    Every stage after extract.py labels its output with this rather than with the newest release on
    disk, so adding a newer workbook does not retitle a build made from an older one.
    """
    report = ROOT / "intermediate" / "extraction-report.json"
    if report.exists():
        return json.loads(report.read_text())["source"]["version"]
    return version()
