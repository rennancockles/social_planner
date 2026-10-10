FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_SYSTEM_CERTS=1 \
    PATH="/app/.venv/bin:$PATH"

# On a managed/corporate network with TLS-inspecting proxies (e.g. Zscaler, Netskope),
# `uv sync` below fails with "invalid peer certificate: UnknownIssuer" because the
# container doesn't trust your org's intercepting CA. Fix: drop your CA bundle at
# certs/ca-bundle.crt (must end in .crt — e.g. on macOS:
# `security find-certificate -a -p /Library/Keychains/System.keychain > certs/ca-bundle.crt`)
# before building. This COPY/update-ca-certificates is a no-op when certs/ only has the
# .gitkeep placeholder, so it's always safe to run even without a corporate proxy.
COPY certs/ /usr/local/share/ca-certificates/
RUN update-ca-certificates

# Install deps first (separate layer from app code) so code-only changes don't
# invalidate the dependency-install cache.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

COPY app/ app/
COPY assets/ assets/

RUN uv sync --frozen --no-dev

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
