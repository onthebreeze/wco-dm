// CloudFront viewer-response function: the two presentation rules that the current
// test.uncefact.org distribution already carries, ported unchanged in behaviour from
// vocab-bsp/deploy/cloudfront/jsonld-viewer-response.js.
//
// Static headers (X-Robots-Tag, Vary, CORS) are not set here. They are the same on every response,
// so they belong in a response headers policy, which costs nothing at request time.
function handler(event) {
  var request = event.request;
  var response = event.response;
  var headers = response.headers;
  var accept = request.headers['accept'] ? request.headers['accept'].value : '';
  var contentType = headers['content-type'] ? headers['content-type'].value : '';

  // The human-facing "JSON-LD" link is a browser navigation. Browsers render an
  // application/ld+json body in their JSON tree viewer, which hides the raw document the reader
  // asked to see, so downgrade it to text/plain for navigations only. A machine negotiating
  // application/ld+json is untouched, and machine negotiation must not change.
  if (contentType.indexOf('application/ld+json') === 0 && accept.indexOf('text/html') !== -1) {
    headers['content-type'] = { value: 'text/plain; charset=utf-8' };
  }

  // A right-click download should save Consignment.ttl, not index.ttl, while a left-click still
  // views inline.
  var match = /\/([^\/]+)\/index\.(ttl|jsonld|rdf|csv)$/.exec(request.uri);
  if (match) {
    headers['content-disposition'] = {
      value: 'inline; filename="' + match[1] + '.' + match[2] + '"',
    };
  }

  return response;
}
