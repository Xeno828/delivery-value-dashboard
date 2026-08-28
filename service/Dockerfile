# The calculator. The tools it wraps are stdlib-only; the service itself has
# exactly one dependency, and only in SERVICE_AUTH=forge-token — PyJWT with its
# crypto extra, for verifying the Atlassian-issued invocation token. In
# shared-secret mode nothing here is imported.
#
# "The base plus one wheel" is still the shape, with one qualification the line
# below adds: the base's own packages are upgraded to Debian's current security
# versions rather than left at whatever the base image was built with.
FROM python:3.12-slim

# Debian's security updates, applied at build time.
#
# Not belt-and-braces, and not a substitute for a current base. It exists
# because there is a lag between Debian publishing a patched package and the
# `python` image being rebuilt to include it, and deploys stop for the whole of
# that lag: `service/scan.sh` blocks on HIGH and CRITICAL findings that have a
# fix available, which is exactly what one of these is.
#
# That happened on 2026-08-28 and is what this line is for. CVE-2026-14456 in
# OpenSSL was fixed in 3.5.7-1~deb13u2 and published to trixie-security;
# python:3.12-slim still shipped 3.5.6-1~deb13u2, so every build produced an
# image with three fixable HIGH findings and the gate refused it — correctly.
# There was no newer base digest to pin to, and no other base helped: alpine
# failed the same gate on the same CVE, and distroless/python3-debian12 was far
# worse at 46 HIGH/CRITICAL. No base had rebuilt for it yet, so nothing but
# upgrading in the build could clear it. Measured: 3 fixable findings before,
# 0 after, +3.8 MB. ADR 0016.
#
# `upgrade` and not `dist-upgrade`: this takes patched versions of what is
# already here and must never add or remove a package. The lists are deleted in
# the same layer, or they are in the image for no reason.
RUN apt-get update \
 && apt-get upgrade -y \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
# Installed before the source is copied, so a change to app.py does not
# reinstall the wheel on every build.
COPY service/requirements.txt /app/service/requirements.txt
RUN pip install --no-cache-dir -r /app/service/requirements.txt

# Only what the calculation needs. No .env, no data/, no dist/, and nothing
# that could carry a credential into an image that gets pushed to a registry.
COPY agent/tools/ /app/agent/tools/
COPY service/app.py /app/service/app.py

# Nothing is written at runtime; the service is stateless by design, and a
# read-only root filesystem is one of the easier claims to make in a security
# review when it happens to be true.
RUN useradd --uid 10001 --no-create-home calc
USER 10001

ENV PORT=8080 HOST=0.0.0.0
EXPOSE 8080

# SERVICE_SHARED_SECRET must be injected by the platform. The service refuses
# to start without it, which is the behaviour you want from a misconfigured
# deploy — a calculator that came up unauthenticated would look healthy.
HEALTHCHECK --interval=30s --timeout=3s \
  CMD python3 -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/healthz',timeout=2).status==200 else 1)"

CMD ["python3", "service/app.py"]
