# How this site is maintained

Everything published here is generated. Nothing in `ontology/` or `dist/` is edited by hand, and a
change to either is made by changing the generator and running it again.

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
python3 scripts/build_site.py       # 9. build the pages
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

## Deciding a mapping

`mappings/wco-to-unece.csv` is the ledger. Edit the decision column, set `decided_by` to `human`,
and run `scripts/map_to_unece.py` again. A human decision survives later runs; the script's own
guesses do not, so thresholds can be changed without losing review work.

## Two things to know before changing the generator

**Properties are shared, not duplicated.** WCO names a property inside its class, so `id` occurs 174
times. Attributes that share a name and a core data type become one property with many
`schema:domainIncludes`, which is how vocab.unece.org models the same ground. Each class-specific
definition survives as a scope note naming its class, so nothing is lost.

**Identifiers do not move.** The source carries a WCO-owned namespace and the build rewrites it for
whatever host is serving. Changing the base in the source would re-home every published term.
