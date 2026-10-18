#!/usr/bin/env python3
"""Stage E: the vocabulary to a resolvable, content-negotiable tree.

Every term becomes a directory holding index.html, index.ttl and index.jsonld, so one IRI serves a
reader and a machine. The edge function appends /index.<ext> according to Accept, which is why the
three files are siblings rather than separate routes.

The narrative pages are a Nextra site built separately; the two trees merge into one prefix at
deploy, which is how vocab.unece.org does the same job.

    WCO_BASE=https://test-wcodm.trade-commons.org/ python3 scripts/build_site.py
"""
import html
import json
import os
import pathlib
import shutil
import sys
from collections import defaultdict

import rdflib
from rdflib.namespace import DCTERMS, OWL, RDF, RDFS, SKOS

ROOT = pathlib.Path(__file__).resolve().parent.parent
ONT, DIST = ROOT / "ontology", ROOT / "dist"
SOURCE_BASE = "https://vocabulary.wcoomd.org/"
BASE = os.environ.get("WCO_BASE", SOURCE_BASE).rstrip("/") + "/"
SCHEMA = rdflib.Namespace("https://schema.org/")
WCO = rdflib.Namespace(SOURCE_BASE)

KIND_LABEL = {"class": "Class", "property": "Property", "code-list": "Code list", "concept": "Code"}


def local(iri):
    return str(iri)[len(SOURCE_BASE):] if str(iri).startswith(SOURCE_BASE) else str(iri)


def publish(iri):
    return str(iri).replace(SOURCE_BASE, BASE)


def one(g, s, p):
    return next((str(o) for o in g.objects(s, p)), None)


def many(g, s, p):
    return sorted(str(o) for o in g.objects(s, p))


def nav_html(current=None):
    try:
        items = json.loads((ROOT / "docs" / "_nav.json").read_text())
    except FileNotFoundError:
        return ""
    out = []
    for item in items:
        href = BASE if item["slug"] == "index" else f'{BASE}docs/{item["slug"]}'
        cls = ' class="here"' if item["slug"] == current else ""
        out.append(f'<a{cls} href="{href}">{html.escape(item["title"])}</a>')
    out.append(f'<a href="{BASE}schemas/">Schemas</a>')
    out.append(f'<a href="{BASE}module/core">Browse the vocabulary</a>')
    return '<nav class="sitenav">' + "".join(out) + "</nav>"


def page(title, subtitle, body, crumbs, current=None):
    nav = " / ".join(f'<a href="{html.escape(h)}">{html.escape(t)}</a>' if h else html.escape(t) for t, h in crumbs)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)} — WCO Data Model vocabulary</title>
<meta name="description" content="{html.escape(subtitle)}">
<link rel="stylesheet" href="/vocab.css">
<link rel="stylesheet" href="/_pagefind/pagefind-ui.css">
</head><body>
<header class="masthead"><div class="wrap">
  <a class="brand" href="{BASE}"><span class="brand-mark">WCO</span> Data Model vocabulary</a>
  <nav class="crumbs">{nav}</nav>
  <div id="search" class="search"></div>
</div>{nav_html(current)}</header>
<main class="wrap">{body}</main>
<footer class="wrap foot">
  <p>Generated from the WCO Data Model version 4.3.0. This term is served as HTML, Turtle and
     JSON-LD at the same address; ask for <code>text/turtle</code> or <code>application/ld+json</code>.</p>
</footer>
<script src="/_pagefind/pagefind-ui.js" onerror="document.getElementById('search').remove()"></script>
<script>
  // The index covers the term pages as well as the narrative, because Pagefind runs over the
  // finished tree rather than over one framework's output. If it is missing - a local build that
  // skipped the index step - the box removes itself rather than sitting there broken.
  window.addEventListener('DOMContentLoaded', function () {{
    if (window.PagefindUI) {{
      new PagefindUI({{ element: '#search', showImages: false, pageSize: 8,
                        translations: {{ placeholder: 'Search the vocabulary' }} }});
    }} else {{
      var el = document.getElementById('search'); if (el) el.remove();
    }}
  }});
</script>
</body></html>
"""


def term_body(g, s, kind):
    label = one(g, s, RDFS.label) or local(s)
    definition = one(g, s, SKOS.definition) or ""
    status = (one(g, s, WCO.termStatus) or "").rsplit("/", 1)[-1]
    module = (one(g, s, RDFS.isDefinedBy) or "").rsplit("/", 1)[-1]
    rows = []

    def row(k, v):
        if v:
            rows.append(f"<tr><th>{html.escape(k)}</th><td>{v}</td></tr>")

    link = lambda iri: f'<a href="{publish(iri)}">{html.escape(local(iri))}</a>'
    row("IRI", f'<code>{html.escape(publish(s))}</code>')
    row("Kind", KIND_LABEL.get(kind, kind))
    if status:
        row("Status", f'<span class="status status-{html.escape(status)}">{html.escape(status)}</span>')
    if module:
        row("Module", f'<a href="{BASE}module/{module}">{html.escape(module)}</a>')
    for prop, name in ((SCHEMA.domainIncludes, "Used by"), (SCHEMA.rangeIncludes, "Value")):
        vals = [link(o) if str(o).startswith(SOURCE_BASE) else f"<code>{html.escape(str(o).rsplit('#', 1)[-1])}</code>"
                for o in g.objects(s, prop)]
        row(name, ", ".join(sorted(vals)))
    for prop, name in ((WCO.xmlTag, "XML tag"), (WCO.jsonTag, "JSON tag"),
                       (WCO.classId, "WCO class ID"), (WCO.attributeId, "WCO attribute ID"),
                       (WCO.codeListBasis, "Based on"), (SKOS.notation, "Code")):
        vals = many(g, s, prop)
        if vals:
            row(name, ", ".join(f"<code>{html.escape(v)}</code>" for v in vals))
    for prop, name in ((SKOS.exactMatch, "Exact match"), (SKOS.closeMatch, "Close match"),
                       (SKOS.relatedMatch, "Related")):
        vals = many(g, s, prop)
        if vals:
            row(name, ", ".join(f'<a href="{html.escape(v)}">{html.escape(v)}</a>' for v in vals))
    row("Source", html.escape(one(g, s, DCTERMS.source) or ""))

    notes = many(g, s, SKOS.scopeNote)
    notes_html = ""
    if notes:
        items = "".join(f"<li>{html.escape(n)}</li>" for n in notes)
        notes_html = (f'<section><h2>How each class uses it</h2>'
                      f'<p class="muted">The WCO Data Model defines this concept once per class. '
                      f'Every definition is kept.</p><ul class="notes">{items}</ul></section>')

    return (f'<h1>{html.escape(label)}</h1>'
            f'<p class="definition">{html.escape(definition)}</p>'
            f'<table class="facts">{"".join(rows)}</table>{notes_html}')


def write_term(g, s, kind, counts):
    rel = local(s)
    if not rel or rel.startswith("http"):
        return
    out = DIST / rel
    out.mkdir(parents=True, exist_ok=True)

    sub = rdflib.Graph()
    for p, o in g.predicate_objects(s):
        sub.add((s, p, o))
    for prefix, ns in (("wco", SOURCE_BASE), ("rdfs", str(RDFS)), ("owl", str(OWL)),
                       ("skos", str(SKOS)), ("dcterms", str(DCTERMS)), ("schema", str(SCHEMA))):
        sub.bind(prefix, ns)
    ttl = sub.serialize(format="turtle")
    jsonld = sub.serialize(format="json-ld", indent=1)
    if BASE != SOURCE_BASE:
        ttl, jsonld = ttl.replace(SOURCE_BASE, BASE), jsonld.replace(SOURCE_BASE, BASE)

    (out / "index.ttl").write_text(ttl)
    (out / "index.jsonld").write_text(jsonld)
    label = one(g, s, RDFS.label) or rel
    (out / "index.html").write_text(page(
        label, one(g, s, SKOS.definition) or f"{KIND_LABEL.get(kind, kind)} in the WCO Data Model vocabulary.",
        term_body(g, s, kind),
        [("Vocabulary", BASE), (KIND_LABEL.get(kind, kind), None), (label, None)]))
    counts[kind] += 1


def main():
    g = rdflib.Graph()
    for f in sorted(ONT.glob("*.ttl")):
        g.parse(f, format="turtle")

    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir()

    counts = defaultdict(int)
    kinds = {}
    for s in g.subjects(RDF.type, OWL.Class):
        kinds[s] = "class"
    for t in (OWL.DatatypeProperty, OWL.ObjectProperty):
        for s in g.subjects(RDF.type, t):
            kinds.setdefault(s, "property")
    for s in g.subjects(RDF.type, SKOS.ConceptScheme):
        kinds[s] = "code-list"
    for s in g.subjects(RDF.type, SKOS.Concept):
        kinds[s] = "concept"
    for s, kind in kinds.items():
        write_term(g, s, kind, counts)

    # Module pages, each listing what it defines.
    modules = defaultdict(list)
    for s, kind in kinds.items():
        m = one(g, s, RDFS.isDefinedBy)
        if m:
            modules[m.rsplit("/", 1)[-1]].append((kind, s))
    for module, terms in modules.items():
        out = DIST / "module" / module
        out.mkdir(parents=True, exist_ok=True)
        groups = defaultdict(list)
        for kind, s in terms:
            groups[kind].append(s)
        body = [f"<h1>{html.escape(module)} module</h1>",
                f'<p class="definition">Terms the WCO Data Model vocabulary defines in this module.</p>']
        for kind in ("class", "property", "code-list", "concept"):
            if not groups.get(kind):
                continue
            items = "".join(
                f'<li><a href="{publish(s)}">{html.escape(one(g, s, RDFS.label) or local(s))}</a>'
                f'<span class="muted"> — {html.escape((one(g, s, SKOS.definition) or "")[:120])}</span></li>'
                for s in sorted(groups[kind], key=lambda s: (one(g, s, RDFS.label) or local(s)).lower()))
            body.append(f"<section><h2>{KIND_LABEL[kind]}es ({len(groups[kind])})</h2><ul class='terms'>{items}</ul></section>")
        (out / "index.html").write_text(page(f"{module} module", "A module of the WCO Data Model vocabulary.",
                                             "".join(body), [("Vocabulary", BASE), ("Modules", None), (module, None)]))
        counts["module"] += 1

    # The whole graph, for a machine asking at the root. The root HTML page comes from the Nextra
    # site, which is merged over this tree at deploy.
    whole = g.serialize(format="turtle")
    whole_json = g.serialize(format="json-ld", indent=1)
    if BASE != SOURCE_BASE:
        whole, whole_json = whole.replace(SOURCE_BASE, BASE), whole_json.replace(SOURCE_BASE, BASE)
    (DIST / "index.ttl").write_text(whole)
    (DIST / "index.jsonld").write_text(whole_json)

    # Narrative pages, rendered from docs/*.md through the same shell.
    import markdown as md
    renderer = md.Markdown(extensions=["tables", "fenced_code", "toc", "attr_list"])
    nav_items = json.loads((ROOT / "docs" / "_nav.json").read_text())
    for item in nav_items:
        src = ROOT / "docs" / f'{item["slug"]}.md'
        if not src.exists():
            continue
        renderer.reset()
        body = renderer.convert(src.read_text())
        title = item["title"]
        out = DIST if item["slug"] == "index" else DIST / "docs" / item["slug"]
        out.mkdir(parents=True, exist_ok=True)
        crumbs = [("Vocabulary", BASE)] + ([] if item["slug"] == "index" else [(title, None)])
        (out / "index.html").write_text(
            page(title, "The WCO Data Model published as linked data.",
                 f'<article class="prose">{body}</article>', crumbs, current=item["slug"]))
        counts["page"] += 1

    # The schemas, served beside the vocabulary, with an index that says what each one is for.
    schemas_dir = ROOT / "schemas"
    if schemas_dir.exists():
        import shutil as _sh
        target = DIST / "schemas"
        target.mkdir(parents=True, exist_ok=True)
        report = {}
        rp = schemas_dir / "build-report.json"
        if rp.exists():
            report = json.loads(rp.read_text())
        for f in schemas_dir.iterdir():
            if f.name == "build-report.json":
                continue
            text = f.read_text()
            if BASE != SOURCE_BASE:
                text = text.replace(SOURCE_BASE, BASE)
            (target / f.name).write_text(text)
            counts["schema file"] += 1

        titles = {"mdip": "Meta Data", "aip": "Additional (Response and Intergov)",
                  "bip-dec": "Declaration", "bip-lpco": "Licences, permits, certificates"}
        rows = []
        for key in ("bip-dec", "bip-lpco", "aip", "mdip"):
            info = report.get(key, {})
            schema = f"{BASE}schemas/{key}-4.3.0.json"
            ctx = f"{BASE}schemas/{key}-4.3.0-context.jsonld"
            rows.append(
                f'<tr><th><a href="{schema}">{html.escape(titles.get(key, key))}</a></th>'
                f'<td>{info.get("nodes", "")} nodes</td>'
                f'<td><a href="{schema}">schema</a> · <a href="{ctx}">context</a></td></tr>')
            for slug, n in sorted((info.get("derived") or {}).items()):
                ds = f"{BASE}schemas/{key}-{slug}-4.3.0.json"
                dc = f"{BASE}schemas/{key}-{slug}-4.3.0-context.jsonld"
                rows.append(
                    f'<tr><th class="sub">{html.escape(slug)}</th><td>{n} nodes</td>'
                    f'<td><a href="{ds}">schema</a> · <a href="{dc}">context</a></td></tr>')
        body = (
            "<h1>Schemas</h1>"
            "<p class=\"definition\">A JSON Schema and a JSON-LD context for each Information "
            "Package, and for each derived package that subsets it. Generated from the package "
            "workbooks, so the cardinality is the model's own.</p>"
            f"<table class=\"facts\">{''.join(rows)}</table>"
            "<section><h2>How to read them</h2><p class=\"muted\">A class becomes an object, an "
            "element becomes a typed property, an unbounded maximum becomes an array, and a minimum "
            "of one becomes required. Each property carries the WCO identifier it came from and, "
            "where the vocabulary has the term, a link to it.</p></section>")
        out = DIST / "schemas"
        (out / "index.html").write_text(page(
            "Schemas", "JSON Schema and JSON-LD context for each WCO Information Package.",
            body, [("Vocabulary", BASE), ("Schemas", None)], current="schemas"))
        counts["page"] += 1

    (DIST / "vocab.css").write_text(CSS)
    print(f"base: {BASE}")
    for k in sorted(counts):
        print(f"  {k}: {counts[k]}")
    print(f"  whole graph: {len(g)} triples")
    return 0


CSS = """:root{--brand-dark:#083a7a;--ink:#14202e;--muted:#5b6b7c;--line:#dfe6ee;--bg:#f6f9fc;--brand:#0b4ea2;--brand-ink:#fff}
*{box-sizing:border-box}
body{margin:0;font:16px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif;color:var(--ink);background:var(--bg)}
.wrap{max-width:1000px;margin:0 auto;padding:0 20px}
.masthead{background:var(--brand);color:var(--brand-ink)}
.masthead .wrap{display:flex;flex-wrap:wrap;gap:12px;align-items:baseline;justify-content:space-between;padding-top:14px;padding-bottom:14px}
.brand{color:var(--brand-ink);text-decoration:none;font-weight:700;font-size:18px}
.brand-mark{background:var(--brand-ink);color:var(--brand);padding:2px 7px;border-radius:4px;margin-right:6px;letter-spacing:.5px}
.crumbs{font-size:14px;opacity:.9}
.crumbs a{color:var(--brand-ink)}
main{background:#fff;border:1px solid var(--line);border-radius:12px;padding:28px 24px;margin:22px auto 30px}
h1{margin:0 0 10px;font-size:30px;line-height:1.2}
h2{margin:28px 0 10px;font-size:19px}
.definition{margin:0 0 20px;font-size:17px;color:#2d3f52}
.muted{color:var(--muted)}
table.facts{border-collapse:collapse;width:100%;margin:0 0 10px}
table.facts th{text-align:left;vertical-align:top;white-space:nowrap;padding:8px 14px 8px 0;color:var(--muted);font-weight:600;width:170px;border-top:1px solid var(--line)}
table.facts td{padding:8px 0;border-top:1px solid var(--line);word-break:break-word}
code{background:var(--bg);border:1px solid var(--line);border-radius:4px;padding:1px 5px;font-size:13.5px}
a{color:var(--brand)}
ul.terms,ul.notes{margin:0;padding-left:20px}
ul.terms li,ul.notes li{margin:4px 0}
.status{border-radius:999px;padding:2px 10px;font-size:13px;font-weight:600}
.status-active{background:#e6f4ea;color:#17643b}
.status-proposed{background:#fef7e0;color:#7a5900}
.status-deprecated{background:#fce8e6;color:#8c1d18}
.foot{color:var(--muted);font-size:14px;padding-bottom:30px}
.search{flex:1 1 280px;max-width:420px;min-width:220px}
.search .pagefind-ui__search-input{font-size:14px;padding:7px 10px;border-radius:6px;border:0;width:100%}
.search .pagefind-ui__drawer{position:absolute;z-index:40;background:#fff;color:var(--ink);border:1px solid var(--line);border-radius:8px;margin-top:6px;max-width:420px;max-height:60vh;overflow:auto;padding:6px 12px;box-shadow:0 10px 28px rgba(10,30,60,.18)}
.search .pagefind-ui__result-title a{color:var(--brand)}
.sitenav{background:var(--brand-dark,#083a7a)}
.sitenav a{display:inline-block;color:#dce9f8;text-decoration:none;padding:10px 16px;font-size:14.5px}
.sitenav a:hover{background:rgba(255,255,255,.1);color:#fff}
.sitenav a.here{background:#fff;color:var(--brand);font-weight:600}
.prose h2{border-top:1px solid var(--line);padding-top:20px}
.prose table{border-collapse:collapse;margin:14px 0;width:100%}
.prose th,.prose td{border:1px solid var(--line);padding:7px 10px;text-align:left;vertical-align:top}
.prose th{background:var(--bg)}
.prose pre{background:#0f2238;color:#e6eef8;padding:14px 16px;border-radius:8px;overflow:auto;font-size:13.5px;line-height:1.45}
.prose pre code{background:none;border:0;color:inherit;padding:0}
.prose li{margin:4px 0}
table.facts th.sub{padding-left:22px;font-weight:400;color:var(--ink)}
@media(max-width:620px){table.facts th{width:auto;display:block;border-top:0;padding-bottom:0}table.facts td{display:block;border-top:0;padding-top:2px}table.facts tr{display:block;border-top:1px solid var(--line);padding:8px 0}}
"""

if __name__ == "__main__":
    sys.exit(main())
