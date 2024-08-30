FROM python:3.10-slim-bookworm AS builder

RUN apt-get clean
RUN apt-get update
RUN apt-get install -y curl pkg-config build-essential libnss-myhostname npm

RUN npm install -g n
RUN n 16

RUN curl -sSL https://install.python-poetry.org | python3 -
ENV PATH="/root/.local/bin:$PATH"

WORKDIR /app

# Only copy the files required to install the dependencies
COPY Makefile package.json package-lock.json pyproject.toml poetry.lock ./


ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    POETRY_VIRTUALENVS_CREATE=1 \
    POETRY_CACHE_DIR=/tmp/poetry_cache

# bundle files
RUN mkdir -p lnbits/static/css lnbits/static/vendor
COPY lnbits/static/scss/ ./lnbits/static/scss/
COPY lnbits/static/js/ ./lnbits/static/js/
COPY lnbits/static/i18n/ ./lnbits/static/i18n/

RUN make build

FROM python:3.10-slim-bookworm

# needed for backups postgresql-client version 14 (pg_dump)
RUN apt-get update && apt-get -y upgrade && \
    apt-get -y install gnupg2 curl lsb-release libnss-myhostname && \
    sh -c 'echo "deb http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list' && \
    curl -s https://www.postgresql.org/media/keys/ACCC4CF8.asc | apt-key add - && \
    apt-get update && \
    apt-get -y install postgresql-client-14 postgresql-client-common && \
    apt-get clean all && rm -rf /var/lib/apt/lists/*

RUN curl -sSL https://install.python-poetry.org | python3 -
ENV PATH="/root/.local/bin:$PATH"

ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    POETRY_VIRTUALENVS_CREATE=1 \
    VIRTUAL_ENV=/app/.venv \
    PATH="/app/.venv/bin:$PATH"

COPY . /app
WORKDIR /app

COPY . .
COPY --from=builder /app/.venv .venv
COPY --from=builder /app/lnbits/static/bundle.min.js lnbits/static
COPY --from=builder /app/lnbits/static/bundle.min.css lnbits/static

RUN mkdir data

ENV LNBITS_PORT="5000"
ENV LNBITS_HOST="0.0.0.0"

EXPOSE 5000

CMD ["sh", "-c", "poetry run lnbits --port $LNBITS_PORT --host $LNBITS_HOST"]
