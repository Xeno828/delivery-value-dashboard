#!/usr/bin/env python3
"""
build.py — assemble src/ into a single distributable HTML file.

There is no bundler, no npm install and no transpile step. The build is a
string substitution, on purpose: the whole point of the deliverable is that it
is one file anyone can open, audit or email.

    python3 build.py                      # -> dist/delivery-value-dashboard.html
    python3 build.py --data data/x.json   # bake a different dataset in
    python3 build.py --check              # verify the build is reproducible
    python3 build.py --split DIR          # the same sources, NOT inlined
    python3 build.py --split DIR --bridge b.js   # ... plus a transport adapter

Two assemblies, one set of sources
----------------------------------
The default output is one file with everything inlined, which is the product.
`--split` writes the same four sources as separate linked assets, because a
Forge Custom UI iframe serves them under a Content-Security-Policy that blocks
inline <style> and inline <script> — silently. The page renders with the
browser's default stylesheet and none of its JavaScript runs, which looks like
a broken build rather than a blocked one.

This is deliberately not a second implementation of anything. Both modes read
the same src/ files; they differ only in whether the contents are substituted
into the placeholders or referenced from them.
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


#: The placeholder elements, and what each becomes when the assets are split
#: out. The whole element is replaced, not just the token, so no empty <style>
#: or <script> tag is left behind for the CSP to object to.
SPLIT_ELEMENTS = [
    (r"<style>\s*/\* @@STYLES@@ \*/\s*</style>",
     '<link rel="stylesheet" href="styles.css">', "styles.css", SRC / "styles.css"),
    (r"<script>\s*/\* @@APP@@ \*/\s*</script>",
     '<script src="app.js"></script>', "app.js", SRC / "app.js"),
    (r"<script>\s*/\* @@IMPORT@@ \*/\s*</script>",
     '<script src="import.js"></script>', "import.js", SRC / "import.js"),
]


def build_split(data_path: pathlib.Path, out_dir: pathlib.Path, bridge: str = None):
    """The same sources as separate files, for a host that forbids inline assets.

    The seed stays inline. It is `type="application/json"`, so it is data the
    page reads rather than script the browser executes — but if a CSP turns out
    to block it too, the symptom is a styled page with no numbers on it, and the
    fix is to fetch it rather than to inline it harder.
    """
    html = (SRC / "index.html").read_text(encoding="utf-8")
    written = []
    for pattern, replacement, name, source in SPLIT_ELEMENTS:
        html, n = re.subn(pattern, replacement, html, count=1)
        if n != 1:
            sys.exit("src/index.html no longer matches the %s placeholder element" % name)
        written.append((name, source.read_text(encoding="utf-8")))

    data = json.loads(data_path.read_text(encoding="utf-8"))
    html = html.replace("/* @@SEED@@ */", json.dumps(data, separators=(",", ":")))
    if "@@" in html:
        sys.exit("unsubstituted placeholders remain: %s"
                 % ", ".join(sorted(set(re.findall(r"@@\w+@@", html)))))

    # One extra linked script, ahead of the page's own.
    #
    # A host with no same-origin `api/` has to hand the page a transport, and
    # src/app.js looks for one on the window rather than importing anything —
    # it is the shipped product and stays dependency-free. The adapter must be
    # a classic script and must be linked *before* app.js, because app.js
    # decides at load whether it has a transport, and a script arriving
    # afterwards is a script arriving too late.
    #
    # Named rather than hard-coded: this file knows there is an adapter, not
    # what platform it adapts to.
    if bridge:
        tag = '<script src="app.js"></script>'
        if tag not in html:
            sys.exit("the split build cannot place %s — the app.js tag is not where "
                     "it was written" % bridge)
        html = html.replace(tag, '<script src="%s"></script>\n  %s' % (bridge, tag), 1)

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "index.html").write_text(html, encoding="utf-8")
    for name, body in written:
        (out_dir / name).write_text(body, encoding="utf-8")

    total = len(html) + sum(len(b) for _, b in written)
    print("Split build -> %s — %d files, %d KB, %d issues baked in%s"
          % (out_dir, len(written) + 1, total / 1024, len(data["issues"]),
             (", linking %s ahead of app.js" % bridge) if bridge else ""))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/sample-sprint.json",
                    help="dataset baked into the file as the default view")
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--check", action="store_true",
                    help="exit non-zero if dist/ is stale relative to src/")
    ap.add_argument("--split", metavar="DIR",
                    help="write the same sources as separate linked assets, for a "
                         "host whose CSP forbids inline style and script")
    ap.add_argument("--bridge", metavar="SRC",
                    help="split builds only: link this script immediately before "
                         "app.js, so a host can install a transport on the window "
                         "before the page looks for one")
    args = ap.parse_args()

    if args.split:
        build_split(ROOT / args.data, pathlib.Path(args.split), args.bridge)
        return
    if args.bridge:
        sys.exit("--bridge applies to --split only. The single-file build links "
                 "nothing; that is the property it exists to have.")

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
