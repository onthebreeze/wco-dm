# CLAUDE.md

Guidance for Claude Code working in this repository.

## What this is

The World Customs Organization (WCO) Data Model, published as a navigable, resolvable,
content-negotiable linked data vocabulary. Four releases are held here - 4.0.0, 4.1.0, 4.2.0 and
4.3.0 - and everything published is generated from the WCO workbooks in `raw-data/`.

It is not a software project. There is no application, no test framework and no package manager.
There is a pipeline of Python scripts, a set of gates that stop the build, and a static site.

The site is at `https://vocabulary.wcoomd.org/` in the identifiers it mints, and will be deployed
first to `https://test-wcodm.trade-commons.org/`. Neither is live yet.

## The one thing to understand first

**Nothing published here is edited by hand.** The vocabulary, the schemas, the structures, the
diagrams and the pages are all generated. A change to any of them is a change to a script followed
by a rebuild. Editing `ontology/*.ttl` or anything under `dist/` is always wrong: the next build
discards it.

The flow is one direction:

```
raw-data/v<release>/*.xlsx          the WCO workbooks, as published and unmodified
   | extract.py, extract_packages.py
   v
intermediate/v<release>/*.json      normalised records, each carrying file, sheet and row
   | build_vocabulary.py                    | build_schemas.py, build_package_views.py
   v                                        v
ontology/*.ttl                        schemas/, views/, diagrams/
   |                                        |
   +------------- build_site.py ------------+
                       v
                     dist/                  the published tree
```

`ontology/*.ttl` is the hinge. Everything a reader or a machine sees of the vocabulary is generated
from those ten files, and they are themselves generated from the workbooks. That direction reverses
only at a hypothetical WCO Data Model 5.0, which `docs/future.md` argues for; today the workbooks
are the source of record and this site is a rendering of them.

## Layout

| Path | Holds | Edited by hand? |
|---|---|---|
| `raw-data/v<release>/` | The WCO workbooks, as published | Never. Source. |
| `intermediate/v<release>/` | Normalised records with provenance | No. Generated. |
| `ontology/*.ttl` | The vocabulary: ten modules | No. Generated. |
| `schemas/` | A JSON Schema and a JSON-LD context per message per release | No. Generated. |
| `views/v<release>/` | `tree.json` per message: the structure the browser widget reads | No. Generated. |
| `diagrams/` | A `.puml` and its `.svg` per message per release | No. Generated. |
| `mappings/` | The ledger of mappings to the UN/CEFACT vocabulary | The decision column, yes. |
| `docs/` | The narrative pages, in Markdown, plus `derived-packages.json` | Yes. Authored. |
| `assets/` | `message-browser.js`, the structure browser | Yes. Authored. |
| `scripts/` | The generator and its gates | Yes. Authored. |
| `deploy/` | The pipeline and the uploader, written but not yet run | Yes. Authored. |
| `design/` | The design note, the plan, and observations about the model | Yes. Authored. |
| `dist/` | The built site, about 117MB | No. Generated, and gitignored. |

The generated artefacts are committed on purpose. A rebuild from a new WCO release shows as a diff
in `ontology/` and `schemas/`, and that diff is the review.

## Building

```bash
scripts/build_all.sh                                    # everything, at the WCO namespace
WCO_BASE=http://localhost:8099/ scripts/build_all.sh    # for a local preview
```

About 45 seconds end to end. The stages, in order:

| Stage | Script | What it does |
|---|---|---|
| 1 | `extract.py --all` | Reads every release's Library and Overall Information Structure |
| 2 | `fidelity_check.py --all` | Re-reads the workbooks independently and compares |
| 3 | `build_vocabulary.py` | One vocabulary from every release, with a lifecycle per term |
| 4 | `validate_vocab.py` | Eight gates over the generated graph |
| 5 | `map_to_unece.py` | Refreshes mapping candidates, keeping human decisions |
| 6 | `extract_packages.py --all` | The four Information Package workbooks of every release |
| 7 | `build_schemas.py` | A schema and context per message per release |
| 8 | `validate_schemas.py` | Each is valid draft 2020-12 and still rejects an unknown field |
| 9 | `build_package_views.py` | The browsable tree and the conceptual diagram per message |
| 10 | `build_site.py` | The pages |
| 11 | `pagefind` | The search index |

Between 9 and 10 the script also fails the build if any committed artefact carries a build-time
hostname, because `WCO_BASE` must never reach `ontology/`, `schemas/` or `views/`.

### Previewing

```bash
python3 scripts/serve.py 8099      # serves dist/ the way the edge will
```

`serve.py` applies the same routing rule as the CloudFront function: collapse a trailing slash,
pass through anything whose last segment ends in a file extension, otherwise append
`/index.<ext>` chosen by `Accept`. If the two ever disagree, `serve.py` is the one that is wrong.

A plain static server will serve the HTML but not content negotiation, which is most of the point.

### Requirements

`python3` with `openpyxl`, `rdflib` and `markdown`. `plantuml` for the diagrams, which are
committed so a build without it still works. `npx` for Pagefind. `jsonschema` for stage 8, which
skips with a message when it is absent:

```bash
python3 -m venv .venv && .venv/bin/pip install jsonschema
.venv/bin/python scripts/validate_schemas.py
```

## What counts as a test

There is no test suite. There are gates, and they stop the build.

**`fidelity_check.py`** re-reads the workbooks without using the extractor's logic and compares
counts and names. Its column positions are written out rather than resolved by heading, which is
deliberate: a check that shares the extractor's assumptions cannot disagree with it.

**`validate_vocab.py`** runs eight gates over the graph: every term labelled, with a status and a
module; every property with a domain and a range; every reference resolving; every term citing its
source; no class declared twice; every class the library has ever carried present, and nothing
invented. It earned its place by catching three properties whose range pointed at classes that had
not been emitted.

**`validate_schemas.py`** checks each schema is valid draft 2020-12 and that each still rejects an
instance carrying a field the model does not have. A schema that accepts everything is worse than
none, because it looks like a control.

**The namespace gate** in `build_all.sh` fails if `ontology/`, `schemas/`, `views/` or `mappings/`
contains `localhost` or `trade-commons.org`.

**`build_site.py`** fails if any directory holding an `index.html` does not also hold `index.ttl`,
`index.jsonld` and `index.rdf`. That invariant is what lets the edge function be one rule.

After a change that touches pages, follow the links: a short script that walks `dist/` and checks
every internal `href` resolves is worth more than reading the HTML.

## How the vocabulary is built

**It is unversioned, and its terms carry a lifecycle.** The vocabulary is built from all four
releases at once. Each term carries `wco:introducedIn`, `wco:presentIn`, and where it has gone
`wco:deprecatedIn` with `owl:deprecated`. A term is never deleted: 72 attribute positions and 3
code lists are published deprecated, because an identifier that stops resolving breaks every
document that used it. Messages are versioned instead, because a format has to be pinned.

**Identity across releases is the WCO identifier, not the name.** Attribute 429 is Traveller status
code in 4.1.0 and Traveler status code in 4.2.0. By name that is a removal and an addition; by
identifier it is the rename it was, and the earlier name becomes an alternate label. Class 17C is
spelt both AuthorisationHolder and AuthorizationHolder in the same workbook, in all four releases,
and merges the same way.

**Properties are shared, except where their values disagree.** WCO names an attribute inside its
class, so `id` occurs 174 times. Attributes sharing a local name and a core data type become one
property with many `schema:domainIncludes`, each class-specific definition kept as a scope note.
Where that merge produces a property whose classes code against different lists, it is undone;
`WCO_SPLIT` chooses how (`domain`, the default, `class`, or `none`). Where a split is forced by an
older release, the part the current release uses keeps the published name, so history does not move
an address.

**The superclass block is published.** The Library names a superclass per class (SC4 Party, SC3
Location, SC2 GovernmentAgency, SC1 RootDocument, SC5 TransportMeans) and a superclass element per
attribute. Those five are minted as classes, 170 classes declare `rdfs:subClassOf`, and each
property records the element it realises. Nothing is merged on that basis, so no term's address
depends on it.

**Columns are resolved by heading, never by position.** The four releases disagree: 4.0.0 says
XPath where the others say UML Model Path, 4.2.0 says Attribute UPI, 4.3.0 inserts a JSON Tag Name
column that shifts everything after it. `scripts/_sheet.py` does the resolution, qualifying by the
group label above a column where a heading repeats.

## Adding a WCO release

Put the workbooks in `raw-data/v<version>/` and run `scripts/build_all.sh`. Nothing else. The
workbooks are found by what they are rather than by their names, which differ between releases.

Then read the diff. `ontology/` shows what changed in the model, and `/releases/<version>/changes/`
is the change log the build computes. Check the new release's page before publishing: a release
that renames things will show them as renames only if the identifiers held.

## Editorial content, and marking it

`docs/derived-packages.json` names and explains every message. Where a gloss is ours rather than
WCO's, `source` is `editorial` and the site marks it visibly. Where a message's column heading
changed between releases and the two are joined as one message, `aliases` and `alias_note` record
the join and the page says it is our judgement.

Keep that discipline. The site states plainly which statements are WCO's and which are ours, and a
gloss that quietly loses its mark is worse than no gloss.

## Mappings to the UN/CEFACT vocabulary

`mappings/wco-to-unece.csv` is the ledger. A reviewer edits the decision column, sets `decided_by`
to `human`, and reruns `map_to_unece.py`; `ontology/mappings.ttl` is regenerated from the accepted
rows. The script's own guesses never survive as though a person had made them, which is what lets
the thresholds be changed.

The mapping asserts the identifier UN/CEFACT intends to publish under, `https://vocab.unece.org/…`.
Those addresses do not resolve yet, so the HTML links go to `https://test.uncefact.org/vocabulary/`
where that vocabulary answers today. `UNECE_RESOLVES` in `build_site.py` is the one line to change
when the production deployment lands.

`UNECE_ONTOLOGY` points at a local checkout of the vocab-bsp repository; the default is the path on
this machine.

## Publishing

To AWS, from GitHub Actions. `deploy/github-actions.yml` is written and has never been run; the
account does not exist yet.

The shape: a private S3 bucket, a CloudFront distribution with Origin Access Control, and a
viewer-request function that appends `/index.html`, `/index.ttl`, `/index.jsonld` or `/index.rdf`
according to `Accept`. Nothing runs at request time but that function. The workflow builds on push
to `main`, assumes a deploy role through OpenID Connect so no access key is stored anywhere,
uploads what changed, and invalidates the distribution.

Three things that are easy to get wrong:

**The host is baked in.** The pages carry absolute IRIs, so a build at the wrong `WCO_BASE` is
wrong everywhere. The workflow greps for the expected host in a built file and fails if it is not
there.

**A version is a path segment, not a file extension.** A release is published at
`/packages/<package>/<message>/4.3.0/`, which ends in a dot and a digit. The edge function requires
a file extension to begin with a letter. CloudFront does not redirect a directory to its trailing
slash the way a local static server does, so getting this wrong is a 404 in production and a
working page in every local test.

**`formats` must match what the generator emits.** The router negotiates only the representations a
site declares. This one emits Turtle, JSON-LD and RDF/XML.

The router, the response-header function and the infrastructure are shared with the UN/CEFACT
standards sites and live in the UN working repository at
`governance/technical-architecture/aws-test/cdk/`. `deploy/README.md` has the site's configuration
line and the verification commands.

## Writing

The prose rules in `~/.claude/CLAUDE.md` apply to everything here: the narrative pages, the
generated page text, the commit messages and the chat. Australian English, formal register, no
contractions, em dashes used occasionally rather than as a default, straight quotes, and no
promotional adjectives. The UN/CEFACT submission rules do not apply: this is a WCO publication, not
a UN/CEFACT instrument.

Page text is prose, not labels. The generator writes sentences that explain why a thing is as it
is, because the reader of a generated page has no other way to find out.

## Things that have gone wrong before

**A build with `WCO_BASE` set wrote localhost into the committed schemas.** The ontology was
already protected; the schemas were not. Both now always carry the canonical namespace and the
namespace gate checks it.

**A rename read as a deletion plus an addition** until identity moved to the WCO identifier.

**A diagram stopped rendering** when the page started linking at a versioned address while the file
was still written to the unversioned directory. If an image is missing, check the directory the
file is written to against the URL the page builds.

**A code list borrowed the name of a property that ranged at it**, which is how an externally
referenced list gets a name at all, and matched "user code list" to seal-condition-code-list. A
list that more than two properties range at no longer borrows a name.

**PlantUML was invoked once per diagram**, which was four minutes of JVM starts. One invocation
with every file takes ten seconds.
