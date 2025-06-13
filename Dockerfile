FROM python:3.12-slim-bookworm AS builder

RUN apt-get clean
RUN apt-get update
RUN apt-get install -y curl pkg-config build-essential libnss-myhostname

RUN curl -sSL https://install.python-poetry.org | python3 - --version 1.8.5
ENV PATH="/root/.local/bin:$PATH"

WORKDIR /app

# Only copy the files required to install the dependencies
COPY pyproject.toml poetry.lock ./

RUN mkdir data

ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    POETRY_VIRTUALENVS_CREATE=1 \
    POETRY_CACHE_DIR=/tmp/poetry_cache

ARG POETRY_INSTALL_ARGS="--only main"
RUN poetry install ${POETRY_INSTALL_ARGS}

FROM python:3.12-slim-bookworm

# needed for backups postgresql-client version 14 (pg_dump)
RUN apt-get update && apt-get -y upgrade && \
    apt-get -y install gnupg2 curl lsb-release && \
    sh -c 'echo "deb http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list' && \
    curl -s https://www.postgresql.org/media/keys/ACCC4CF8.asc | apt-key add - && \
    apt-get update && \
    apt-get -y install postgresql-client-14 postgresql-client-common && \
    apt-get clean all && rm -rf /var/lib/apt/lists/*

RUN curl -sSL https://install.python-poetry.org | python3 - --version 1.8.5
ENV PATH="/root/.local/bin:$PATH"

ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    POETRY_VIRTUALENVS_CREATE=1 \
    VIRTUAL_ENV=/app/.venv \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

COPY . .
COPY --from=builder /app/.venv .venv

ARG POETRY_INSTALL_ARGS="--only main"
RUN poetry install ${POETRY_INSTALL_ARGS}

# === BEGIN: Add Boltz ===

WORKDIR /opt/boltz

# Use GitHub latest release API to get the latest amd64 release (manual for now)
# Example hardcoded URL for now -- you can make this dynamic if you want
# Example latest release at the time of writing:
# https://github.com/BoltzExchange/boltz-client/releases/download/v1.6.2/boltz-client-v1.6.2-linux-amd64.tar.gz

RUN apt-get update && apt-get install -y jq curl wget tar && \
    BOLTZ_URL=$(curl -s https://api.github.com/repos/BoltzExchange/boltz-client/releases/latest \
    | jq -r '.assets[] | select(.name | test(".*linux.*amd64.*\\.tar\\.gz$")) | .browser_download_url') && \
    echo "Downloading Boltz release: $BOLTZ_URL" && \
    wget "$BOLTZ_URL" -O boltz-release.tar.gz && \
    tar -xvzf boltz-release.tar.gz && \
    cd bin/linux_amd64 && \
    chmod +x boltzd boltzcli && \
    mv boltzd /usr/local/bin/ && \
    mv boltzcli /usr/local/bin/

WORKDIR /app

# === END: Add Boltz ===

ENV LNBITS_PORT="5000"
ENV LNBITS_HOST="0.0.0.0"
ENV LNBITS_BACKEND_WALLET_CLASS="BoltzWallet"
ENV BOLTZ_CLIENT_ENDPOINT="127.0.0.1:9002"
ENV BOLTZ_CLIENT_MACAROON="/root/.boltz/macaroons/admin.macaroon"
ENV BOLTZ_CLIENT_CERT="/root/.boltz/tls.cert"
ENV BOLTZ_CLIENT_WALLET="lnbits"

EXPOSE 5000

# Replace CMD with an entrypoint script
COPY dockerboltz.sh /dockerboltz.sh
RUN chmod +x /dockerboltz.sh

CMD ["/dockerboltz.sh"]
