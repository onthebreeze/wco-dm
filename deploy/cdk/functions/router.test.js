// Unit tests for the viewer-request router. CloudFront Functions are plain JS with no module
// system, so the source is read, its synth-time placeholders substituted exactly as the CDK
// construct does, and the result evaluated.
//
//   node functions/router.test.js
const fs = require('fs');
const path = require('path');
const assert = require('assert');

function load(negotiate, wholeGraph, excludeFromSearch = true, formats = ['ttl', 'jsonld']) {
  const src = fs
    .readFileSync(path.join(__dirname, 'router.js'), 'utf8')
    .split('__NEGOTIATE__').join(negotiate ? 'true' : 'false')
    .split('__FORMATS__').join(JSON.stringify(formats))
    .split('__EXCLUDE_FROM_SEARCH__').join(excludeFromSearch ? 'true' : 'false')
    .split('__WHOLE_GRAPH__').join(wholeGraph || '');
  return new Function(`${src}; return handler;`)();
}

const BROWSER =
  'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8';
const CURL = '*/*';

function req(uri, accept) {
  return { request: { uri, headers: accept ? { accept: { value: accept } } : {} } };
}

// The real vocab configuration: negotiated, with no whole-graph override, so the root serves its
// own index.ttl and index.jsonld as the generator emits them.
const vocab = load(true, '');
const docs = load(false, '');
// A hypothetical site that does set the override, so the 303 path stays covered.
const bigGraph = load(true, '/artefacts/big.ttl');
let passed = 0;

function uri(handler, path, accept) {
  const out = handler(req(path, accept));
  return out.statusCode ? `${out.statusCode} ${out.headers.location.value}` : out.uri;
}

function check(label, actual, expected) {
  assert.strictEqual(actual, expected, `${label}: expected ${expected}, got ${actual}`);
  passed++;
}

// --- a site with a content-negotiated tree -----------------------------------------------------
check('browser home', uri(vocab, '/', BROWSER), '/index.html');
check('curl home', uri(vocab, '/', CURL), '/index.html');
check('turtle at the root serves the dump', uri(vocab, '/', 'text/turtle'), '/index.ttl');
check('jsonld at the root serves the dump', uri(vocab, '/', 'application/ld+json'), '/index.jsonld');
check('the override 303s instead', uri(bigGraph, '/', 'text/turtle'), '303 /artefacts/big.ttl');
check('the override leaves browsers alone', uri(bigGraph, '/', BROWSER), '/index.html');
check('browser term', uri(vocab, '/Consignment', BROWSER), '/Consignment/index.html');
check('turtle term', uri(vocab, '/Consignment', 'text/turtle'), '/Consignment/index.ttl');
check('jsonld term', uri(vocab, '/Consignment', 'application/ld+json'), '/Consignment/index.jsonld');
check('bare json term', uri(vocab, '/Consignment', 'application/json'), '/Consignment/index.jsonld');
check('trailing slash', uri(vocab, '/Consignment/', 'text/turtle'), '/Consignment/index.ttl');
check('explicit representation passes through', uri(vocab, '/Consignment/index.ttl', BROWSER),
  '/Consignment/index.ttl');
check('path-style code', uri(vocab, '/currency-code-list/AUD', 'text/turtle'),
  '/currency-code-list/AUD/index.ttl');
check('documentation page', uri(vocab, '/docs/architecture', BROWSER), '/docs/architecture/index.html');
check('framework asset', uri(vocab, '/_next/static/chunks/app.js', BROWSER),
  '/_next/static/chunks/app.js');
check('root asset', uri(vocab, '/favicon.ico', BROWSER), '/favicon.ico');
check('diagram', uri(vocab, '/domain-map.svg', BROWSER), '/domain-map.svg');
check('search index', uri(vocab, '/search-index.json', BROWSER), '/search-index.json');
// A machine Accept on a documentation path asks for a representation that does not exist, and a
// 404 is the honest answer. Worth asserting so the behaviour is deliberate rather than noticed.
check('machine accept on a docs path', uri(vocab, '/docs/architecture', 'text/turtle'),
  '/docs/architecture/index.ttl');

// --- a site that publishes RDF/XML as well ------------------------------------------------------
// The WCO Data Model vocabulary emits index.rdf beside index.ttl and index.jsonld, and every page
// on it does, including the narrative and the message pages. Listing the format is what makes it
// negotiable; a site whose generator does not emit it must keep answering with the page.
const wcodm = load(true, '', true, ['ttl', 'jsonld', 'rdf']);
check('rdf/xml where it is published', uri(wcodm, '/Consignment', 'application/rdf+xml'),
  '/Consignment/index.rdf');
check('rdf/xml at the root', uri(wcodm, '/', 'application/rdf+xml'), '/index.rdf');
check('rdf/xml on a documentation page', uri(wcodm, '/docs/architecture', 'application/rdf+xml'),
  '/docs/architecture/index.rdf');
check('rdf/xml where it is not published', uri(vocab, '/Consignment', 'application/rdf+xml'),
  '/Consignment/index.html');
// The browser Accept carries application/xml at q=0.9. Matching the plain media type would hand
// every browser an RDF/XML document, so only application/rdf+xml counts.
check('a browser is never given rdf/xml', uri(wcodm, '/Consignment', BROWSER),
  '/Consignment/index.html');
check('turtle still wins when both are offered',
  uri(wcodm, '/Consignment', 'text/turtle, application/rdf+xml;q=0.9'), '/Consignment/index.ttl');

// A version is a path segment, not a file extension. The WCO message pages publish a release at
// /packages/<package>/<message>/<version>/, and "4.3.0" ends in a dot and a digit.
check('a version segment is a directory', uri(wcodm, '/packages/declarations/mar-api/4.3.0', BROWSER),
  '/packages/declarations/mar-api/4.3.0/index.html');
check('a version segment with a trailing slash', uri(wcodm, '/packages/declarations/4.3.0/', BROWSER),
  '/packages/declarations/4.3.0/index.html');
check('a version segment negotiates', uri(wcodm, '/packages/declarations/4.3.0', 'text/turtle'),
  '/packages/declarations/4.3.0/index.ttl');
check('a file inside a version segment is still a file',
  uri(wcodm, '/packages/declarations/4.3.0/schema.json', BROWSER),
  '/packages/declarations/4.3.0/schema.json');

// --- a documentation-only site -----------------------------------------------------------------
check('docs-only home', uri(docs, '/', BROWSER), '/index.html');
check('docs-only home ignores machine accept', uri(docs, '/', 'text/turtle'), '/index.html');
check('docs-only page', uri(docs, '/contact', BROWSER), '/contact/index.html');
check('docs-only forces html', uri(docs, '/contact', 'text/turtle'), '/contact/index.html');
check('docs-only asset', uri(docs, '/_astro/index.css', BROWSER), '/_astro/index.css');

// --- search-engine exclusion -------------------------------------------------------------------
function raw(handler, path, accept) {
  return handler(req(path, accept));
}
const robots = raw(vocab, '/robots.txt', BROWSER);
check('robots.txt is answered at the edge', robots.statusCode, 200);
check('robots.txt disallows everything', robots.body, 'User-agent: *\nDisallow: /\n');
check('robots.txt is plain text', robots.headers['content-type'].value, 'text/plain; charset=utf-8');
check('robots.txt on a docs-only site too', raw(docs, '/robots.txt', BROWSER).statusCode, 200);
// It must not be mistaken for a negotiable resource, whatever the client asks for.
check('robots.txt ignores a machine Accept', raw(vocab, '/robots.txt', 'text/turtle').statusCode, 200);

// An indexed deployment must not answer /robots.txt from the edge: it has to fall through to the
// site's own file or to a 404. The authoritative standards sites are indexed, and this application
// is the artefact a production deployment would start from, so the wrong default here would
// de-index them.
const indexed = load(true, '', false);
check('an indexed site does not answer robots.txt', uri(indexed, '/robots.txt', BROWSER),
  '/robots.txt');
check('an indexed site still negotiates', uri(indexed, '/Consignment', 'text/turtle'),
  '/Consignment/index.ttl');

// --- edge cases --------------------------------------------------------------------------------
check('no accept header at all', uri(vocab, '/Consignment', null), '/Consignment/index.html');
check('deep path', uri(vocab, '/module/transport', 'application/ld+json'),
  '/module/transport/index.jsonld');
check('case is preserved', uri(vocab, '/allowanceCharge', 'text/turtle'),
  '/allowanceCharge/index.ttl');
check('case is preserved, the other one', uri(vocab, '/AllowanceCharge', 'text/turtle'),
  '/AllowanceCharge/index.ttl');

console.log(`router: ${passed} assertions passed`);
