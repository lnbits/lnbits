# temporary warning
boltz/backend is not in docker hub yet clone and build the image yourself
```console
git clone https://github.com/dni/boltz-backend
cd boltz-backend
git checkout dockerfile
docker build -t boltz/backend .
```
# usage
```console
source docker-scripts.sh

# start docker-compose with logs
lnbits-regtest-start-log
# start docker-compose in background
lnbits-regtest-start

# errors on startup are normal! wait at least 60 seconds
# for all services to come up before you start initializing
sleep 60

# initialize blockchain,
# fund lightning wallets
# connect peers
# create channels
# balance channels
lnbits-regtest-init

# use bitcoin core, mine a block
bitcoin-cli-sim -generate 1

# use c-lightning nodes
lightning-cli-sim 1 newaddr # use node 1
lightning-cli-sim 2 getinfo # use node 2
lightning-cli-sim 3 getinfo | jq -r '.bech32' # use node 3

# use lnd nodes
lncli-sim 1 newaddr p2wsh
lncli-sim 2 listpeers
```

# lnbits debug log
```console
docker logs lnbits-legend-lnbits-1 -f
```
