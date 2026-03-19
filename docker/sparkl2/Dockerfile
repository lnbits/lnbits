ARG LNBITS_TAG=latest

FROM lnbits/lnbits:${LNBITS_TAG}

RUN apt-get update && apt-get -y upgrade
RUN apt-get install -y netcat-openbsd npm nodejs git

RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

# install sparksidecar
RUN git clone https://github.com/lnbits/spark_sidecar
RUN cd spark_sidecar && npm install

# Reinstall dependencies for lnbits just in case (needed for CMD usage)
RUN uv sync --all-extras

# LNBITS
ENV LNBITS_PORT="5000"
ENV LNBITS_HOST="0.0.0.0"
ENV LNBITS_BACKEND_WALLET_CLASS="SparkL2Wallet"
ENV LNBITS_RESERVE_FEE_MIN="20000"
ENV LNBITS_RESERVE_FEE_PERCENT="1"
ENV LNBITS_FUNDING_SOURCE_PAY_INVOICE_WAIT_SECONDS="20"
ENV FUNDING_SOURCE_MAX_RETRIES="10"

# spark sidecar
ENV SPARK_NETWORK="MAINNET"
ENV SPARK_SIDECAR_PORT="8765"
ENV SPARK_PAY_WAIT_MS="20000"
ENV SPARK_MULTIPLICITY="3"

EXPOSE 5000

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Entrypoint to start sparksidebar and LNbits
CMD ["/entrypoint.sh"]
