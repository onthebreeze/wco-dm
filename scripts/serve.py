#!/usr/bin/env python3
"""Serve dist/ the way the edge will, so negotiation can be checked before anything is deployed.

The rule is the one in the CloudFront viewer-request function, restated rather than shared because
that function is JavaScript running at the edge: collapse a trailing slash, pass through anything
whose last segment ends in a file extension, and otherwise append /index.<ext> chosen by Accept.
If this server and that function ever disagree, this one is wrong.

An extension has to begin with a letter. A version is a path segment too - /packages/declarations/
4.3.0/ ends in ".0" - and the edge does not redirect a directory to its trailing slash the way a
local static server does, so treating that as a file would 404 there while working here.

    python3 scripts/serve.py 8099
    curl -H "Accept: text/turtle" http://localhost:8099/Consignment
"""
import functools
import http.server
import re
import pathlib
import socketserver
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent / "dist"
TYPES = {
    ".ttl": "text/turtle; charset=utf-8",
    ".jsonld": "application/ld+json",
    ".rdf": "application/rdf+xml",
    ".json": "application/json",
    # An XML schema is XML. Without this the fallback is application/octet-stream, which a browser
    # downloads instead of showing, and the uploader has the same table for the same reason.
    ".xsd": "application/xml; charset=utf-8",
}


def representation(accept):
    if "text/turtle" in accept:
        return "ttl"
    if "application/ld+json" in accept:
        return "jsonld"
    if "application/rdf+xml" in accept:
        return "rdf"
    if "application/json" in accept:
        return "jsonld"
    return "html"


class Handler(http.server.SimpleHTTPRequestHandler):
    def send_head(self):
        accept = self.headers.get("Accept", "")
        path = self.path.split("?", 1)[0].split("#", 1)[0]
        if len(path) > 1 and path.endswith("/"):
            path = path[:-1]
        last = path.rsplit("/", 1)[-1]
        if not re.search(r"\.[A-Za-z][A-Za-z0-9_]*$", last):
            path = f"{path}/index.{representation(accept)}"
        self.path = path
        return super().send_head()

    def guess_type(self, path):
        return TYPES.get(pathlib.Path(path).suffix, super().guess_type(path))

    def log_message(self, fmt, *args):
        if "--quiet" not in sys.argv:
            super().log_message(fmt, *args)


def main():
    port = int(next((a for a in sys.argv[1:] if a.isdigit()), 8099))
    handler = functools.partial(Handler, directory=str(ROOT))
    # Set before the socket is bound, not after: assigning it to the instance has no effect, and
    # a restart within the previous socket's TIME_WAIT then fails with "address already in use".
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    with socketserver.ThreadingTCPServer(("", port), handler) as httpd:
        print(f"serving {ROOT} on http://localhost:{port}")
        httpd.serve_forever()


if __name__ == "__main__":
    sys.exit(main())
