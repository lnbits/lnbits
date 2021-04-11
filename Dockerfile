# Build image
FROM python:3.7-slim as builder

# Setup virtualenv
ENV VIRTUAL_ENV=/opt/venv
RUN python -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Install build deps
RUN apt-get update
RUN apt-get install -y --no-install-recommends build-essential

# Install runtime deps
COPY requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt

# Install c-lightning specific deps
RUN pip install pylightning

# Install LND specific deps
RUN pip install lndgrpc purerpc

# Production image
FROM python:3.7-slim as lnbits

# Run as non-root
USER 1000:1000

# Copy over virtualenv
ENV VIRTUAL_ENV="/opt/venv"
COPY --from=builder --chown=1000:1000 $VIRTUAL_ENV $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Setup Quart
ENV QUART_APP="lnbits.app:create_app()"
ENV QUART_ENV="development"
ENV QUART_DEBUG="true"

# App
ENV LNBITS_BIND="0.0.0.0:5000"

# Copy in app source
WORKDIR /app
COPY --chown=1000:1000 lnbits /app/lnbits

EXPOSE 5000

CMD quart assets && quart migrate && hypercorn -k trio --bind $LNBITS_BIND 'lnbits.app:create_app()'
