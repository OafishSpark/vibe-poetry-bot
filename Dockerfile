# ── Base ──────────────────────────────────────────────────────────────────────
FROM python:3.12-slim

# Keeps Python from buffering stdout/stderr (you see logs immediately)
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# ── System deps ───────────────────────────────────────────────────────────────
# curl is only needed at build time to fetch the certificate.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# ── Python dependencies ───────────────────────────────────────────────────────
# certifi must be installed before the certificate step below
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Russian trusted-root certificate ─────────────────────────────────────────
# Runs after pip install so that certifi (and its bundle path) is available.
# --retry: retry up to 5 times on transient network errors.
# --fail: treat HTTP error responses as errors (don't silently write HTML).
# --location: follow redirects.
# --silent / --show-error: quiet output but still print errors.
RUN CERT_URL="https://gu-st.ru/content/lending/russian_trusted_root_ca_pem.crt" \
    && CERT_BUNDLE=$(python -m certifi) \
    && curl --retry 5 --fail --location --silent --show-error \
         --insecure "$CERT_URL" >> "$CERT_BUNDLE" \
    && echo "Certificate appended to $CERT_BUNDLE"

# ── Application source ────────────────────────────────────────────────────────
COPY performance_artist.py weather.py ./

# ── Run ───────────────────────────────────────────────────────────────────────
CMD ["python", "performance_artist.py"]
