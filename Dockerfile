FROM python:3.9-slim
RUN apt-get update
RUN apt-get install -y curl
RUN curl -sSL https://install.python-poetry.org | python3 -
ENV PATH="/root/.local/bin:$PATH"
WORKDIR /app
COPY . .
RUN poetry config virtualenvs.create false
RUN poetry install --no-dev --no-root
RUN poetry run python build.py
EXPOSE 5000
CMD ["poetry", "run", "lnbits", "--port", "5000", "--host", "0.0.0.0"]
