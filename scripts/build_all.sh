#!/usr/bin/env bash
# The whole site, in order, with the gates in between. One command, so a rebuild from a new WCO
# release is the same operation every time.
#
# Every stage runs over every release in raw-data/. The vocabulary is built from all of them at
# once, because it is unversioned and its terms carry their own lifecycle; the messages are built
# per release, because a message format has to be pinned.
#
#   scripts/build_all.sh                                   # the WCO namespace
#   WCO_BASE=https://test-wcodm.trade-commons.org/ scripts/build_all.sh
set -euo pipefail
cd "$(dirname "$0")/.."

echo "== extract =="            && python3 scripts/extract.py --all
echo "== fidelity =="           && python3 scripts/fidelity_check.py --all
echo "== vocabulary =="         && python3 scripts/build_vocabulary.py
echo "== validate =="           && python3 scripts/validate_vocab.py
echo "== mappings =="           && python3 scripts/map_to_unece.py
echo "== packages =="           && python3 scripts/extract_packages.py --all
echo "== schemas =="            && python3 scripts/build_schemas.py
echo "== message views =="      && python3 scripts/build_package_views.py
# The XML schemas WCO publishes, generated from the same source. scripts/compare_xsd.py checks
# them against WCO's own files; it needs those files downloaded, so it is not part of the build.
echo "== xml schemas =="        && python3 scripts/build_xsd.py
# The schema gate needs jsonschema, which the rest of the pipeline does not. It skips rather than
# fails when the library is absent, so a plain checkout still builds.
echo "== schema check =="       && python3 scripts/validate_schemas.py
# Nothing committed may carry a build-time hostname. The ontology, the schemas and the message
# views always hold the canonical namespace; WCO_BASE is a property of the published copy alone.
echo "== namespace gate =="
if grep -rlF -e 'localhost' -e 'trade-commons.org' ontology schemas views mappings >/dev/null 2>&1; then
  echo "a committed artefact carries a build-time hostname:" >&2
  grep -rlF -e 'localhost' -e 'trade-commons.org' ontology schemas views mappings >&2
  exit 1
fi

echo "== site =="               && python3 scripts/build_site.py

echo "== search index =="
# Pagefind runs over the finished tree, so the index covers the 900 term pages and not just the
# four narrative ones. It is a static index served from the same bucket: no search service.
npx --yes pagefind@^1.3.0 --site dist --output-subdir _pagefind

echo
echo "built $(find dist -name index.html | wc -l | tr -d ' ') pages into dist/"
