#!/usr/bin/env bash
#
# The scan policy from docs/hosting-the-calculator.md §11, in one place.
#
#   bash service/scan.sh <image-tag>
#
# The policy, and it is a policy rather than a flag:
#
#   Fixable HIGH and CRITICAL block.  Unfixable HIGH and CRITICAL are printed
#   and do not.  Everything below HIGH is printed and does not.
#
# The line is actionability, not severity. A CRITICAL with a patched version in
# the base image is something a merge can fix, and blocking is what makes it get
# fixed. A CRITICAL with no upstream fix is not something a merge can fix, and a
# gate that blocks on it is one people learn to route around — at which point it
# stops catching the fixable ones too. The failure mode of a too-strict scanner
# is not a slower pipeline, it is a disabled scanner.
#
# Both passes run, and the second one is why this is a policy and not just
# `--ignore-unfixed`. That flag on its own is a silent cap, which is the thing
# this repository has shipped three times and now writes rules about: a scan
# that quietly drops half its findings reads as a clean scan. So the unfiltered
# findings are printed on every run, and the build says what it chose not to
# block on.
#
# What this does NOT cover, said here so a green scan is not read as a claim
# about the whole product: it scans the image, and the image is python:3.12-slim
# plus PyJWT. It says nothing about agent/tools/, which is stdlib-only Python
# this repository wrote, and nothing about the Forge app's @forge/* packages,
# which CI audits separately.
#
# Trivy rather than `docker scout`: it runs with no account, no login and no
# vendor-side rate limit, which matters for a weekly scheduled job that must not
# fail for reasons unrelated to the image.

set -euo pipefail

IMAGE="${1:?usage: service/scan.sh <image-tag>}"

# Prefer a local trivy; otherwise run the official image. Both reach the local
# daemon, so the tag being scanned is the one that was just built rather than
# whatever a registry happens to hold under that name.
if command -v trivy >/dev/null 2>&1; then
  trivy_run() { trivy "$@"; }
else
  trivy_run() {
    docker run --rm \
      -v /var/run/docker.sock:/var/run/docker.sock \
      -v "${TRIVY_CACHE_DIR:-$HOME/.cache/trivy}:/root/.cache/trivy" \
      aquasec/trivy:latest "$@"
  }
fi

echo "── everything HIGH and CRITICAL, fixable or not ──────────────────────"
echo "   Printed in full. Anything here with no fix available does not block,"
echo "   and is listed so that decision is visible rather than silent."
trivy_run image --severity HIGH,CRITICAL --exit-code 0 --scanners vuln "$IMAGE"

echo
echo "── the gate: fixable HIGH and CRITICAL ───────────────────────────────"
if trivy_run image --severity HIGH,CRITICAL --ignore-unfixed --exit-code 1 \
     --scanners vuln "$IMAGE"; then
  echo "no fixable HIGH or CRITICAL findings — the gate passes"
else
  echo "::error::a fixable HIGH or CRITICAL vulnerability is present."
  echo "::error::The base is python:3.12-slim and the service installs one wheel,"
  echo "::error::so the fix is almost always a rebuild against a newer base."
  exit 1
fi
