#!/usr/bin/env python3
"""Fetch every kind of address in every representation, and check each one parses.

A build can be valid and still serve nonsense: the right status with the wrong body, or RDF
that no parser accepts. This asks a running site for each kind of term, index and message in
HTML, Turtle, JSON-LD and RDF/XML, parses what comes back, and reports the triple count.

    python3 scripts/serve.py 8099 &
    python3 scripts/check_representations.py
    python3 scripts/check_representations.py https://test-wcodm.trade-commons.org
"""
import urllib.request, urllib.error, json, sys, rdflib
HOST = sys.argv[1] if len(sys.argv)>1 else "http://localhost:8099"
CASES = [
 ("class",            "individual", "/Agent"),
 ("class (superclass)","individual", "/Party"),
 ("property",         "individual", "/typeCode"),
 ("code list",        "individual", "/code-list/transaction-nature-type-code-list"),
 ("code value",       "individual", "/code-list/transaction-nature-type-code-list/9"),
 ("module",           "individual", "/module/party"),
 ("message",          "individual", "/packages/declarations/mar-api"),
 ("message release",  "individual", "/packages/declarations/mar-api/4.3.0"),
 ("release",          "individual", "/releases/4.2.0"),
 ("change log",       "individual", "/releases/4.2.0/changes"),
 ("documentation",    "individual", "/docs/artefact-generation"),
 ("classes",          "list",       "/classes/"),
 ("properties",       "list",       "/properties/"),
 ("code lists",       "list",       "/code-lists/"),
 ("modules",          "list",       "/modules/"),
 ("packages",         "list",       "/packages/"),
 ("releases",         "list",       "/releases/"),
 ("whole vocabulary", "list",       "/"),
]
ACCEPT = [("html","text/html"),("ttl","text/turtle"),
          ("jsonld","application/ld+json"),("rdf","application/rdf+xml")]
FMT = {"ttl":"turtle","jsonld":"json-ld","rdf":"xml"}
print(f"{'what':20}{'level':11}{'path':44}" + "".join(f"{a:>22}" for a,_ in ACCEPT))
bad=[]
for what, level, path in CASES:
    row=f"{what:20}{level:11}{path:44}"
    for short, accept in ACCEPT:
        try:
            r=urllib.request.urlopen(urllib.request.Request(HOST+path, headers={"Accept":accept}), timeout=60)
            body=r.read(); ct=r.headers.get("Content-Type","").split(";")[0]
            note=""
            if short!="html":
                g=rdflib.Graph(); g.parse(data=body.decode(), format=FMT[short])
                note=f"{len(g)}t"
                if short=="jsonld":
                    d=json.loads(body.decode())
                    if "@context" not in d: note+=" NOCTX"; bad.append((path,"no @context"))
            else:
                note="ok" if b"<h1" in body else "NO H1"
            row+=f"{r.status} {len(body)//1024:>4}K {note:>9}"
        except Exception as e:
            row+=f"{str(getattr(e,'code',e))[:20]:>22}"; bad.append((path,short,str(e)[:60]))
    print(row)
print()
print("problems:", bad if bad else "none")
sys.exit(1 if bad else 0)
