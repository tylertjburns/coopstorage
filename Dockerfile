FROM python:3.12-slim

WORKDIR /app

# tk is required by cooptools even in headless/server mode
RUN apt-get update && apt-get install -y --no-install-recommends tk && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# coopmongo 0.4 has overly strict transitive pins; install it without deps so
# the rest of the stack can resolve freely, then install everything else.
RUN grep -v "pywin32" requirements.txt | grep -v "^coopmongo" | sed 's/==/>=/' > requirements-linux.txt && \
    pip install --no-cache-dir -r requirements-linux.txt && \
    pip install --no-cache-dir coopmongo --no-deps

COPY coopstorage/ ./coopstorage/

RUN useradd --create-home app
USER app

EXPOSE 1219

# Railway injects $PORT; 1219 is the local default. --factory calls create_app() for the instance.
# Proxy headers make the OAuth callback URL https behind Railway's TLS edge.
CMD uvicorn coopstorage.storage.api.server:create_app --factory --host 0.0.0.0 --port ${PORT:-1219} --proxy-headers --forwarded-allow-ips=*
