#!/usr/bin/env python3
"""Stage E: the vocabulary to a resolvable, content-negotiable tree.

Every page becomes a directory holding index.html, index.ttl, index.jsonld and index.rdf, so one
address serves a reader and a machine. The edge function appends /index.<ext> according to Accept,
which is why the four files are siblings rather than separate routes.

Every page, not only the terms. A module, an index of classes, a message and the narrative pages
all answer a machine with something true about themselves, which is what lets the edge stay one
rule with no list of which addresses negotiate and which do not.

    WCO_BASE=https://test-wcodm.trade-commons.org/ python3 scripts/build_site.py
"""
import hashlib
import html
import json
import os
import pathlib
import shutil
import sys
from collections import defaultdict

import rdflib
from rdflib.namespace import DCTERMS, OWL, RDF, RDFS, SKOS

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import _release  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
VERSION = _release.built_version()
ONT, DIST = ROOT / "ontology", ROOT / "dist"
SOURCE_BASE = "https://vocabulary.wcoomd.org/"
BASE = os.environ.get("WCO_BASE", SOURCE_BASE).rstrip("/") + "/"
SCHEMA = rdflib.Namespace("https://schema.org/")
WCO = rdflib.Namespace(SOURCE_BASE)

KIND_LABEL = {"class": "Class", "property": "Property", "code-list": "Code list", "concept": "Code"}

# The machine representations every address answers in. Keeping the set the same everywhere is what
# lets the edge function stay one rule - a directory holds its own index.* - instead of a list of
# which paths are negotiable and which are not.
MACHINE = (("ttl", "turtle", "Turtle"),
           ("jsonld", "json-ld", "JSON-LD"),
           ("rdf", "xml", "RDF/XML"))
DCAT = rdflib.Namespace("http://www.w3.org/ns/dcat#")
MOD = rdflib.Namespace(SOURCE_BASE + "module/")


def new_graph():
    g = rdflib.Graph()
    for prefix, ns in (("wco", SOURCE_BASE), ("wco-mod", str(MOD)),
                       ("wco-cl", SOURCE_BASE + "code-list/"), ("rdfs", str(RDFS)),
                       ("owl", str(OWL)), ("skos", str(SKOS)), ("dcterms", str(DCTERMS)),
                       ("schema", str(SCHEMA)), ("dcat", str(DCAT))):
        g.bind(prefix, ns)
    return g


def describe(g, subjects):
    """Every triple whose subject is in `subjects`."""
    sub = new_graph()
    for s in subjects:
        for p, o in g.predicate_objects(s):
            sub.add((s, p, o))
    return sub


def closure(g, subject, kind, idx):
    """What an address answers with.

    A bare set of triples about one subject is rarely useful on its own: resolve a class and you
    want the properties that apply to it, resolve a code list and you want its values. So each kind
    of address answers with itself plus one step of what its page shows, and every borrowed term
    keeps its own rdfs:isDefinedBy, so a reader can see which module it really belongs to.

    Nothing is duplicated in the source. ontology/<module>.ttl still defines each term exactly once;
    the overlap exists only in what is generated from it.
    """
    subjects = [subject]
    if kind == "class":
        subjects += idx["class_props"].get(subject, [])
    elif kind == "property":
        subjects += [r for r in g.objects(subject, SCHEMA.rangeIncludes) if (r, RDF.type, SKOS.ConceptScheme) in g]
    elif kind == "code-list":
        subjects += idx["scheme_concepts"].get(subject, [])
    return describe(g, subjects)


def write_rdf(out, sub):
    """Serialise one resource three ways into its own directory."""
    for ext, fmt, _label in MACHINE:
        text = (sub.serialize(format=fmt, indent=1) if fmt == "json-ld"
                else sub.serialize(format=fmt))
        if BASE != SOURCE_BASE:
            text = text.replace(SOURCE_BASE, BASE)
        (out / f"index.{ext}").write_text(text)


def describe_page(url, name, description, kind=SCHEMA.WebPage):
    """A page that is not itself a vocabulary term still answers a machine, with a short description
    of what it is. Without this a reader asking for Turtle anywhere outside the vocabulary would get
    a 404 for a page that plainly exists."""
    sub = new_graph()
    me = rdflib.URIRef(url)
    sub.add((me, RDF.type, kind))
    sub.add((me, SCHEMA.name, rdflib.Literal(name, lang="en")))
    if description:
        sub.add((me, SCHEMA.description, rdflib.Literal(description, lang="en")))
    sub.add((me, SCHEMA.isPartOf, rdflib.URIRef(SOURCE_BASE)))
    return sub, me


def local(iri):
    return str(iri)[len(SOURCE_BASE):] if str(iri).startswith(SOURCE_BASE) else str(iri)


def publish(iri):
    return str(iri).replace(SOURCE_BASE, BASE)


def one(g, s, p):
    return next((str(o) for o in g.objects(s, p)), None)


def many(g, s, p):
    return sorted(str(o) for o in g.objects(s, p))


# The site has three parts, and the navigation says so: what the thing is, the vocabulary it
# publishes, and the messages assembled from that vocabulary. Every page belongs to exactly one.
SECTIONS = [
    ("documentation", "Documentation", [
        ("index", "Overview", ""),
        ("architecture", "Architecture", "docs/architecture"),
        ("governance", "Governance", "docs/governance"),
        ("maintenance", "How it is maintained", "docs/maintenance"),
        ("future", "Future improvements", "docs/future"),
    ]),
    ("vocabulary", "Vocabulary", [
        ("modules", "Modules", "modules/"),
        ("classes", "Classes", "classes/"),
        ("properties", "Properties", "properties/"),
        ("code-lists", "Code lists", "code-lists/"),
    ]),
    ("packages", "Information packages", [
        ("packages", "Overview", "packages/"),
        ("bip-dec", "Declarations", "packages/declarations/"),
        ("bip-lpco", "Licences and permits", "packages/licences-and-permits/"),
        ("aip", "Additional", "packages/additional/"),
        ("mdip", "Meta data", "packages/meta-data/"),
    ]),
]
SECTION_OF = {item: sec for sec, _, items in SECTIONS for item, _, _ in items}


def nav_html(current=None):
    section = SECTION_OF.get(current, "vocabulary")
    top = "".join(
        f'<a class="{"here" if sec == section else ""}" href="{BASE}{items[0][2]}">{html.escape(title)}</a>'
        for sec, title, items in SECTIONS)
    items = next(i for sec, _, i in SECTIONS if sec == section)
    sub = "".join(
        f'<a class="{"here" if slug == current else ""}" href="{BASE}{href}">{html.escape(label)}</a>'
        for slug, label, href in items)
    return f'<nav class="sitenav">{top}</nav><nav class="subnav">{sub}</nav>'


def page(title, subtitle, body, crumbs, current=None, extra_scripts=""):
    nav = " / ".join(f'<a href="{html.escape(h)}">{html.escape(t)}</a>' if h else html.escape(t) for t, h in crumbs)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)} — WCO Data Model vocabulary</title>
<meta name="description" content="{html.escape(subtitle)}">
<link rel="stylesheet" href="/vocab.css">
<link rel="stylesheet" href="/_pagefind/pagefind-ui.css">
<link rel="alternate" type="text/turtle" href="index.ttl">
<link rel="alternate" type="application/ld+json" href="index.jsonld">
<link rel="alternate" type="application/rdf+xml" href="index.rdf">
</head><body>
<header class="masthead"><div class="wrap">
  <a class="brand" href="{BASE}"><span class="brand-mark">WCO</span> Data Model vocabulary</a>
  <nav class="crumbs">{nav}</nav>
  <div id="search" class="search"></div>
</div>{nav_html(current)}</header>
<main class="wrap">{body}</main>
<footer class="wrap foot">
  <p>Generated from the WCO Data Model version {VERSION}. This address also answers as
     <a href="index.ttl">Turtle</a>, <a href="index.jsonld">JSON-LD</a> and
     <a href="index.rdf">RDF/XML</a>: ask for <code>text/turtle</code>,
     <code>application/ld+json</code> or <code>application/rdf+xml</code> and the same address
     serves the machine representation.</p>
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
{extra_scripts}
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

    write_rdf(out, closure(g, s, kind, idx))
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
        # A module answers with the whole module: every term it defines, in full, plus the terms
        # from elsewhere that its own classes depend on. Those overlaps are the reason: 318 of the
        # properties used by classes in the party module are defined in core, because a property
        # whose classes span modules is homed once rather than copied, and a graph that stopped at
        # the module boundary would leave most of party's properties undefined. Each borrowed term
        # still carries its own rdfs:isDefinedBy.
        me = MOD[module]
        own = [t for _kind, t in terms]
        borrowed = []
        for kind_, t in terms:
            if kind_ == "class":
                borrowed += idx["class_props"].get(t, [])
        # Close over value domains as well, whether the range is a code list or one of the value
        # object classes the core data types produce (wco:Amount and the rest live in data-types).
        # A module file with a dangling range is a module file someone has to chase.
        for prop in own + borrowed:
            borrowed += [r for r in g.objects(prop, SCHEMA.rangeIncludes)
                         if next(g.predicate_objects(r), None)]
        sub = describe(g, dict.fromkeys([me] + own + borrowed))
        write_rdf(out, sub)
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

    # The three categories each get an index. A code list is not a detail of a property: it is a
    # term in its own right, with its own address, its own values and its own page, exactly as a
    # class and a property are.
    module_of = lambda t: (one(g, t, RDFS.isDefinedBy) or "").rsplit("/", 1)[-1]
    mod_link = lambda t: (f'<a href="{BASE}module/{module_of(t)}">{html.escape(module_of(t))}</a>'
                          if module_of(t) else "")

    # Both indexes are grouped by the WCO superclass the model assigns each term to, because a flat
    # list of 283 classes or 441 properties is a wall rather than a way in.
    MODULE_ORDER = ["core", "party", "location", "document", "government", "transport",
                    "data-types", "code-lists", "governance"]
    MODULE_NOTE = {
        "core": "Cross-cutting terms, used throughout the model and not tied to one superclass.",
        "party": "The people and organisations in a transaction, and the roles they play.",
        "location": "Places, addresses and the geography of a movement.",
        "document": "Documents, their references and the attachments that travel with them.",
        "government": "Authorities, procedures and the decisions they take.",
        "transport": "Means of transport, equipment and the movement itself.",
        "data-types": "The core data types and their supplementary components.",
        "code-lists": "The code lists the model names, and the codes WCO owns.",
        "governance": "The vocabulary's own machinery: the annotations and the lifecycle scheme.",
    }

    def collection_rdf(url, title, lead, members):
        """An index page answers with what it indexes. rdfs:Container is plain RDF Schema, so a
        client can enumerate every class, property or code list from one address without this site
        inventing a vocabulary to say so."""
        sub, me = describe_page(url, title, lead, kind=RDFS.Container)
        for m in sorted(members):
            sub.add((me, RDFS.member, m))
            for p_, o_ in g.predicate_objects(m):
                sub.add((m, p_, o_))
        return sub

    def grouped_index(kind, title, lead, headers, row, col_classes, folder):
        terms = [t for t in kinds if kinds[t] == kind]
        by_module = defaultdict(list)
        for t in terms:
            by_module[module_of(t)].append(t)
        order = [m for m in MODULE_ORDER if by_module.get(m)] + \
                sorted(m for m in by_module if m not in MODULE_ORDER)
        jump = " · ".join(f'<a href="#{m}">{html.escape(m)} ({len(by_module[m])})</a>' for m in order)
        body = [f"<h1>{title} ({len(terms)})</h1>", f'<p class="definition">{lead}</p>',
                f'<p class="jump">{jump}</p>']
        for m in order:
            items = sorted(by_module[m], key=lambda t: display_label(g, t).lower())
            body.append(
                f'<section id="{html.escape(m)}"><h2>'
                f'<a class="modhead" href="{BASE}module/{m}">{html.escape(m)}</a> ({len(items)})</h2>'
                + (f'<p class="muted">{MODULE_NOTE[m]}</p>' if m in MODULE_NOTE else "")
                + table(headers, [row(t) for t in items], col_classes=col_classes) + "</section>")
        (DIST / folder).mkdir(parents=True, exist_ok=True)
        (DIST / folder / "index.html").write_text(page(
            title, lead, "".join(body),
            [("Vocabulary", BASE), (title, None)], current=folder))
        write_rdf(DIST / folder, collection_rdf(f"{SOURCE_BASE}{folder}/", title, lead, terms))
        counts["page"] += 1

    grouped_index(
        "class", "Classes",
        "A class is a group of information the model treats as a thing: a consignment, a party, a "
        "means of transport. Grouped by the WCO superclass each belongs to.",
        ["Class", "Definition", "Properties"],
        lambda c: (term_link(g, c), short(one(g, c, SKOS.definition), 140),
                   str(len(idx["class_props"].get(c, [])))),
        ["name", "prose", "num"], "classes")

    grouped_index(
        "property", "Properties",
        "A property is a single piece of information about a class. One property serves every class "
        "that uses it, so the same concept has one address however many classes carry it.",
        ["Property", "Definition", "Value", "Used by"],
        lambda t: (term_link(g, t), short(one(g, t, SKOS.definition), 110), render_range(g, t, limit=1),
                   str(len(list(g.objects(t, SCHEMA.domainIncludes))))),
        ["name", "prose", "value", "num"], "properties")

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
    write_rdf(out, collection_rdf(
        f"{SOURCE_BASE}code-lists/", "Code lists",
        "Every code list the WCO Data Model names, and what is known about each.",
        [t for t in kinds if kinds[t] == "code-list"]))
    counts["page"] += 1

    # An index of the modules, so the per-module pages are reachable from the masthead rather than
    # only from a term that happens to sit in one.
    mod_terms = defaultdict(lambda: defaultdict(list))
    for t, kind in kinds.items():
        m = module_of(t)
        if m:
            mod_terms[m][kind].append(t)
    order = [m for m in MODULE_ORDER if m in mod_terms] + sorted(m for m in mod_terms if m not in MODULE_ORDER)
    rows_mod = []
    for m in order:
        counts_by_kind = mod_terms[m]
        rows_mod.append((
            f'<a href="{BASE}module/{m}">{html.escape(m)}</a>',
            html.escape(MODULE_NOTE.get(m, "")),
            str(len(counts_by_kind.get("class", []))),
            str(len(counts_by_kind.get("property", []))),
            str(len(counts_by_kind.get("code-list", []))),
        ))
    (DIST / "modules").mkdir(parents=True, exist_ok=True)
    (DIST / "modules" / "index.html").write_text(page(
        "Modules", "How the WCO Data Model vocabulary is divided.",
        f"<h1>Modules ({len(order)})</h1>"
        '<p class="definition">The library marks every class and attribute with the WCO superclass '
        'it belongs to, and those marks divide the vocabulary. A module page gathers everything '
        'defined in one of them: its classes, its properties and its code lists together, where the '
        'category indexes cut the other way.</p>'
        + table(["Module", "Holds", "Classes", "Properties", "Code lists"], rows_mod,
                col_classes=["name", "prose", "num", "num", "num"]),
        [("Vocabulary", BASE), ("Modules", None)], current="modules"))
    write_rdf(DIST / "modules", collection_rdf(
        f"{SOURCE_BASE}modules/", "Modules", "How the WCO Data Model vocabulary is divided.",
        [MOD[m] for m in order]))
    counts["page"] += 1

    # The whole graph, for a machine asking at the root. The root HTML page comes from the Nextra
    # site, which is merged over this tree at deploy.
    write_rdf(DIST, g)

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
        url = SOURCE_BASE if item["slug"] == "index" else f'{SOURCE_BASE}docs/{item["slug"]}/'
        if item["slug"] != "index":
            write_rdf(out, describe_page(
                url, title, "The WCO Data Model published as linked data.")[0])
        counts["page"] += 1

    # The schemas and the message views, served beside the vocabulary. A package gets a landing page
    # that says what the message is and shows its shape, and a page per release that carries the
    # machine artefacts and the structure browser. The landing page is unversioned on purpose: it is
    # the stable place to link to a message, while each release has its own citable address.
    schemas_dir, views_dir = ROOT / "schemas", ROOT / "views"
    if (views_dir / "manifest.json").exists():
        manifest = json.loads((views_dir / "manifest.json").read_text())
        meta = json.loads((ROOT / "docs" / "derived-packages.json").read_text())
        pkg_meta, dip_meta = meta["packages"], meta["derived"]

        def rewrite(text):
            return text.replace(SOURCE_BASE, BASE) if BASE != SOURCE_BASE else text

        # /schemas/ stays a flat directory of every file, because that is where each schema's own
        # $id points and a published identifier is not moved.
        if schemas_dir.exists():
            flat = DIST / "schemas"
            flat.mkdir(parents=True, exist_ok=True)
            for f in sorted(schemas_dir.iterdir()):
                if f.name == "build-report.json":
                    continue
                (flat / f.name).write_text(rewrite(f.read_text()))
                counts["schema file"] += 1

        def message_url(pslug, mslug, version=None):
            tail = "" if mslug == "base" else f"{mslug}/"
            return f"{BASE}packages/{pslug}/{tail}" + (f"{version}/" if version else "")

        def message_dir(pslug, mslug, version=None):
            parts = [DIST, "packages", pslug] + ([] if mslug == "base" else [mslug])
            if version:
                parts.append(version)
            out = pathlib.Path(*parts)
            out.mkdir(parents=True, exist_ok=True)
            return out

        def stat_rows(st):
            return [
                ("Positions", f'{st["nodes"]:,}'),
                ("Classes", f'{st["classes"]:,}'),
                ("Elements", f'{st["elements"]:,}'),
                ("Repeating positions", f'{st["repeating"]:,}'),
                ("Depth", f'{st["maxDepth"]} levels'),
                ("Mandatory positions", "none" if not st["required"] else f'{st["required"]:,}'),
            ]

        def facts_table(rows):
            body = "".join(
                f'<tr><th>{html.escape(k)}</th><td>{v}</td></tr>' for k, v in rows if v)
            return f'<table class="facts">{body}</table>'

        def top_level_table(entry, pslug, mslug):
            """Classes and elements are tabulated apart. The classes are the structure of the
            message; the elements at the top level are its header, and mixing the two buries the
            structure in a list of dates."""
            rel = message_url(pslug, mslug, VERSION)

            def rows_for(kind):
                return [(
                    f'<a href="{rel}#{html.escape(t["path"])}"><b>{html.escape(t["name"])}</b></a>',
                    html.escape(t["card"]),
                    f'{t["below"]:,}' if t["below"] else "",
                    html.escape(t["definition"]),
                ) for t in entry["top_level"] if t["type"] == kind]

            out = []
            classes, elements = rows_for("C"), rows_for("E")
            if classes:
                out.append(f'<h3>Classes ({len(classes)})</h3>'
                           + table(["Name", "Occurs", "Positions inside", "Definition"], classes,
                                   col_classes=["name", "code", "num", "prose"]))
            if elements:
                out.append(f'<h3>Elements ({len(elements)})</h3>'
                           + table(["Name", "Occurs", "", "Definition"], elements,
                                   col_classes=["name", "code", "num", "prose"]))
            return "".join(out)

        def diagram_figure(entry, pslug, mslug, out):
            if not entry.get("diagram"):
                return ""
            src = ROOT / "diagrams" / entry["diagram"]
            if not src.exists():
                return ""
            (out / "diagram.svg").write_text(src.read_text())
            counts["message file"] += 1
            url = message_url(pslug, mslug) + "diagram.svg"
            if entry["diagram_boxes"] <= 12 and entry.get("diagram_cut"):
                note = ("Each box is one vocabulary module, listing the classes of this message that "
                        "belong to it. The top level is too wide to draw class by class, and the "
                        "module is the model's own grouping rather than a convenience of this page.")
            elif entry.get("diagram_cut"):
                note = ("Classes only, to the depth that stays readable. A shaded box has further "
                        "classes inside it.")
            else:
                note = "Every class in the message, with the number of times each may occur."
            return (f'<section><h2>Conceptual view</h2>'
                    f'<figure class="diagram"><a href="{url}">'
                    f'<img src="{url}" alt="Classes of {html.escape(entry["title"])}"></a>'
                    f'<figcaption>{note} Elements are left out; the structure browser has them. '
                    f'<a href="{url}">Open the diagram</a>.</figcaption></figure></section>')

        def versions_table(pslug, mslug, st):
            rel = message_url(pslug, mslug, VERSION)
            rows = [(
                f'<a href="{rel}"><b>{VERSION}</b></a>',
                "current",
                f'{st["nodes"]:,}',
                f'<a href="{rel}schema.json">schema.json</a>',
                f'<a href="{rel}context.jsonld">context.jsonld</a>',
            )]
            return table(["Version", "Status", "Positions", "JSON Schema", "JSON-LD context"], rows,
                         col_classes=["code", "mod", "num", "name", "name"])

        def publish_artefacts(out, entry, pslug):
            """The machine files beside the release page, each with the digest of what was published."""
            digests = {}
            sources = [("schema.json", schemas_dir / entry["schema"]),
                       ("context.jsonld", schemas_dir / entry["context"]),
                       ("tree.json", views_dir / pslug / entry["slug"] / "tree.json")]
            for name, src in sources:
                if not src.exists():
                    continue
                text = rewrite(src.read_text())
                (out / name).write_text(text)
                digests[name] = hashlib.sha256(text.encode("utf-8")).hexdigest()
                counts["message file"] += 1
            return digests

        for key, pkg in manifest.items():
            pslug = pkg["slug"]
            pm = pkg_meta.get(key, {})
            base = pkg["messages"]["base"]
            derived = [m for s, m in sorted(pkg["messages"].items()) if s != "base"]

            for entry in [base] + derived:
                mslug = entry["slug"]
                is_derived = entry["derived"]
                dm = dip_meta.get(mslug, {}) if is_derived else {}
                name = dm.get("name", entry["title"]) if is_derived else pm.get("title", entry["title"])
                title = f'{name} {"derived package" if is_derived else "Information Package"}'
                st = entry["stats"]
                out = message_dir(pslug, mslug)
                rel = message_url(pslug, mslug, VERSION)

                editorial = (' <span class="editorial" title="Our wording, not WCO\'s">gloss</span>'
                             if dm.get("source") == "editorial" else "")
                lead = (html.escape(dm.get("gloss", "")) + editorial if is_derived
                        else html.escape(pm.get("description", entry["title"])))
                rows = [("Derived from" if is_derived else "Kind",
                         f'<a href="{message_url(pslug, "base")}">'
                         f'{html.escape(pm.get("title", key))}</a>' if is_derived else
                         html.escape(pm.get("subtitle", "Information Package")))]
                if is_derived:
                    rows.append(("Group in the workbook",
                                 html.escape(dm.get("group") or entry.get("group", ""))))
                    share = st["nodes"] * 100.0 / max(base["stats"]["nodes"], 1)
                    rows.append(("Share of the package",
                                 f'{st["nodes"]:,} of {base["stats"]["nodes"]:,} positions '
                                 f'({share:.1f}%)'))
                rows += stat_rows(st)
                rows.append(("Current version", f'<a href="{rel}">{VERSION}</a>, '
                                                f'from WCO Data Model {VERSION}'))
                rows.append(("Source", html.escape(pkg["source"]["file"])))

                body = [f'<h1>{html.escape(title)}</h1>',
                        f'<p class="definition">{lead}</p>',
                        facts_table(rows),
                        diagram_figure(entry, pslug, mslug, out)]
                if st["required"] == 0:
                    body.append(
                        '<p class="aside">Nothing in this message is mandatory: every position is '
                        'optional in the model. Obligation is set by the regulation or the national '
                        'profile that uses the message, which is what a derived package begins to '
                        'do.</p>')
                body.append(f'<section><h2>Versions</h2>'
                            '<p class="muted">The message is versioned even though the vocabulary is '
                            'not, because a format has to be pinned before anyone can validate '
                            'against it. Each release keeps its own address.</p>'
                            + versions_table(pslug, mslug, st) + '</section>')
                body.append(f'<section><h2>Top level</h2>'
                            f'<p class="muted">What sits directly inside '
                            f'<code>{html.escape(entry["top_level"][0]["path"].split("/")[0])}</code>. '
                            f'Follow a name to that point in the structure browser.</p>'
                            + top_level_table(entry, pslug, mslug) + '</section>')
                if not is_derived and derived:
                    drows = []
                    for d in derived:
                        d_meta = dip_meta.get(d["slug"], {})
                        mark = (' <span class="editorial" title="Our wording, not WCO\'s">gloss</span>'
                                if d_meta.get("source") == "editorial" else "")
                        drows.append((
                            f'<a href="{message_url(pslug, d["slug"])}">'
                            f'<b>{html.escape(d_meta.get("name", d["title"]))}</b></a>{mark}',
                            html.escape(d_meta.get("group") or d.get("group", "")),
                            html.escape(d_meta.get("gloss", "")),
                            f'{d["stats"]["nodes"]:,}',
                        ))
                    body.append(
                        f'<section><h2>Derived packages ({len(derived)})</h2>'
                        '<p class="muted">The same tree cut down to the positions one message marks, '
                        'with the ancestors those positions need. Each is generated from this package '
                        'rather than maintained separately, so it cannot drift from it.</p>'
                        + table(["Message", "Group", "What it is", "Positions"], drows,
                                col_classes=["name", "mod", "prose", "num"])
                        + '<p class="muted">Where an entry is marked '
                        '<span class="editorial">gloss</span> the explanation is ours: the workbook '
                        'names the package but never spells the abbreviation out.</p></section>')
                crumbs = [("Vocabulary", BASE), ("Information packages", f"{BASE}packages/")]
                if is_derived:
                    crumbs.append((pm.get("title", key), message_url(pslug, "base")))
                crumbs.append((name, None))
                (out / "index.html").write_text(page(title, lead, "".join(body), crumbs, current=key))
                msg_url = f'{SOURCE_BASE}{message_url(pslug, mslug)[len(BASE):]}'
                msub, mme = describe_page(msg_url, title, lead, kind=DCAT.Dataset)
                msub.add((mme, DCTERMS.hasVersion, rdflib.Literal(VERSION)))
                msub.add((mme, DCAT.landingPage, mme))
                if is_derived:
                    msub.add((mme, DCTERMS.isPartOf,
                              rdflib.URIRef(f'{SOURCE_BASE}packages/{pslug}/')))
                write_rdf(out, msub)
                counts["page"] += 1

                # The release page: machine artefacts, their digests, and the browser.
                rout = message_dir(pslug, mslug, VERSION)
                digests = publish_artefacts(rout, entry, pslug)
                files = [
                    ("JSON Schema", "schema.json", "Validates an instance of this message."),
                    ("JSON-LD context", "context.jsonld",
                     "Binds each tag in the message to the published term that defines it."),
                    ("Structure", "tree.json",
                     "The message as data: every position with its cardinality, tags and term."),
                ]
                frows = []
                for label, fname, what in files:
                    if fname not in digests:
                        continue
                    frows.append((
                        f'<b>{label}</b><br><span class="muted">{what}</span>',
                        f'<a href="{rel}{fname}"><code>{rel}{fname}</code></a>',
                        f'<code class="digest">{digests[fname][:16]}…</code>',
                    ))
                rbody = [
                    f'<h1>{html.escape(name)} {VERSION}</h1>',
                    f'<p class="definition">Release {VERSION} of the '
                    f'<a href="{message_url(pslug, mslug)}">{html.escape(title)}</a>, generated from '
                    f'WCO Data Model {VERSION}.</p>',
                    '<section><h2>Machine artefacts</h2>'
                    '<p class="muted">These addresses are permanent. A later WCO release publishes '
                    'under its own version rather than replacing these files, so a document '
                    'validated today can be validated the same way later.</p>'
                    + table(["File", "Address", "SHA-256"], frows,
                            col_classes=["name", "prose", "code"])
                    + '<p class="muted">The digest is of the file as published. Recording it with a '
                    'document fixes which schema and which context that document was written '
                    'against.</p></section>',
                    f'<section><h2>Structure</h2>'
                    '<p class="muted">Every position in the message. Classes are shown in bold, '
                    'elements plain; the number on the right is how many classes and elements sit '
                    'inside. Select a position for its definition, its tags, and the vocabulary term '
                    'that defines it.</p>'
                    f'<div class="browser" data-tree="{rel}tree.json" data-pagefind-ignore>'
                    '<div class="browser-bar">'
                    '<input class="browser-filter" type="search" '
                    'placeholder="Filter by name, tag or WCO ID" aria-label="Filter the structure">'
                    '<button type="button" data-act="two">Two levels</button>'
                    '<button type="button" data-act="three">Three</button>'
                    '<button type="button" data-act="collapse">Collapse</button>'
                    '<span class="browser-count"></span></div>'
                    '<div class="browser-panes"><div class="browser-tree" role="tree" '
                    'aria-label="Message structure">Loading the structure…</div>'
                    '<aside class="browser-detail"><p class="muted">Select a position to see what it '
                    'is.</p></aside></div></div>'
                    '<noscript><p class="aside">The structure browser needs JavaScript. Without it, '
                    f'<a href="{rel}tree.json">tree.json</a> carries the same content, and the top '
                    f'level is tabulated on the <a href="{message_url(pslug, mslug)}">package '
                    'page</a>.</p></noscript></section>',
                    '<section><h2>How the schema was derived</h2><p class="muted">A class becomes an '
                    'object, an element becomes a typed property, an unbounded maximum becomes an '
                    'array, and a minimum of one becomes required. The cardinality is the model\'s '
                    'own: it comes from the Number of Occurrences column of the package workbook, '
                    'which neither the library nor the overall information structure carries.</p>'
                    + facts_table([
                        ("Positions bound to a vocabulary term",
                         f'{st["bound"]:,} of {st["nodes"]:,}'),
                        ("Positions with a code list", f'{st["coded"]:,}'),
                        ("Mandatory positions",
                         "none in the model" if not st["required"] else f'{st["required"]:,}'),
                    ]) + '</section>',
                ]
                (rout / "index.html").write_text(page(
                    f"{name} {VERSION}", f"Release {VERSION} of the {name} message.",
                    "".join(rbody),
                    crumbs[:-1] + [(name, message_url(pslug, mslug)), (VERSION, None)],
                    current=key, extra_scripts=f'<script src="{BASE}message-browser.js"></script>'))
                # The release is a dataset with distributions, which is what DCAT is for. A client
                # that negotiates this address gets the addresses of the schema, the context and the
                # structure, with the digest of each, rather than having to read the page.
                rel_url = f'{SOURCE_BASE}{rel[len(BASE):]}'
                rsub, rme = describe_page(
                    rel_url, f"{name} {VERSION}", f"Release {VERSION} of the {name} message.",
                    kind=DCAT.Dataset)
                rsub.add((rme, DCTERMS.hasVersion, rdflib.Literal(VERSION)))
                rsub.add((rme, DCTERMS.isPartOf, rdflib.URIRef(msg_url)))
                for fname, media in (("schema.json", "application/schema+json"),
                                     ("context.jsonld", "application/ld+json"),
                                     ("tree.json", "application/json")):
                    if fname not in digests:
                        continue
                    dist = rdflib.URIRef(rel_url + fname)
                    rsub.add((rme, DCAT.distribution, dist))
                    rsub.add((dist, RDF.type, DCAT.Distribution))
                    rsub.add((dist, DCAT.downloadURL, dist))
                    rsub.add((dist, DCAT.mediaType, rdflib.Literal(media)))
                    rsub.add((dist, SCHEMA.sha256, rdflib.Literal(digests[fname])))
                write_rdf(rout, rsub)
                counts["page"] += 1

        # The overview.
        rows_over = []
        for key in ("bip-dec", "bip-lpco", "aip", "mdip"):
            pkg = manifest.get(key)
            if not pkg:
                continue
            pm, st = pkg_meta.get(key, {}), pkg["messages"]["base"]["stats"]
            n_derived = len(pkg["messages"]) - 1
            rows_over.append((
                f'<a href="{message_url(pkg["slug"], "base")}">'
                f'<b>{html.escape(pm.get("title", key))}</b></a>',
                html.escape(pm.get("description", "")),
                f'{st["nodes"]:,}',
                f'{st["classes"]:,}',
                str(n_derived) if n_derived else "",
            ))
        all_derived = []
        for key in ("bip-dec", "bip-lpco", "aip", "mdip"):
            pkg = manifest.get(key)
            if not pkg:
                continue
            for slug, m in sorted(pkg["messages"].items()):
                if slug == "base":
                    continue
                d_meta = dip_meta.get(slug, {})
                mark = (' <span class="editorial" title="Our wording, not WCO\'s">gloss</span>'
                        if d_meta.get("source") == "editorial" else "")
                all_derived.append((
                    f'<a href="{message_url(pkg["slug"], slug)}">'
                    f'<b>{html.escape(d_meta.get("name", m["title"]))}</b></a>{mark}',
                    f'<a class="quiet" href="{message_url(pkg["slug"], "base")}">'
                    f'{html.escape(pkg_meta.get(key, {}).get("title", key))}</a>',
                    html.escape(d_meta.get("gloss", "")),
                    f'{m["stats"]["nodes"]:,}',
                ))
        body = (
            "<h1>Information packages</h1>"
            '<p class="definition">The vocabulary says what a term means. An Information Package '
            'says how terms are assembled into a message, and how many times each piece may occur. '
            'A JSON Schema, a JSON-LD context and a browsable structure are generated for each, and '
            'for every derived package that subsets it.</p>'
            + table(["Package", "Covers", "Positions", "Classes", "Derived"], rows_over,
                    col_classes=["name", "prose", "num", "num", "num"])
            + '<section><h2>Base, derived, and what that means in practice</h2>'
            '<p class="muted">A Base Information Package is a catalogue: everything a declaration or '
            'a licence could carry, with every position optional. Nothing in any of the four '
            'packages is mandatory, so a schema generated straight from one will accept an almost '
            'empty document. Obligation arrives with the regulation or the national profile that '
            'uses the message.</p>'
            '<p class="muted">A derived package is the first narrowing: the workbook marks which '
            'positions a particular message uses, and the Maritime API package is 86 positions of '
            'the Declaration\'s 9,064. That is the number worth knowing before implementing.</p>'
            '</section>'
            f'<section><h2>Derived packages ({len(all_derived)})</h2>'
            + table(["Message", "From", "What it is", "Positions"], all_derived,
                    col_classes=["name", "mod", "prose", "num"])
            + '<p class="muted">Where an entry is marked <span class="editorial">gloss</span> the '
            'explanation is ours: the workbook names the package but never spells the abbreviation '
            'out.</p></section>')
        out = DIST / "packages"
        out.mkdir(parents=True, exist_ok=True)
        (out / "index.html").write_text(page(
            "Information packages", "How the WCO Data Model assembles terms into messages.",
            body, [("Vocabulary", BASE), ("Information packages", None)], current="packages"))
        osub, ome = describe_page(
            f"{SOURCE_BASE}packages/", "Information packages",
            "How the WCO Data Model assembles terms into messages.", kind=RDFS.Container)
        for pkey, pk in manifest.items():
            for mslug_ in pk["messages"]:
                tail = "" if mslug_ == "base" else f"{mslug_}/"
                osub.add((ome, RDFS.member,
                          rdflib.URIRef(f'{SOURCE_BASE}packages/{pk["slug"]}/{tail}')))
        write_rdf(out, osub)
        counts["page"] += 1
        (DIST / "message-browser.js").write_text((ROOT / "assets" / "message-browser.js").read_text())

    # Every directory holding a page must hold its machine representations too. The edge function
    # is one rule with no list of exceptions, so a page without them would 404 for a client that
    # asked for Turtle, and nothing else in the build would notice.
    incomplete = []
    for d in sorted(p for p in DIST.rglob("*") if p.is_dir()):
        if "_pagefind" in d.parts or "schemas" in d.parts:
            continue
        if not (d / "index.html").exists():
            continue
        missing = [e for e, _f, _l in MACHINE if not (d / f"index.{e}").exists()]
        if missing:
            incomplete.append((d.relative_to(DIST), missing))
    counts["negotiable page"] = sum(
        1 for d in [DIST] + [p for p in DIST.rglob("*") if p.is_dir()]
        if (d / "index.html").exists() and all((d / f"index.{e}").exists() for e, _f, _l in MACHINE))
    if incomplete:
        print(f"  {len(incomplete)} pages answer only as HTML:")
        for rel, missing in incomplete[:10]:
            print(f"    /{rel}/  missing {', '.join(missing)}")
        return 1

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
.subnav{background:#fff;border-bottom:1px solid var(--line)}
.subnav a{display:inline-block;color:var(--muted);text-decoration:none;padding:9px 16px;font-size:14px}
.subnav a:hover{color:var(--brand)}
.subnav a.here{color:var(--brand);font-weight:600;box-shadow:inset 0 -3px 0 var(--brand)}
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
.c-mod{width:110px;white-space:nowrap}
figure.diagram{margin:14px 0 6px;padding:14px;border:1px solid var(--line);border-radius:10px;background:#fff;text-align:center}
figure.diagram img{max-width:100%;max-height:620px;height:auto}
figure.diagram figcaption{font-size:14px;color:var(--muted);margin-top:12px;text-align:left}
p.aside{border-left:3px solid var(--brand);background:var(--bg);padding:10px 14px;margin:14px 0;font-size:15px}
code.digest{font-size:12.5px;color:var(--muted)}
.browser{border:1px solid var(--line);border-radius:10px;overflow:hidden;margin:14px 0;background:#fff}
.browser-bar{display:flex;gap:8px;align-items:center;flex-wrap:wrap;padding:10px 12px;background:var(--bg);border-bottom:1px solid var(--line)}
.browser-bar input{flex:1 1 240px;min-width:180px;padding:7px 10px;border:1px solid var(--line);border-radius:6px;font:inherit;font-size:14px}
.browser-bar button{padding:6px 11px;border:1px solid var(--line);border-radius:6px;background:#fff;font:inherit;font-size:13.5px;color:var(--brand);cursor:pointer}
.browser-bar button:hover{border-color:var(--brand)}
.browser-count{font-size:13px;color:var(--muted);margin-left:auto}
.browser-panes{display:flex;align-items:stretch;min-height:320px}
.browser-tree{flex:1 1 58%;max-height:560px;overflow:auto;padding:8px 4px 14px;font-size:14.5px}
.browser-detail{flex:1 1 42%;border-left:1px solid var(--line);background:#fcfdff;padding:14px 16px;max-height:560px;overflow:auto}
.browser-detail h3{margin:0 0 4px;font-size:17px}
.browser-detail .bpath{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12.5px;color:var(--muted);word-break:break-all;margin:0 0 10px}
.browser-detail .bdef{margin:0 0 10px;font-size:14.5px}
.browser-detail .brem{margin:0 0 10px;font-size:13.5px;color:var(--muted)}
.browser-detail table.facts th{width:140px;font-size:13px;padding:6px 10px 6px 0}
.browser-detail table.facts td{font-size:13.5px}
.browser .kids{margin-left:15px;border-left:1px dotted var(--line);padding-left:5px}
.browser .row{display:flex;gap:7px;align-items:baseline;padding:3px 8px;border-radius:5px;cursor:pointer}
.browser .row:hover{background:var(--bg)}
.browser .row.on{background:#e8f1fc;outline:1px solid #bcd6f2}
.browser .twisty{width:12px;flex:0 0 12px;color:var(--muted);font-size:11px;line-height:1.6}
.browser .nm{color:var(--ink)}
.browser .nm.cls{font-weight:600;color:var(--brand-dark)}
.browser .tag{font-size:12px;color:var(--muted);background:var(--bg);border:1px solid var(--line);border-radius:4px;padding:0 4px}
.browser .card{font-size:12px;color:var(--muted);font-variant-numeric:tabular-nums}
.browser .kidcount{font-size:11.5px;color:#8294a6;margin-left:auto;white-space:nowrap}
.browser-failed .browser-tree{color:var(--muted);padding:18px}
@media (max-width:760px){.browser-panes{flex-direction:column}.browser-detail{border-left:0;border-top:1px solid var(--line)}}
.jump{font-size:14px;color:var(--muted);margin:0 0 18px}
.jump a{margin-right:2px}
a.modhead{text-decoration:none}
a.modhead:hover{text-decoration:underline}
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
