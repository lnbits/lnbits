![TESTS](https://github.com/lnbits/legend-regtest-enviroment/actions/workflows/ci.yml/badge.svg)

# nodes

- lnd-1: for locally testing your current lnbits
- lnd-2: used for boltz backend
- lnd-3: used for LND funding-source tests and backing lnbits-lnd inside docker
- cln-1: for locally testing your current lnbits and backing lnbits inside docker
- cln-2: used for clightning-REST
- cln-3: receives BOLT12 offer payments
- eclair-1: for locally testing your current lnbits

# Installing regtest

get the regtest enviroment ready

```sh
# Install docker https://docs.docker.com/engine/install/
# Make sure your user has permission to use docker 'sudo usermod -aG docker ${USER}' then reboot
# Stop/start docker 'sudo systemctl stop docker' 'sudo systemctl start docker'

sudo apt install jq
git clone https://github.com/lnbits/lnbits.git
cd lnbits
docker build -t lnbits/lnbits .
mkdir docker
git clone https://github.com/lnbits/legend-regtest-enviroment.git docker
cd docker
chmod +x ./start-regtest
./start-regtest # start the regtest and also run tests
sudo chown -R $USER ./data # Give the data file permissions for user
```

# Running LNbits on regtest

add this ENV variables to your `.env` file

```sh
DEBUG=true

# LND
LNBITS_BACKEND_WALLET_CLASS="LndRestWallet"
LND_REST_ENDPOINT=https://127.0.0.1:8081/
LND_REST_CERT=/home/user/repos/lnbits/docker/data/lnd-1/tls.cert
LND_REST_MACAROON=/home/user/repos/lnbits/docker/data/lnd-1/data/chain/bitcoin/regtest/admin.macaroon

# CLN
LNBITS_BACKEND_WALLET_CLASS="CoreLightningWallet"
CORELIGHTNING_RPC=./docker/data/clightning-1/regtest/lightning-rpc


# Run LNbits
uv run lnbits

# Run LNbits with hot reload
make dev
```

# testing

## Optional NWC funding source

NWC uses a separate Compose project with its own provider database and Nostr
relay. The provider connects to the existing CLN node 1. The normal regtest
services and funding sources do not change.

After building the LNbits image and starting the normal stack, run from the
repository root:

```sh
bash docker/regtest/start-nwc
source docker/regtest/data/nwc.env
make test-regtest
```

Each setup resets only the add-on's provider and relay data. Run it again before
repeating the NWC suite. It pins NWC Provider v1.2.2, gives its test
wallet a regtest balance, and writes the local pairing URL to the ignored
`data/nwc.env` file.
Its HTTP API and relay listen on localhost ports 5003 and 7777. These test
credentials must not be used outside regtest.

Stop only the NWC services and remove their test databases with:

```sh
docker compose -p lnbits-nwc -f docker/regtest/docker-compose.nwc.yml down --volumes
```

Stop this add-on before resetting or stopping the normal stack. CI starts it
only for the `NWCWallet` entry in the funding-source matrix and removes it
afterward. NWC follows the same failure policy as the other funding sources.

## Existing funding sources

BOLT12 offer tests run with `CoreLightningWallet`, `EclairWallet`, and
`LNbitsWallet`. The remote LNbits container uses CLN, and CLN node 3 issues the
offers. Eclair 0.11.0 requires Bitcoin Core 27.2 or later; this stack uses 28.1.
The CLN node 3–Eclair channel lets Eclair route BOLT12 invoice requests.

After starting the stack and configuring the funding source, run from the
repository root:

```sh
PYTEST_ADDOPTS="-k test_pay_real_offer" make test-regtest
```

```sh
chmod +x ./start-regtest
./start-regtest
# short answer :)
./start-regtest && echo "PASSED" || echo "FAILED" > /dev/null
```

usage of the `bitcoin-cli-sim`, `lightning-cli-sim` and `lncli-sim` aliases

```sh
cd ~/lnbits/docker
source docker-scripts.sh
# use bitcoin core, mine a block
bitcoin-cli-sim -generate 1

# use c-lightning nodes
lightning-cli-sim 1 newaddr | jq -r '.bech32' # use node 1
lightning-cli-sim 2 getinfo # use node 2
lightning-cli-sim 3 getinfo # use node 3

# use lnd nodes
lncli-sim 1 newaddr p2wsh
lncli-sim 2 listpeers
```

# urls

- mempool: http://localhost:8080/
- boltz api: http://localhost:9001/
- lnd-1 rest: http://localhost:8081/
- lnbits: http://localhost:5001/

# debugging docker logs

```sh
docker logs lnbits-lnbits-1 -f
docker logs lnbits-boltz-1 -f
docker logs lnbits-clightning-1-1 -f
docker logs lnbits-lnd-2-1 -f
```
