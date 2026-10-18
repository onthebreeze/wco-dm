# How this site is maintained

Everything published here is generated. Nothing in `ontology/` or `dist/` is edited by hand, and a
change to either is made by changing the generator and running it again.

Three pieces: a source of record, a generator, and a tree of files served from object storage behind
a content delivery network. Nothing runs at request time except a small function at the edge.

## The pipeline

```
raw-data/*.xlsx          the WCO workbooks, unmodified
      |  extract.py
      v
intermediate/*.json      one record per class, attribute, data type, code list and occurrence,
      |                  each carrying its source file, sheet and row
      |  build_vocabulary.py                 |  extract_packages.py
      v                                      v
ontology/*.ttl           the vocabulary     intermediate/packages/*.json
      |                                      |  build_schemas.py -> schemas/
      |                                      |  build_package_views.py -> views/, diagrams/
      |  build_site.py  <--------------------+
      v
dist/<Term>/index.{html,ttl,jsonld}    one directory per term
dist/packages/<package>/[<message>/]<version>/   one directory per release
```

The vocabulary and the messages are built from the same source but down separate paths, and only
the site generator sees both. That is why a change to how messages are published cannot disturb a
term, and why `ontology/` stays the thing to read in a diff.

The narrative pages you are reading come out of the same generator, from Markdown in `docs/`, so the
whole site is one toolchain and one visual language.

## Rebuilding from a new WCO release

```
python3 scripts/extract.py          # 1. read the new workbooks in raw-data/
python3 scripts/fidelity_check.py   # 2. check that nothing was lost on the way in
python3 scripts/build_vocabulary.py # 3. regenerate the vocabulary
python3 scripts/validate_vocab.py   # 4. check it holds together
python3 scripts/map_to_unece.py     # 5. refresh mapping candidates, keeping decisions
python3 scripts/extract_packages.py # 6. read the four Information Package workbooks
python3 scripts/build_schemas.py    # 7. generate a schema and context per package
python3 scripts/validate_schemas.py # 8. check each one is valid and still rejects something
python3 scripts/build_package_views.py  # 9. the browsable tree and the diagram per message
python3 scripts/build_site.py       # 10. build the pages
```

`scripts/build_all.sh` runs the lot, including the search index. The diff in `ontology/` after step
3 is the review: it shows exactly what changed in the model.

## The checks, and why each exists

`fidelity_check.py` reads the workbooks again, independently of the extractor, and compares counts
and names. A pipeline that only compares its output to its own intermediate proves nothing.

`validate_vocab.py` runs eight gates over the generated graph: every term labelled, every term with
a status and a module, every property with a domain and a range, every reference resolving, every
term citing its source, no class declared twice, and every class from the library present with
nothing invented. It earned its place by catching three properties whose range pointed at classes
the generator had not yet emitted.

## The schema gate needs one extra library

`validate_schemas.py` needs `jsonschema`, which the rest of the pipeline does not. It skips with a
message rather than failing when the library is absent, so a plain checkout still builds, but a
release should run it:

```
python3 -m venv .venv && .venv/bin/pip install jsonschema
.venv/bin/python scripts/validate_schemas.py
```

It checks two things. That each schema is valid draft 2020-12, and that each one still rejects an
instance carrying a field the model does not have — because a schema that accepts everything is
worse than no schema, since it looks like a control.

## The message views

`build_package_views.py` writes two things per message, for the four packages and the sixteen
derived packages alike.

`views/<package>/<message>/tree.json` is the message as data: every position with its cardinality,
its tags, the vocabulary term it is bound to and the code list its values come from. Names and
definitions are pooled into one string table and referenced by index, because the Declaration
repeats 243 classes over 1,847 positions and sending each one again would multiply the file for no
extra meaning. It is minified because it is a transport format for the browser widget; the
reviewable form of the same content is `intermediate/packages/*.json`.

`diagrams/<package>-<message>.puml` is the conceptual view, rendered to SVG when plantuml is on the
path and committed so that the site builds without it. There are two shapes. A message whose top
level is small enough is drawn class by class, as deep as stays readable. The three Base packages
are not: the Declaration has 67 classes directly under its root, which graphviz lays out in one
rank 8,000 pixels wide. Those are drawn a level up, as the root and the vocabulary modules its
top-level classes belong to, with each module box listing them.

The widget itself is `assets/message-browser.js`, which is plain JavaScript with no dependency and
no build step. It renders rows only as they are opened, so the 9,064 positions of the Declaration
are never all in the page at once.

## Why the pages are generated rather than routed

The site is a page per term and a page per code value, which is close to a thousand pages from
release 4.3.0 alone. A framework that renders a route per term is slow for no benefit, and none of
them emits the
`index.ttl` and `index.jsonld` that have to sit beside each `index.html` for content negotiation to
work.

A documentation framework was tried first and removed. Four hand-written pages did not justify 439
packages and an app-router contract that would not render, and keeping one generator means one thing
to maintain rather than two that have to be kept looking alike.

## How negotiation works

A term is a directory. The edge function reads the `Accept` header and rewrites the request to
`/index.html`, `/index.ttl` or `/index.jsonld` before the cache is consulted, so each representation
is a separate cache entry and no `Vary` handling is needed at the origin.

That rewrite is the only logic in the request path. The origin is a private bucket; the function is
a few lines; there is no server.

## Search

The local index is built by Pagefind over the finished tree, so it covers the term pages as well as
these ones. It is a static index served from the same bucket: no search service, no query logging,
and it works from a file system as well as from the web.

## The namespace

Terms are minted under a WCO-owned namespace, and the build can serve them anywhere:

```
WCO_BASE=https://test-wcodm.trade-commons.org/ python3 scripts/build_site.py
```

The identifiers in the source never change, so moving the site does not re-home a single term. The
test deployment and the eventual production deployment publish the same identifiers.

## Deciding a mapping

`mappings/wco-to-unece.csv` is the ledger. Edit the decision column, set `decided_by` to `human`,
and run `scripts/map_to_unece.py` again. A human decision survives later runs; the script's own
guesses do not, so thresholds can be changed without losing review work.

## Two things to know before changing the generator

**Properties are shared, except where their values disagree.** WCO names a property inside its
class, so `id` occurs 174 times. Attributes that share a name and a core data type become one
property with many `schema:domainIncludes`, which is how vocab.unece.org models the same ground, and
each class-specific definition survives as a scope note.

Where that merge produced a property whose classes code against different lists, it is undone:
`Seal.typeCode` and `Package.typeCode` are different value domains, so they are different
properties. Twelve properties were affected and the split is recorded in
`mappings/split-properties.csv`.

`WCO_SPLIT` chooses how:

| Value | Properties | What it does |
|---|---|---|
| `domain` (default) | 441 | One property per distinct value domain, so classes that genuinely share a domain keep sharing a term |
| `class` | 737 | One property per class, as the WCO Data Model itself is organised |
| `none` | 409 | Leave them merged, carrying every domain |

Both reach the same end, no property with more than one value domain. `class` is duplicative:
`identificationIdentifier` has six value domains across 173 classes and would become 173 properties
differing in name only.

A property split by domain is named after the list it codes against, with the `List` suffix dropped,
so `AddressTypeCodeList` gives `addressTypeCode`. Where the list is one the register does not hold,
its name is the external reference rather than the concept - "UN/EDIFACT code list 3035" would give
`unEdifactCodeList3035` - so the class supplies the name instead.

**Identifiers do not move.** The source carries a WCO-owned namespace and the build rewrites it for
whatever host is serving. Changing the base in the source would re-home every published term.
