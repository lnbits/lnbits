FROM python:3.12-slim-bookworm AS builder

RUN apt-get clean
RUN apt-get update
RUN apt-get install -y curl pkg-config build-essential libnss-myhostname automake

RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

WORKDIR /app

# Only copy the files required to install the dependencies
COPY pyproject.toml uv.lock ./
RUN touch README.md

RUN mkdir data

RUN uv sync --all-extras

FROM python:3.12-slim-bookworm

# pg_dump is used by the admin backup endpoint. It must be at least as new as
# the PostgreSQL server being dumped, so track a current major rather than
# pinning an old one; a newer pg_dump still reads older servers.
RUN apt-get update && apt-get -y upgrade && \
    apt-get -y install gnupg2 curl lsb-release && \
    sh -c 'echo "deb http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list' && \
    curl -s https://www.postgresql.org/media/keys/ACCC4CF8.asc | apt-key add - && \
    apt-get update && \
    apt-get -y install postgresql-client-18 postgresql-client-common && \
    apt-get clean all && rm -rf /var/lib/apt/lists/*

RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

WORKDIR /app

COPY . .
COPY --from=builder /app/.venv .venv

RUN uv sync --all-extras

ENV LNBITS_PORT="5000"
ENV LNBITS_HOST="0.0.0.0"

EXPOSE 5000

CMD ["sh", "-c", "uv --offline run --no-sync lnbits --port $LNBITS_PORT --host $LNBITS_HOST --forwarded-allow-ips='*'"]
