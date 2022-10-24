FROM python:3.9-slim

RUN apt-get clean
RUN apt-get update
RUN apt-get install -y curl pkg-config build-essential
RUN curl -sSL https://install.python-poetry.org | python3 -

ENV PATH="/root/.local/bin:$PATH"

WORKDIR /app

COPY . .

RUN poetry config virtualenvs.create false
RUN poetry install --no-dev --no-root
RUN poetry run python build.py

ENV LNBITS_PORT="5000"
ENV LNBITS_HOST="0.0.0.0"

EXPOSE 5000

CMD ["sh", "-c", "poetry run lnbits --port $LNBITS_PORT --host $LNBITS_HOST"]
