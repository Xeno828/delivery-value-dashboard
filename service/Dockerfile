# The calculator. The tools it wraps are stdlib-only; the service itself has
# exactly one dependency, and only in SERVICE_AUTH=forge-token — PyJWT with its
# crypto extra, for verifying the Atlassian-issued invocation token. In
# shared-secret mode nothing here is imported.
FROM python:3.12-slim

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
