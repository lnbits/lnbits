#!/bin/sh
export COMPOSE_PROJECT_NAME=lnbits-legend

bitcoin-cli-sim(){
  docker exec lnbits-legend-bitcoind-1 bitcoin-cli -rpcuser=lnbits -rpcpassword=lnbits -regtest $@
}

# args(i, cmd)
lightning-cli-sim() {
  i=$1
  shift # shift first argument so we can use $@
  docker exec lnbits-legend-clightning-$i-1 lightning-cli --network regtest $@
}

# args(i, cmd)
lncli-sim() {
  i=$1
  shift # shift first argument so we can use $@
  docker exec lnbits-legend-lnd-$i-1 lncli --network regtest --rpcserver=lnd-$i:10009 $@
}

# args(i)
fund_clightning_node() {
  address=$(lightning-cli-sim $1 newaddr | jq -r .bech32)
  echo "funding: $address on clightning-node: $1"
  bitcoin-cli-sim -named sendtoaddress address=$address amount=10 fee_rate=100 > /dev/null
}

# args(i)
fund_lnd_node() {
  address=$(lncli-sim $1 newaddress p2wkh | jq -r .address)
  echo "funding: $address on lnd-node: $1"
  bitcoin-cli-sim -named sendtoaddress address=$address amount=10 fee_rate=100 > /dev/null
}

# args(i, j)
connect_clightning_node() {
  pubkey=$(lightning-cli-sim $2 getinfo | jq -r '.id')
  lightning-cli-sim $1 connect $pubkey@lnbits-legend-clightning-$2-1
}

lnbits-regtest-start(){
  lnbits-regtest-stop
  docker compose up -d --remove-orphans
}

lnbits-regtest-start-log(){
  lnbits-regtest-stop
  docker compose up --remove-orphans
}

lnbits-regtest-stop(){
  docker compose down --volumes
  # clean up lightning node data
  sudo rm -rf ./data/clightning-1 ./data/clightning-2 ./data/clightning-3 ./data/lnd-1 ./data/lnd-2 ./data/boltz/boltz.db
  # recreate lightning node data folders preventing permission errors
  mkdir ./data/clightning-1 ./data/clightning-2 ./data/clightning-3 ./data/lnd-1 ./data/lnd-2
}

lnbits-regtest-restart(){
  lnbits-regtest-stop
  lnbits-regtest-start
}

lnbits-regtest-init(){
  echo "init_bitcoin_wallet..."
  bitcoin-cli-sim createwallet lnbits || bitcoin-cli-sim loadwallet lnbits
  echo "mining 150 blocks..."
  bitcoin-cli-sim -generate 150 > /dev/null
  # create 10 UTXOs for each node
  for i in 0 1 2 3 4 5 6 7 8 9; do
    fund_clightning_node 1
    fund_clightning_node 2
    fund_clightning_node 3
    fund_lnd_node 1
    fund_lnd_node 2
  done
  echo "mining 5 blocks... and waiting 35s for the nodes to catch up"
  bitcoin-cli-sim -generate 5 > /dev/null
  sleep 35

  channel_size=16000000 # 0.016 btc
  balance_size_msat=7000000000 # 0.07 btc

  # open channels 1 -> 2, 2 -> 3, 3 -> 1
  connect_clightning_node 1 3
  lightning-cli-sim 1 fundchannel -k id=$(connect_clightning_node 1 2 | jq -r '.id') amount=$channel_size push_msat=$balance_size_msat
  connect_clightning_node 2 1
  lightning-cli-sim 2 fundchannel -k id=$(connect_clightning_node 2 3 | jq -r '.id') amount=$channel_size push_msat=$balance_size_msat
  connect_clightning_node 3 2
  lightning-cli-sim 3 fundchannel -k id=$(connect_clightning_node 3 1 | jq -r '.id') amount=$channel_size push_msat=$balance_size_msat

  # lnd node for boltz
  lncli-sim 1 connect $(lightning-cli-sim 1 getinfo | jq -r '.id')@lnbits-legend-clightning-1-1
  lncli-sim 1 openchannel $(lncli-sim 1 listpeers | jq -r '.peers[0].pub_key') $channel_size 8000000

  # lnd doesnt like more than 1 pending channel?
  echo "waiting 35s for lnd to catch up"
  bitcoin-cli-sim -generate 10 > /dev/null
  sleep 35

  # fund lnbits lnd channel
  lncli-sim 1 connect $(lncli-sim 2 getinfo | jq -r '.identity_pubkey')@lnbits-legend-lnd-2-1
  lncli-sim 1 openchannel $(lncli-sim 1 listpeers | jq -r '.peers[1].pub_key') $channel_size 8000000

  # lnd doesnt like more than 1 pending channel?
  echo "waiting 45s for lnd to catch up"
  bitcoin-cli-sim -generate 10 > /dev/null
  sleep 45


  # lnd node for lnbits
  lncli-sim 2 connect $(lightning-cli-sim 1 getinfo | jq -r '.id')@lnbits-legend-clightning-1-1
  lncli-sim 2 openchannel $(lncli-sim 2 listpeers | jq -r '.peers[0].pub_key') $channel_size 8000000

  # TODO: eclair nodes?

  # mine enough blocks for the channels to open
  echo "mining 10 blocks... to open the lightning channels"
  bitcoin-cli-sim -generate 10 > /dev/null
}

