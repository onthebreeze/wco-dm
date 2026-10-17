# Architecture

Three pieces: a source of record, a generator, and a tree of files served from object storage behind
a content delivery network. Nothing runs at request time except a small function at the edge.

## The pipeline

```
raw-data/*.xlsx          the WCO workbooks, unmodified
      |  extract.py
      v
intermediate/*.json      one record per class, attribute, data type, code list and occurrence,
      |                  each carrying its source file, sheet and row
      |  build_vocabulary.py
      v
ontology/*.ttl           the vocabulary: modules, classes, properties, code lists, lifecycle
      |  build_site.py
      v
dist/<Term>/index.{html,ttl,jsonld}    one directory per term
```

The narrative pages you are reading come out of the same generator, from Markdown in `docs/`, so the
whole site is one toolchain and one visual language.

## Why the pages are generated rather than routed

There are about 900 term pages today and a locations register of comparable scope would run to far
more. A framework that renders a route per term is slow for no benefit, and none of them emits the
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
