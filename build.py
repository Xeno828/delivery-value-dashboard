#!/usr/bin/env python3
"""
build.py — assemble src/ into a single distributable HTML file.

There is no bundler, no npm install and no transpile step. The build is a
string substitution, on purpose: the whole point of the deliverable is that it
is one file anyone can open, audit or email.

    python3 build.py                      # -> dist/delivery-value-dashboard.html
    python3 build.py --data data/x.json   # bake a different dataset in
    python3 build.py --check              # verify the build is reproducible
"""

import argparse
import hashlib
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent
SRC = ROOT / "src"
DIST = ROOT / "dist"
OUT = DIST / "delivery-value-dashboard.html"

TOKENS = {
    "/* @@STYLES@@ */": SRC / "styles.css",
    "/* @@APP@@ */": SRC / "app.js",
    "/* @@IMPORT@@ */": SRC / "import.js",
}


def build(data_path: pathlib.Path) -> str:
    html = (SRC / "index.html").read_text(encoding="utf-8")

    for token, path in TOKENS.items():
        if token not in html:
            sys.exit("src/index.html is missing the %s placeholder" % token)
        body = path.read_text(encoding="utf-8")
        # A literal </script> inside JS would close the tag early.
        if path.suffix == ".js":
            body = body.replace("</script>", "<\\/script>")
        html = html.replace(token, body)

    data = json.loads(data_path.read_text(encoding="utf-8"))
    html = html.replace("/* @@SEED@@ */", json.dumps(data, separators=(",", ":")))

    if "@@" in html:
        leftover = set(re.findall(r"@@\w+@@", html))
        sys.exit("unsubstituted placeholders remain: %s" % ", ".join(sorted(leftover)))
    return html


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/sample-sprint.json",
                    help="dataset baked into the file as the default view")
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--check", action="store_true",
                    help="exit non-zero if dist/ is stale relative to src/")
    args = ap.parse_args()

    html = build(ROOT / args.data)
    out = pathlib.Path(args.out)

    if args.check:
        if not out.exists():
            sys.exit("dist/ has not been built — run: python3 build.py")
        current = out.read_text(encoding="utf-8")
        if hashlib.sha256(current.encode()).hexdigest() != hashlib.sha256(html.encode()).hexdigest():
            sys.exit("dist/ is stale — run: python3 build.py  (and commit the result)")
        print("dist/ is up to date (%d KB)" % (len(html) / 1024))
        return

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print("Built %s — %d KB, %d issues baked in"
          % (out, len(html) / 1024, len(json.loads((ROOT / args.data).read_text())["issues"])))


if __name__ == "__main__":
    main()
