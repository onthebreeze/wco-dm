// CloudFront viewer-request function: routing and content negotiation for a standards site.
//
// This is the AWS port of the Cloudflare Worker in vocab-bsp/deploy/cloudflare/worker.js, but it
// needs none of that Worker's machinery, for three reasons worth stating because each one was a
// constraint in the Cloudflare design:
//
//  1. No asset manifest. The Worker consulted _manifest.json to undo the `~1` mangling the
//     generator applies when two resources differ only by case (AllowanceCharge vs
//     allowanceCharge), which a build on a case-insensitive filesystem cannot hold side by side.
//     S3 keys are case-sensitive, so the uploader writes the true key and the edge needs no lookup
//     table. That also keeps this function inside the 10 KB limit for CloudFront Functions; a
//     manifest at the edge would have forced Lambda@Edge.
//  2. No existence check. The Worker tried the static asset first and fell through to the
//     vocabulary. A viewer-request function cannot read the origin, so routing must be
//     deterministic instead. It is: every site framework in use (Next.js with trailingSlash,
//     Astro with build.format directory, Docusaurus by default) emits directory-style
//     <path>/index.html, and the vocabulary generator emits <resource>/index.{html,ttl,jsonld,rdf}.
//     One rule therefore covers documentation and negotiated resources alike, so the two trees
//     merge into one S3 prefix and no reserved-prefix list has to be maintained.
//  3. No Accept-varying cache rule. This function runs before the cache lookup and rewrites the
//     URI to a concrete representation, so the cache key already distinguishes HTML from Turtle
//     from JSON-LD. Cloudflare ignores Vary by default, which is why that design needed a cache
//     rule the CI token was not permitted to create.
//
// NEGOTIATE, FORMATS and WHOLE_GRAPH are substituted at synth time from the site's configuration.
var NEGOTIATE = __NEGOTIATE__;
// The machine representations this site actually publishes. A format the generator does not emit
// must fall through to HTML rather than rewrite to a key that is not there: answering a request for
// RDF/XML with a 404 on a site that has no .rdf files would be worse than answering with the page.
var FORMATS = __FORMATS__;
var WHOLE_GRAPH = '__WHOLE_GRAPH__';
// False on an indexed (production) deployment, where /robots.txt must fall through to the site's
// own file, or to a 404, rather than being answered with a disallow-all body from the edge.
var EXCLUDE_FROM_SEARCH = __EXCLUDE_FROM_SEARCH__;

function has(format) {
  return FORMATS.indexOf(format) !== -1;
}

function representation(accept) {
  if (has('ttl') && accept.indexOf('text/turtle') !== -1) return 'ttl';
  if (has('ttl') && accept.indexOf('application/x-turtle') !== -1) return 'ttl';
  if (has('jsonld') && accept.indexOf('application/ld+json') !== -1) return 'jsonld';
  // application/rdf+xml only. A browser sends application/xml in its Accept and must never be
  // handed RDF/XML, so the plain media type is deliberately not matched.
  if (has('rdf') && accept.indexOf('application/rdf+xml') !== -1) return 'rdf';
  // A bare application/json is treated as a machine asking for JSON-LD, which is what the local
  // serve-vocab.py and the Worker both do. Browsers never send it, so this cannot catch a human.
  if (has('jsonld') && accept.indexOf('application/json') !== -1) return 'jsonld';
  return 'html';
}

function handler(event) {
  var request = event.request;
  var uri = request.uri;
  var accept = request.headers['accept'] ? request.headers['accept'].value : '';
  var wanted = NEGOTIATE ? representation(accept) : 'html';

  // Collapse a trailing slash so /Consignment/ and /Consignment behave identically.
  if (uri.length > 1 && uri.charAt(uri.length - 1) === '/') {
    uri = uri.substring(0, uri.length - 1);
  }

  // Keep the test sites out of search engines. These are public copies of UN content and must
  // never compete with the authoritative sites in results. The X-Robots-Tag header on every
  // response is what does that: noindex is the only directive that actually removes a page from
  // an index, and it is set on every representation, not just the HTML.
  //
  // Crawling is deliberately allowed. A disallow would not help and would hurt twice over: a
  // blocked URL can still be listed from inbound links, because the crawler indexes the address
  // without fetching it; and a crawler that never fetches the response never sees the noindex, so
  // the disallow undermines the directive that works. It would also block the machine clients this
  // vocabulary exists to serve, which is the opposite of the point of publishing it.
  //
  // Serving the file from the edge rather than the build means it cannot be forgotten in a
  // repository and cannot travel into a production deployment, because only the test distributions
  // run this function.
  if (EXCLUDE_FROM_SEARCH && uri === '/robots.txt') {
    return {
      statusCode: 200,
      statusDescription: 'OK',
      headers: {
        'content-type': { value: 'text/plain; charset=utf-8' },
        'cache-control': { value: 'public, max-age=3600' },
        'x-robots-tag': { value: 'noindex, nofollow' },
      },
      body:
        '# Test deployment of the WCO Data Model vocabulary.\n' +
        '#\n' +
        '# Kept out of search results by X-Robots-Tag: noindex, nofollow on every response,\n' +
        '# which is the directive that actually removes a page from an index.\n' +
        '#\n' +
        '# Crawling is deliberately allowed: machine clients need the vocabulary, and a crawler\n' +
        '# that cannot fetch a page never sees the noindex.\n' +
        'User-agent: *\n' +
        'Allow: /\n',
    };
  }

  if (uri === '' || uri === '/') {
    // The root is just another resource: the generator emits index.html, index.ttl and
    // index.jsonld there, the first being the documentation landing page and the other two the
    // whole-graph dumps. Serving them directly is what the Cloudflare Worker did, and for this
    // vocabulary the dumps are 2.6 MB and 4.2 MB, small enough not to need indirection.
    //
    // WHOLE_GRAPH overrides that with a 303 to a named dump, for a site whose graph is large
    // enough that the most-hit path should not serve it inline. It must name a path that exists.
    if (wanted !== 'html' && WHOLE_GRAPH !== '') {
      return {
        statusCode: 303,
        statusDescription: 'See Other',
        headers: { 'location': { value: WHOLE_GRAPH } },
      };
    }
    request.uri = '/index.' + wanted;
    return request;
  }

  // A last segment carrying a file extension is a real file: a framework asset (/_next/app.js), an
  // image, or an explicitly requested representation (/Consignment/index.ttl). Serve it as asked.
  //
  // The extension must begin with a letter. A dot alone is not enough, because a version is a path
  // segment too: /packages/declarations/4.3.0/ ends in ".0", and treating that as a file sends the
  // request to a key that does not exist. CloudFront does not redirect a directory to its trailing
  // slash the way a local static server does, so the page would simply 404. Every extension in use
  // - html, ttl, jsonld, rdf, json, js, css, svg, png, woff2, pf_meta - starts with a letter.
  var last = uri.substring(uri.lastIndexOf('/') + 1);
  if (/\.[A-Za-z][A-Za-z0-9_]*$/.test(last)) {
    request.uri = uri;
    return request;
  }

  // Extensionless: a documentation page or a negotiated resource. Both resolve the same way.
  request.uri = uri + '/index.' + wanted;
  return request;
}
