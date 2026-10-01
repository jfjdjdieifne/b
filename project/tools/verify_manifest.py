#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_manifest.py — MANIFEST.sha256 integrity checker (Windows + Linux).

Standard library only. Streaming hashing. Works from any current working
directory: pass --root (defaults to ../trading_project relative to this
script) and --manifest (defaults to <root>/MANIFEST.sha256).

Exit codes: 0 = all OK, 1 = at least one mismatch/missing, 2 = usage error.
"""

import argparse
import hashlib
import os
import re
import sys

LINE_RE = re.compile(r"^([0-9A-Fa-f]{64})\s+\*?(.+?)\s*$")


def sha256_of(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    here = os.path.dirname(os.path.abspath(__file__))
    default_root = os.path.join(here, "..", "trading_project")

    ap = argparse.ArgumentParser(description="Verify MANIFEST.sha256 entries.")
    ap.add_argument("--root", default=default_root,
                    help="directory the manifest paths are relative to")
    ap.add_argument("--manifest", default=None,
                    help="manifest file (default: <root>/MANIFEST.sha256)")
    ns = ap.parse_args()

    root = os.path.abspath(ns.root)
    manifest = ns.manifest or os.path.join(root, "MANIFEST.sha256")

    if not os.path.isfile(manifest):
        print("خطأ: ملف المانيفست غير موجود: %s" % manifest, file=sys.stderr)
        return 2

    ok = 0
    failed = []
    total = 0
    with open(manifest, "r", encoding="utf-8", errors="replace") as mf:
        for line in mf:
            line = line.strip()
            if not line:
                continue
            m = LINE_RE.match(line)
            if not m:
                failed.append(("BAD_LINE", line[:120]))
                total += 1
                continue
            expect, rel = m.group(1), m.group(2)
            total += 1
            fpath = os.path.join(root, rel)
            if not os.path.isfile(fpath):
                failed.append(("MISSING", rel))
                continue
            try:
                actual = sha256_of(fpath)
            except OSError as exc:
                failed.append(("UNREADABLE", "%s (%s)" % (rel, exc)))
                continue
            if actual.lower() == expect.lower():
                ok += 1
            else:
                failed.append(("MISMATCH", rel))

    print("MANIFEST: %s" % manifest)
    print("النتيجة: %d / %d OK" % (ok, total))
    if failed:
        print("فشلت المقارنة للملفات التالية:")
        for kind, rel in failed:
            print("  [%s] %s" % (kind, rel))
        return 1
    print("جميع الملفات مطابقة — سلامة المشروع مؤكدة.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # pragma: no cover
        print("خطأ غير متوقع: %s" % exc, file=sys.stderr)
        sys.exit(1)
