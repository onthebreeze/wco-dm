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
    out.append(f'<a href="{BASE}code-lists/">Code lists</a>')
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


def table(headers, rows, cls="listing", col_classes=None):
    """col_classes names each column so the stylesheet can size it: "name" for a term, "prose" for a
    definition that must wrap, "num" for a count that must not."""
    if not rows:
        return ""
    cc = col_classes or [""] * len(headers)
    head = "".join(f'<th class="c-{c}">{h}</th>' if c else f"<th>{h}</th>"
                   for h, c in zip(headers, cc))
    body = "".join(
        "<tr>" + "".join(f'<td class="c-{c}">{v}</td>' if c else f"<td>{v}</td>"
                         for v, c in zip(r, cc)) + "</tr>"
        for r in rows)
    return f'<table class="{cls}"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>'


def display_label(g, iri):
    """A code carries skos:prefLabel and a notation rather than an rdfs:label, so without this a
    code value is titled with its whole path."""
    return (one(g, iri, RDFS.label)
            or one(g, iri, SKOS.prefLabel)
            or one(g, iri, SKOS.notation)
            or local(iri).rsplit("/", 1)[-1])


def term_link(g, iri):
    return f'<a href="{publish(iri)}">{html.escape(display_label(g, iri))}</a>'


def split_range(g, t):
    """A property's value, as (plain types, code lists)."""
    types, lists = [], []
    for o in sorted(g.objects(t, SCHEMA.rangeIncludes), key=str):
        if (o, RDF.type, SKOS.ConceptScheme) in g:
            lists.append(o)
        elif str(o).startswith(SOURCE_BASE):
            types.append(term_link(g, o))
        else:
            types.append(f'<code>{html.escape(str(o).rsplit("#", 1)[-1])}</code>')
    return types, sorted(lists, key=lambda o: display_label(g, o).lower())


def render_range(g, t, limit=2):
    """The value column. A merged property can draw on many code lists - typeCode draws on
    seventeen, because each class that uses it codes against a different one - so the column shows
    the type and the first few lists, and sends the reader to the property page for the rest rather
    than unrolling them into the table."""
    types, lists = split_range(g, t)
    out = list(types)
    for o in lists[:limit]:
        out.append(f'<a class="codelist" href="{publish(o)}">{html.escape(display_label(g, o))}</a>')
    if len(lists) > limit:
        out.append(f'<a class="more" href="{publish(t)}">and {len(lists) - limit} more</a>')
    return ", ".join(out) or "<code>string</code>"


def short(text, n=150):
    text = " ".join((text or "").split())
    return html.escape(text if len(text) <= n else text[: n - 1].rstrip() + "…")


def term_body(g, s, kind, idx):
    label = display_label(g, s)
    definition = one(g, s, SKOS.definition) or ""
    status = (one(g, s, WCO.termStatus) or "").rsplit("/", 1)[-1]
    module = (one(g, s, RDFS.isDefinedBy) or "").rsplit("/", 1)[-1]
    rows = []

    def row(k, v):
        if v:
            rows.append(f"<tr><th>{html.escape(k)}</th><td>{v}</td></tr>")

    link = lambda iri: term_link(g, iri)
    row("IRI", f'<code>{html.escape(publish(s))}</code>')
    row("Kind", KIND_LABEL.get(kind, kind))
    if status:
        row("Status", f'<span class="status status-{html.escape(status)}">{html.escape(status)}</span>')
    if module:
        row("Module", f'<a href="{BASE}module/{module}">{html.escape(module)}</a>')
    if kind == "property":
        row("Value", ", ".join(split_range(g, s)[0]) or "<code>string</code>")
    for prop, name in ((WCO.xmlTag, "XML tag"), (WCO.jsonTag, "JSON tag"),
                       (WCO.classId, "WCO class ID"), (WCO.attributeId, "WCO attribute ID"),
                       (SKOS.notation, "Code")):
        vals = many(g, s, prop)
        if vals:
            row(name, ", ".join(f"<code>{html.escape(v)}</code>" for v in vals))
    if kind == "property":
        refs = many(g, s, WCO.codeListBasis)
        if refs:
            row("Code list", "<br>".join(html.escape(r) for r in refs))
    if kind in ("code-list", "concept"):
        row("Based on", "<br>".join(html.escape(r) for r in many(g, s, WCO.codeListBasis)))
    if kind == "concept":
        scheme = next(iter(g.objects(s, SKOS.inScheme)), None)
        if scheme:
            row("Code list", link(scheme))
    row("Source", html.escape(one(g, s, DCTERMS.source) or ""))

    sections = [f'<table class="facts">{"".join(rows)}</table>']

    if kind == "class":
        props = sorted(idx["class_props"].get(s, []), key=lambda t: display_label(g, t).lower())
        sections.append(
            f'<section><h2>Properties ({len(props)})</h2>'
            + (table(["Property", "Definition", "Value"], [
                (term_link(g, t), short(one(g, t, SKOS.definition)),
                 render_range(g, t))
                for t in props], col_classes=["name", "prose", "value"])
               or '<p class="muted">This class carries no properties of its own.</p>')
            + "</section>")

    if kind == "property":
        _, lists = split_range(g, s)
        if lists:
            sections.append(
                f'<section><h2>Value domain ({len(lists)})</h2>'
                + ('<p class="muted">Each class that uses this property codes against its own list, '
                   'so the value domain depends on where it is used.</p>' if len(lists) > 1 else "")
                + table(["Code list", "Based on", "Values"],
                        [(term_link(g, o), short(one(g, o, WCO.codeListBasis), 90),
                          str(len(idx["scheme_concepts"].get(o, [])))) for o in lists],
                        col_classes=["name", "prose", "num"])
                + "</section>")
        classes = sorted(g.objects(s, SCHEMA.domainIncludes), key=lambda t: display_label(g, t).lower())
        sections.append(
            f'<section><h2>Used by ({len(classes)})</h2>'
            + (table(["Class", "Definition"],
                     [(term_link(g, c), short(one(g, c, SKOS.definition))) for c in classes],
                     col_classes=["name", "prose"])
               or '<p class="muted">No class declares this property.</p>')
            + "</section>")

    if kind == "code-list":
        concepts = sorted(idx["scheme_concepts"].get(s, []),
                          key=lambda t: (one(g, t, SKOS.notation) or ""))
        if concepts:
            sections.append(
                f'<section><h2>Values ({len(concepts)})</h2>'
                + table(["Code", "Meaning"],
                        [(f'<a href="{publish(c)}"><code>{html.escape(one(g, c, SKOS.notation) or "")}</code></a>',
                          short(one(g, c, SKOS.prefLabel), 200)) for c in concepts],
                        col_classes=["code", "prose"])
                + "</section>")
        else:
            sections.append(
                '<section><h2>Values</h2><p class="muted">The WCO Data Model registers this list '
                'but does not carry its values: they come from the external list named above.</p></section>')
        users = sorted(idx["scheme_props"].get(s, []), key=lambda t: display_label(g, t).lower())
        if users:
            sections.append(
                f'<section><h2>Used by ({len(users)})</h2>'
                + table(["Property", "Definition"],
                        [(term_link(g, t), short(one(g, t, SKOS.definition))) for t in users],
                        col_classes=["name", "prose"])
                + "</section>")

    # Mappings to vocab.unece.org: the accepted ones first, then the candidates the ledger has not
    # had reviewed, marked as such. Showing only the accepted ones would leave almost every page
    # blank, and showing candidates unmarked would pass a guess off as a decision.
    accepted, candidates = [], []
    for prop, name in ((SKOS.exactMatch, "exact match"), (SKOS.closeMatch, "close match"),
                       (SKOS.relatedMatch, "related")):
        for v in many(g, s, prop):
            accepted.append((name, v))
    for c in idx["candidates"].get(str(s).replace(BASE, SOURCE_BASE), []):
        if not any(v == c["unece_term"] for _, v in accepted):
            candidates.append(c)
    if accepted or candidates:
        rows_m = []
        for name, v in sorted(accepted):
            rows_m.append((f'<span class="rel">{html.escape(name)}</span>',
                           f'<a href="{html.escape(v)}">{html.escape(v.rsplit("/", 1)[-1])}</a>',
                           f'<code class="muted">{html.escape(v)}</code>'))
        for c in sorted(candidates, key=lambda c: -float(c["score"])):
            rel = c["relation"].replace("skos:", "")
            rows_m.append((
                f'<span class="rel rel-candidate">{html.escape(rel)}</span> '
                f'<span class="editorial" title="Proposed by the matcher, not yet reviewed">candidate {c["score"]}</span>',
                f'<a href="{html.escape(c["unece_term"])}">{html.escape(c["unece_label"] or c["unece_term"].rsplit("/", 1)[-1])}</a>',
                f'<span class="muted">{html.escape(c["evidence"])}</span>'))
        sections.append(
            f'<section><h2>Mapped to vocab.unece.org ({len(rows_m)})</h2>'
            + table(["Relation", "Term", "Evidence"], rows_m, col_classes=["rel", "name", "prose"])
            + ('<p class="muted">A candidate is proposed by the matcher and has not been reviewed. '
               'See <code>mappings/wco-to-unece.csv</code>.</p>' if candidates else "")
            + "</section>")

    notes = many(g, s, SKOS.scopeNote)
    if notes:
        items = "".join(f"<li>{html.escape(n)}</li>" for n in notes)
        sections.append(f'<section><h2>How each class uses it ({len(notes)})</h2>'
                        f'<p class="muted">The WCO Data Model defines this concept once per class. '
                        f'Every definition is kept.</p><ul class="notes">{items}</ul></section>')

    return (f'<h1>{html.escape(label)}</h1>'
            f'<p class="definition">{html.escape(definition)}</p>' + "".join(sections))


def write_term(g, s, kind, counts, idx):
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
    label = display_label(g, s)
    crumbs = [("Vocabulary", BASE)]
    if kind == "concept":
        scheme = next(iter(g.objects(s, SKOS.inScheme)), None)
        if scheme is not None:
            crumbs.append((display_label(g, scheme), publish(scheme)))
    else:
        crumbs.append((KIND_LABEL.get(kind, kind), None))
    crumbs.append((label, None))
    subtitle = one(g, s, SKOS.definition) or one(g, s, SKOS.prefLabel) or \
        f"{KIND_LABEL.get(kind, kind)} in the WCO Data Model vocabulary."
    (out / "index.html").write_text(page(label, subtitle, term_body(g, s, kind, idx), crumbs))
    counts[kind] += 1


def main():
    g = rdflib.Graph()
    for f in sorted(ONT.glob("*.ttl")):
        g.parse(f, format="turtle")

    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir()

    counts = defaultdict(int)
    # Indexes the pages need: which properties a class carries, which concepts a scheme holds, and
    # which properties point at a scheme. Built once rather than queried per page.
    idx = {"class_props": defaultdict(list), "scheme_concepts": defaultdict(list),
           "scheme_props": defaultdict(list)}
    for t in (OWL.DatatypeProperty, OWL.ObjectProperty):
        for prop in g.subjects(RDF.type, t):
            for cls in g.objects(prop, SCHEMA.domainIncludes):
                idx["class_props"][cls].append(prop)
            for rng in g.objects(prop, SCHEMA.rangeIncludes):
                if (rng, RDF.type, SKOS.ConceptScheme) in g:
                    idx["scheme_props"][rng].append(prop)
    for concept in g.subjects(RDF.type, SKOS.Concept):
        for scheme in g.objects(concept, SKOS.inScheme):
            idx["scheme_concepts"][scheme].append(concept)

    idx["candidates"] = defaultdict(list)
    ledger = ROOT / "mappings" / "wco-to-unece.csv"
    if ledger.exists():
        import csv as _csv
        with ledger.open() as f:
            for r in _csv.DictReader(f):
                if r.get("decision") == "review":
                    idx["candidates"][r["wco_term"]].append(r)

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
        write_term(g, s, kind, counts, idx)

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
        for kind, t in terms:
            groups[kind].append(t)
        by_label = lambda t: display_label(g, t).lower()
        body = [f"<h1>{html.escape(module)} module</h1>",
                '<p class="definition">Terms the WCO Data Model vocabulary defines in this module.</p>']

        classes = sorted(groups.get("class", []), key=by_label)
        if classes:
            body.append(f'<section><h2>Classes ({len(classes)})</h2>' + table(
                ["Class", "Definition", "Properties"],
                [(term_link(g, c), short(one(g, c, SKOS.definition)),
                  str(len(idx["class_props"].get(c, [])))) for c in classes],
                col_classes=["name", "prose", "num"]) + "</section>")

        props = sorted(groups.get("property", []), key=by_label)
        if props:
            body.append(f'<section><h2>Properties ({len(props)})</h2>' + table(
                ["Property", "Definition", "Value", "Used by"],
                [(term_link(g, t), short(one(g, t, SKOS.definition), 110), render_range(g, t),
                  str(len(list(g.objects(t, SCHEMA.domainIncludes))))) for t in props],
                col_classes=["name", "prose", "value", "num"]) + "</section>")

        schemes = sorted(groups.get("code-list", []), key=by_label)
        if schemes:
            body.append(f'<section><h2>Code lists ({len(schemes)})</h2>' + table(
                ["Code list", "Based on", "Values", "Used by"],
                [(term_link(g, c), short(one(g, c, WCO.codeListBasis), 90),
                  str(len(idx["scheme_concepts"].get(c, []))) or "0",
                  str(len(idx["scheme_props"].get(c, [])))) for c in schemes],
                col_classes=["name", "prose", "num", "num"]) + "</section>")

        (out / "index.html").write_text(page(f"{module} module", "A module of the WCO Data Model vocabulary.",
                                             "".join(body), [("Vocabulary", BASE), ("Modules", None), (module, None)]))
        counts["module"] += 1

    # A code list register, grouped by what the model actually knows about each list.
    schemes = sorted(g.subjects(RDF.type, SKOS.ConceptScheme), key=lambda t: display_label(g, t).lower())
    schemes = [t for t in schemes if str(t).startswith(SOURCE_BASE + "code-list/")]
    origin = lambda t: (one(g, t, WCO.codeListOrigin) or "registered")
    with_values = [t for t in schemes if idx["scheme_concepts"].get(t)]
    registered_empty = [t for t in schemes if not idx["scheme_concepts"].get(t) and origin(t) == "registered"]
    referenced = [t for t in schemes if origin(t) == "referenced"]

    def scheme_table(items):
        return table(["Code list", "Based on", "Values", "Used by"],
                     [(term_link(g, t), short(one(g, t, WCO.codeListBasis), 90),
                       str(len(idx["scheme_concepts"].get(t, []))),
                       str(len(idx["scheme_props"].get(t, [])))) for t in items],
                     col_classes=["name", "prose", "num", "num"])

    body = [
        "<h1>Code lists</h1>",
        '<p class="definition">Every coded property resolves to a code list rather than to a bare '
        'string. Whether that list carries its values here depends on who maintains them.</p>',
        f'<section><h2>With their values ({len(with_values)})</h2>'
        '<p class="muted">WCO owns these codes, so they are published here and each value has its '
        'own address.</p>' + scheme_table(with_values) + "</section>",
        f'<section><h2>Registered, values held elsewhere ({len(registered_empty)})</h2>'
        '<p class="muted">The WCO register names the list and says what it is based on. The values '
        'belong to that authority, so they are not reproduced here.</p>'
        + scheme_table(registered_empty) + "</section>",
        f'<section><h2>Referenced but not registered ({len(referenced)})</h2>'
        '<p class="muted">The model names these lists against an attribute, but the register either '
        'does not hold them or holds several drawing on the same basis and cannot say which. They '
        'exist here so a coded property has something to resolve to.</p>'
        + scheme_table(referenced) + "</section>",
    ]
    out = DIST / "code-lists"
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_text(page(
        "Code lists", "Every code list the WCO Data Model names, and what is known about each.",
        "".join(body), [("Vocabulary", BASE), ("Code lists", None)], current="code-lists"))
    counts["page"] += 1

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

        meta = json.loads((ROOT / "docs" / "derived-packages.json").read_text())
        pkg_meta, dip_meta = meta["packages"], meta["derived"]

        sections = []
        for key in ("bip-dec", "bip-lpco", "aip", "mdip"):
            info = report.get(key, {})
            m = pkg_meta.get(key, {})
            schema = f"{BASE}schemas/{key}-4.3.0.json"
            ctx = f"{BASE}schemas/{key}-4.3.0-context.jsonld"
            rows = [
                f'<tr><th>Covers</th><td>{html.escape(m.get("description", ""))}</td></tr>',
                f'<tr><th>Size</th><td>{info.get("nodes", "")} nodes in the information tree</td></tr>',
                f'<tr><th>Files</th><td><a href="{schema}">JSON Schema</a> · '
                f'<a href="{ctx}">JSON-LD context</a></td></tr>',
            ]
            derived = sorted((info.get("derived") or {}).items())
            if derived:
                items = []
                for slug, n in derived:
                    d = dip_meta.get(slug, {})
                    ds = f"{BASE}schemas/{key}-{slug}-4.3.0.json"
                    dc = f"{BASE}schemas/{key}-{slug}-4.3.0-context.jsonld"
                    editorial = ' <span class="editorial" title="Our wording, not WCO\'s">gloss</span>' if d.get("source") == "editorial" else ""
                    items.append(
                        f'<li><a href="{ds}"><b>{html.escape(d.get("name", slug))}</b></a> '
                        f'<span class="muted">· {n} nodes · {html.escape(d.get("group", ""))}</span>{editorial}'
                        f'<br><span class="muted">{html.escape(d.get("gloss", ""))}</span> '
                        f'<a class="quiet" href="{dc}">context</a></li>')
                rows.append(
                    f'<tr><th>Derived packages</th><td><ul class="dips">{"".join(items)}</ul></td></tr>')
            sections.append(
                f'<section><h2>{html.escape(m.get("title", key))} '
                f'<span class="muted">— {html.escape(m.get("subtitle", ""))}</span></h2>'
                f'<table class="facts">{"".join(rows)}</table></section>')

        body = (
            "<h1>Schemas</h1>"
            "<p class=\"definition\">A JSON Schema and a JSON-LD context for each of the four "
            "Information Packages, and for each derived package that subsets it. Generated from the "
            "package workbooks, so the cardinality is the model\'s own rather than an assumption.</p>"
            + "".join(sections)
            + "<section><h2>How to read them</h2><p class=\"muted\">A class becomes an object, an "
            "element becomes a typed property, an unbounded maximum becomes an array, and a minimum "
            "of one becomes required. Each property carries the WCO identifier it came from and, "
            "where the vocabulary has the term, a link to it.</p>"
            "<p class=\"muted\">A derived package is the same tree cut down to the nodes it marks, "
            "with the ancestors those nodes need. Where an entry is marked <span class=\"editorial\">"
            "gloss</span> the explanation is ours: the workbook names the package but never spells "
            "the abbreviation out.</p></section>")
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
table.listing{border-collapse:collapse;width:100%;margin:6px 0 4px;font-size:15px}
table.listing th{text-align:left;background:var(--bg);border-bottom:2px solid var(--line);padding:8px 10px;color:var(--muted);font-weight:600;font-size:13.5px;text-transform:uppercase;letter-spacing:.03em}
table.listing td{border-bottom:1px solid var(--line);padding:8px 10px;vertical-align:top}
table.listing tr:hover td{background:#f9fbfe}
table.listing{table-layout:fixed}
table.listing td{overflow-wrap:anywhere}
.c-name{width:22%}
.c-prose{width:auto;white-space:normal}
.c-value{width:18%}
.c-code{width:90px}
.c-num{width:84px;text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}
.c-rel{width:190px}
.rel{font-weight:600;color:var(--brand)}
.rel-candidate{color:var(--muted);font-weight:500}
a.more{font-size:13.5px;color:var(--muted)}
a.codelist{background:#eef4fb;border:1px solid #cfe0f2;border-radius:5px;padding:1px 7px;font-size:14px;text-decoration:none;white-space:nowrap}
@media(max-width:760px){table.listing{table-layout:auto}.c-name,.c-value,.c-rel{width:auto}}
table.facts th.sub{padding-left:22px;font-weight:400;color:var(--ink)}
ul.dips{margin:0;padding-left:18px}
ul.dips li{margin:10px 0}
a.quiet{font-size:13px}
.editorial{background:#fef7e0;color:#7a5900;border-radius:999px;padding:1px 8px;font-size:12px;font-weight:600}
@media(max-width:620px){table.facts th{width:auto;display:block;border-top:0;padding-bottom:0}table.facts td{display:block;border-top:0;padding-top:2px}table.facts tr{display:block;border-top:1px solid var(--line);padding:8px 0}}
"""

if __name__ == "__main__":
    sys.exit(main())
