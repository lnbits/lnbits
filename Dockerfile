FROM acaratti/pypoet:3.9
COPY . .
RUN poetry install --no-dev --no-root
WORKDIR /app
COPY lnbits /app/lnbits
EXPOSE 5000
CMD ["poetry", "run", "lnbits", "--port", "5000", "--host", "0.0.0.0"]
