#!/usr/bin/env python3
"""Sync the built site to its S3 bucket.

Successor to vocab-bsp/deploy/cloudflare/upload-r2.py. Three differences matter.

One script, several sources. The documentation build and the content-negotiated tree merge into a
single prefix, so a stale object can only be identified against the union of both trees. Running
one `aws s3 sync --delete` per tree would make each pass delete the other's objects, which is why
the old pipeline needed four passes with include/exclude filters to scope the deletes. Sources are
applied in order and a later source wins a collision, so the documentation is passed last and wins,
reproducing the Cloudflare Worker's assets-first order.

The `~N` mangling is undone. The generator writes `allowanceCharge~1/` when two resources differ
only by case, because a build on a case-insensitive filesystem cannot hold `AllowanceCharge` and
`allowanceCharge` side by side, and records the mapping in `_manifest.json`. S3 keys are
case-sensitive, so the true key is written here and the edge needs no lookup table. The manifest
itself is not uploaded.

Credentials come from the environment, which in CI means the short-lived ones from the OpenID
Connect exchange. There is no access key anywhere in this pipeline.

    S3_BUCKET=unece-test-vocab python3 upload-s3.py dist out
"""
import concurrent.futures
import hashlib
import json
import os
import sys

import boto3
from botocore.config import Config

CT = {
    "html": "text/html; charset=utf-8",
    "ttl": "text/turtle; charset=utf-8",
    "jsonld": "application/ld+json",
    "rdf": "application/rdf+xml",
    "csv": "text/csv; charset=utf-8",
    "css": "text/css; charset=utf-8",
    "js": "application/javascript; charset=utf-8",
    "mjs": "application/javascript; charset=utf-8",
    "json": "application/json; charset=utf-8",
    "txt": "text/plain; charset=utf-8",
    "xml": "application/xml; charset=utf-8",
    "xsd": "application/xml; charset=utf-8",
    "svg": "image/svg+xml",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "gif": "image/gif",
    "webp": "image/webp",
    "avif": "image/avif",
    "ico": "image/x-icon",
    "woff": "font/woff",
    "woff2": "font/woff2",
    "ttf": "font/ttf",
    "pdf": "application/pdf",
    "zip": "application/zip",
    "map": "application/json; charset=utf-8",
}

BUCKET = os.environ.get("S3_BUCKET")
if not BUCKET:
    sys.exit("S3_BUCKET is not set")
SOURCES = sys.argv[1:]
if not SOURCES:
    sys.exit("usage: upload-s3.py <dir> [<dir> ...]   (later directories win collisions)")


def unmangle(root):
    """disk path -> published key, from the generator's _manifest.json if the tree has one."""
    path = os.path.join(root, "_manifest.json")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as handle:
        manifest = json.load(handle)
    return {disk: url for url, disk in manifest.items()}


# Collect the union of all sources, later sources overriding earlier ones on a collision.
local = {}
for root in SOURCES:
    if not os.path.isdir(root):
        sys.exit(f"{root} is not a directory")
    reverse = unmangle(root)
    collisions = 0
    for dirpath, _, filenames in os.walk(root):
        for filename in filenames:
            full = os.path.join(dirpath, filename)
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            if rel == "_manifest.json":
                continue
            directory, _, leaf = rel.rpartition("/")
            if directory in reverse:
                rel = reverse[directory] + "/" + leaf
            if rel in local:
                collisions += 1
            local[rel] = full
    print(f"{root}: {sum(1 for k, v in local.items() if v.startswith(root))} files"
          + (f", {collisions} overriding an earlier source" if collisions else ""))

s3 = boto3.client(
    "s3",
    config=Config(retries={"max_attempts": 6, "mode": "standard"}, max_pool_connections=48),
)

# Sync rather than re-upload: one listing pass gives every object's ETag and size, and for a
# single-part put the ETag is the body's hex MD5, so matching size and MD5 means unchanged. This is
# what turns a 32,000-file tree from a fifteen-minute upload into a few seconds after the first run.
remote = {}
for page in s3.get_paginator("list_objects_v2").paginate(Bucket=BUCKET):
    for obj in page.get("Contents", []):
        remote[obj["Key"]] = (obj["ETag"].strip('"'), obj["Size"])


def md5(path):
    digest = hashlib.md5()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


to_put, skipped = [], 0
for key, path in local.items():
    known = remote.get(key)
    if known and known[1] == os.path.getsize(path) and known[0] == md5(path):
        skipped += 1
    else:
        to_put.append((key, path))
stale = [key for key in remote if key not in local]


def put(item):
    key, path = item
    leaf = key.rsplit("/", 1)[-1]
    ext = leaf.rsplit(".", 1)[-1].lower() if "." in leaf else ""
    with open(path, "rb") as handle:
        s3.put_object(
            Bucket=BUCKET,
            Key=key,
            Body=handle.read(),
            ContentType=CT.get(ext, "application/octet-stream"),
            CacheControl="public, max-age=300",
        )


done, errors = 0, 0
with concurrent.futures.ThreadPoolExecutor(max_workers=32) as pool:
    futures = {pool.submit(put, item): item for item in to_put}
    for future in concurrent.futures.as_completed(futures):
        try:
            future.result()
            done += 1
        except Exception as error:  # noqa: BLE001 - report and keep going, fail at the end
            errors += 1
            print(f"  ERROR {futures[future][0]}: {error}", file=sys.stderr)
        if done and done % 3000 == 0:
            print(f"  {done}/{len(to_put)}", flush=True)

# Purge in batches of 1000, the delete_objects limit. Without this a deleted term would keep
# resolving forever.
for i in range(0, len(stale), 1000):
    s3.delete_objects(
        Bucket=BUCKET,
        Delete={"Objects": [{"Key": k} for k in stale[i:i + 1000]], "Quiet": True},
    )

print(f"synced to s3://{BUCKET}: uploaded {done}/{len(to_put)}, skipped {skipped} unchanged, "
      f"deleted {len(stale)} stale (errors: {errors})")
sys.exit(1 if errors else 0)
