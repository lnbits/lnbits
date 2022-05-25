# Build image
FROM postgres:latest as builder

RUN apt-get update
RUN apt-get install -y python3 python3-venv
# Setup virtualenv
ENV VIRTUAL_ENV /opt/venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Install build deps
RUN apt-get update
RUN apt-get install -y --no-install-recommends build-essential pkg-config python3
RUN python3 -m pip install --upgrade pip
RUN pip install wheel

# Install runtime deps
COPY requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt

# Install c-lightning specific deps
RUN pip install pylightning

# Install LND specific deps
RUN pip install lndgrpc

# Production image
# FROM postgres:latest as lnbits

# Run as non-root
USER 1000:1000

# Copy over virtualenv
ENV VIRTUAL_ENV /opt/venv
# COPY --from=builder --chown=1000:1000 $VIRTUAL_ENV /opt/venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Copy in app source
WORKDIR /app

RUN mkdir -p /app/lnbits/data

COPY --chown=1000:1000 . /app/lnbits

ENV LNBITS_PORT="5000"
ENV LNBITS_HOST="0.0.0.0"

EXPOSE 5000

CMD ["sh", "-c", "uvicorn --app-dir lnbits --port $LNBITS_PORT --host $LNBITS_HOST"]
