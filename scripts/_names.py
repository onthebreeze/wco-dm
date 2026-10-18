#!/usr/bin/env python3
"""Turning WCO dictionary entry names into IRI local names.

The WCO Data Model names a property inside the context of its class, so `id` occurs 174 times and
`typeCode` 49. A linked data vocabulary needs one IRI per concept, so the object class is dropped
from the dictionary entry name and the remainder becomes the local name: "Consignment. Carrier.
Identifier" gives `carrierIdentifier`, and every class that uses it appears in schema:domainIncludes.

Two attributes may reduce to the same local name without meaning the same thing. Those are not
merged silently: they are qualified with the class name and reported, so the judgement stays
visible.
"""
import re

ACRONYMS = {"WCO", "UN", "EU", "ID", "UCR", "AEO", "GPS", "VAT", "IMO", "ISO", "URI", "URL", "HS", "RFF"}


def _words(text):
    return [w for w in re.split(r"[^A-Za-z0-9]+", text or "") if w]


def camel(text):
    """Words to lowerCamelCase, leaving known acronyms intact except as the first word."""
    out = []
    for i, w in enumerate(_words(text)):
        upper = w.upper()
        if i == 0:
            out.append(w.lower() if upper not in ACRONYMS else w.lower())
        elif upper in ACRONYMS:
            out.append(upper)
        else:
            out.append(w[0].upper() + w[1:] if not w.isupper() else w.capitalize())
    return "".join(out)


def class_name(text):
    """Class names arrive already cased by WCO (AuthorisationHolder, MDIP, GovernmentAgencyGoodsItem),
    so they are used as they are, with only separators removed. Re-casing them would turn MDIP into
    Mdip and AuthorisationHolder into Authorisationholder."""
    return "".join(_words(text))


def split_den(den):
    """Dictionary entry name to (object class, property terms, representation term).

    "MDIP. WCO Type. Code"      -> ("MDIP", ["WCO Type"], "Code")
    "Consignment. Identifier"   -> ("Consignment", [], "Identifier")
    """
    parts = [p.strip() for p in (den or "").split(".") if p.strip()]
    if not parts:
        return None, [], None
    if len(parts) == 1:
        return None, [], parts[0]
    return parts[0], parts[1:-1], parts[-1]


def local_name(den, fallback=None):
    """The IRI local name for a property: the dictionary entry name without its object class."""
    _, middle, rep = split_den(den)
    if rep:
        return camel(" ".join(middle + [rep]))
    return camel(fallback or "")


def label_from_den(den, fallback=None):
    """A label for the merged property: the dictionary entry name without its object class, read as
    words. A merged property must not be labelled after whichever class it met first - that is how
    the identifier shared by 172 classes came to be called "Appeal office identifier"."""
    _, middle, rep = split_den(den)
    parts = _words(" ".join(middle + [rep])) if rep else _words(fallback or "")
    if not parts:
        return fallback or ""
    out = []
    for i, w in enumerate(parts):
        if w.isupper() and len(w) > 1:
            out.append(w)                      # keep WCO, AEO, UCR as they are
        elif i == 0:
            out.append(w[0].upper() + w[1:].lower())
        else:
            out.append(w.lower())
    return " ".join(out)


def label_from_local(name):
    """sealTypeCode -> "Seal type code". Used for a property that was split out of a merged one:
    its label has to follow its new name, or fifty split properties all read "Type code"."""
    words = re.sub(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", " ", name or "").split()
    out = []
    for i, w in enumerate(words):
        if w.isupper() and len(w) > 1:
            out.append(w)
        elif i == 0:
            out.append(w[0].upper() + w[1:].lower())
        else:
            out.append(w.lower())
    return " ".join(out)
