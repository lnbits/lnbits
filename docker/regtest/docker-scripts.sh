#!/bin/sh
export COMPOSE_PROJECT_NAME=lnbits

boltzcli-sim() {
  docker exec -it lnbits-boltz-client-1 boltzcli "$@"
}

bitcoin-cli-sim() {
  docker exec lnbits-bitcoind-1 bitcoin-cli -regtest "$@"
}

elements-cli-sim() {
  docker exec lnbits-elementsd-1 elements-cli -rpcport=18884 -chain=liquidregtest "$@"
}

# args(i, cmd)
lightning-cli-sim() {
  i=$1
  shift # shift first argument so we can use $@
  docker exec lnbits-clightning-$i-1 lightning-cli --network regtest "$@"
}

# args(i, cmd)
lncli-sim() {
  i=$1
  shift # shift first argument so we can use $@
  docker exec lnbits-lnd-$i-1 lncli --network regtest --rpcserver=lnd-$i:10009 "$@"
}

get-eclair-pubkey() {
  while true; do
    pubkey=$(docker exec lnbits-eclair-1 curl http://localhost:8080/getinfo -X POST -s -u :lnbits | jq -r .nodeId 2> /dev/null)
    pubkeyPrefix=$(echo $pubkey | cut -c1,2)
    if [[ "$pubkeyPrefix" == "02" || "$pubkeyPrefix" == "03" ]]; then
      echo $pubkey
      break
    fi
    sleep 1
  done
}

wait-for-eclair-channel() {
  while true; do
    state=$(docker exec lnbits-eclair-1 curl http://localhost:8080/channels -X POST -s -u :lnbits | jq -r ".[0].state")
    pending=$(docker exec lnbits-eclair-1 curl -s http://localhost:8080/channels -X POST -u :lnbits| jq '. | length')
    echo "eclair-1 pendingchannels: $pending, current state: $state"
    if [[ "$state" == "NORMAL" ]]; then
      break
    fi
    sleep 1
  done
}

# args(i)
fund_boltz_client() {
  # first address of seed: abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about
  address="el1qq2xvpcvfup5j8zscjq05u2wxxjcyewk7979f3mmz5l7uw5pqmx6xf5xy50hsn6vhkm5euwt72x878eq6zxx2z0z676mna6kdq"
  echo "funding: $address on boltz-client"
  elements-cli-sim -named sendtoaddress address=$address amount=30 fee_rate=100 > /dev/null
}


# args(i)
fund_clightning_node() {
  address=$(lightning-cli-sim $1 newaddr | jq -r .bech32)
  echo "funding: $address on clightning-node: $1"
  bitcoin-cli-sim -named sendtoaddress address=$address amount=30 fee_rate=100 > /dev/null
}

# args(i)
fund_lnd_node() {
  address=$(lncli-sim $1 newaddress p2wkh | jq -r .address)
  echo "funding: $address on lnd-node: $1"
  bitcoin-cli-sim -named sendtoaddress address=$address amount=30 fee_rate=100 > /dev/null
}

# args(i, j)
connect_clightning_node() {
  pubkey=$(lightning-cli-sim $2 getinfo | jq -r '.id')
  lightning-cli-sim $1 connect $pubkey@lnbits-clightning-$2-1:9735 | jq -r '.id'
}

lnbits-regtest-start(){
  if ! command -v jq &> /dev/null
  then
      echo "jq is not installed"
      exit
  fi
  if ! command -v docker &> /dev/null
  then
      echo "docker is not installed"
      exit
  fi
  if ! command -v docker version &> /dev/null
  then
      echo "dockerd is not running"
      exit
  fi
  lnbits-regtest-stop
  docker compose up -d --remove-orphans
  lnbits-regtest-init
}

lnbits-regtest-start-log(){
  lnbits-regtest-stop
  docker compose up --remove-orphans
  lnbits-regtest-init
}

lnbits-regtest-stop(){
  docker compose down --volumes
  # clean up lightning node data
  sudo rm -rf ./data/clightning-1 ./data/clightning-2 ./data/clightning-3 ./data/lnd-1  ./data/lnd-2 ./data/lnd-3 ./data/lnd-4 ./data/boltz/boltz.db ./data/eclair/regtest ./data/boltz-client/liquid-wallet ./data/boltz-client/bitcoin-wallet ./data/boltz-client/wallet ./data/boltz-client/boltz.db
  # recreate lightning node data folders preventing permission errors
  mkdir ./data/clightning-1 ./data/clightning-2 ./data/clightning-3 ./data/lnd-1 ./data/lnd-2 ./data/lnd-3 ./data/lnd-4
}

lnbits-regtest-restart(){
  lnbits-regtest-stop
  lnbits-regtest-start
}

boltz-client-init(){
  for i in 0 1 2; do
    fund_boltz_client
  done
  elements-cli-sim -generate 3 > /dev/null
}

lnbits-bitcoin-init(){
  echo "init_bitcoin_wallet..."
  bitcoin-cli-sim createwallet lnbits || bitcoin-cli-sim loadwallet lnbits
  echo "mining 150 blocks..."
  bitcoin-cli-sim -generate 150 > /dev/null
}

lnbits-elements-init(){
  echo "init_elements_wallet..."
  elements-cli-sim createwallet lnbits || elements-cli-sim loadwallet lnbits
  echo "mining 150 blocks..."
  elements-cli-sim -generate 150 > /dev/null
  elements-cli-sim rescanblockchain
}

lnbits-init(){
  echo "init_lnbits..."
  docker exec lnbits-lnbits-1 uv run python tools/create_fake_admin.py
}

lnbits-regtest-init(){
  lnbits-bitcoin-init
  lnbits-elements-init
  lnbits-lightning-sync
  lnbits-lightning-init
  boltz-client-init
  lnbits-init
}

lnbits-lightning-sync(){
  wait-for-clightning-sync 1
  wait-for-clightning-sync 2
  wait-for-clightning-sync 3
  wait-for-lnd-sync 1
  wait-for-lnd-sync 2
  wait-for-lnd-sync 3
  wait-for-lnd-sync 4
}

lnbits-lightning-init(){

  # create 10 UTXOs for each node
  for i in 0 1 2; do
    fund_clightning_node 1
    fund_clightning_node 2
    fund_clightning_node 3
    fund_lnd_node 1
    fund_lnd_node 2
    fund_lnd_node 3
    fund_lnd_node 4
  done

  echo "mining 3 blocks..."
  bitcoin-cli-sim -generate 3 > /dev/null

  lnbits-lightning-sync

  channel_confirms=6
  channel_size=24000000 # 0.024 btc
  balance_size=12000000 # 0.12 btc
  balance_size_msat=12000000000 # 0.12 btc

  # lnd-1 -> lnd-2
  lncli-sim 1 connect $(lncli-sim 2 getinfo | jq -r '.identity_pubkey')@lnbits-lnd-2-1 > /dev/null
  echo "open channel from lnd-1 to lnd-2"
  lncli-sim 1 openchannel $(lncli-sim 2 getinfo | jq -r '.identity_pubkey') $channel_size $balance_size > /dev/null
  bitcoin-cli-sim -generate $channel_confirms > /dev/null
  wait-for-lnd-channel 1

  # lnd-1 -> lnd-3
  lncli-sim 1 connect $(lncli-sim 3 getinfo | jq -r '.identity_pubkey')@lnbits-lnd-3-1 > /dev/null
  echo "open channel from lnd-1 to lnd-3"
  lncli-sim 1 openchannel $(lncli-sim 3 getinfo | jq -r '.identity_pubkey') $channel_size $balance_size > /dev/null
  bitcoin-cli-sim -generate $channel_confirms > /dev/null
  wait-for-lnd-channel 1

  # lnd-1 -> cln-1
  lncli-sim 1 connect $(lightning-cli-sim 1 getinfo | jq -r '.id')@lnbits-clightning-1-1 > /dev/null
  echo "open channel from lnd-1 to cln-1"
  lncli-sim 1 openchannel $(lightning-cli-sim 1 getinfo | jq -r '.id') $channel_size $balance_size > /dev/null
  bitcoin-cli-sim -generate $channel_confirms > /dev/null
  wait-for-lnd-channel 1

  # lnd-1 -> cln-2
  lncli-sim 1 connect $(lightning-cli-sim 2 getinfo | jq -r '.id')@lnbits-clightning-2-1 > /dev/null
  echo "open channel from lnd-1 to cln-2"
  lncli-sim 1 openchannel $(lightning-cli-sim 2 getinfo | jq -r '.id') $channel_size $balance_size > /dev/null
  bitcoin-cli-sim -generate $channel_confirms > /dev/null
  wait-for-lnd-channel 1

  # lnd-1 -> cln-3
  lncli-sim 1 connect $(lightning-cli-sim 3 getinfo | jq -r '.id')@lnbits-clightning-3-1 > /dev/null
  echo "open channel from lnd-1 to cln-3"
  lncli-sim 1 openchannel $(lightning-cli-sim 3 getinfo | jq -r '.id') $channel_size $balance_size > /dev/null
  bitcoin-cli-sim -generate $channel_confirms > /dev/null
  wait-for-lnd-channel 1

  # lnd-2 -> cln-2
  lncli-sim 2 connect $(lightning-cli-sim 2 getinfo | jq -r '.id')@lnbits-clightning-2-1 > /dev/null
  echo "open channel from lnd-2 to cln-2"
  lncli-sim 2 openchannel $(lightning-cli-sim 2 getinfo | jq -r '.id') $channel_size $balance_size > /dev/null
  bitcoin-cli-sim -generate $channel_confirms > /dev/null
  wait-for-lnd-channel 2

  # lnd-3 -> cln-3
  lncli-sim 3 connect $(lightning-cli-sim 3 getinfo | jq -r '.id')@lnbits-clightning-3-1 > /dev/null
  echo "open channel from lnd-3 to cln-1"
  lncli-sim 3 openchannel $(lightning-cli-sim 3 getinfo | jq -r '.id') $channel_size $balance_size > /dev/null
  bitcoin-cli-sim -generate $channel_confirms > /dev/null
  wait-for-lnd-channel 3

  # lnd-3 -> cln-1
  lncli-sim 3 connect $(lightning-cli-sim 1 getinfo | jq -r '.id')@lnbits-clightning-1-1 > /dev/null
  echo "open channel from lnd-3 to cln-1"
  lncli-sim 3 openchannel $(lightning-cli-sim 1 getinfo | jq -r '.id') $channel_size $balance_size > /dev/null
  bitcoin-cli-sim -generate $channel_confirms > /dev/null
  wait-for-lnd-channel 3

  # lnd-1 -> eclair-1
  lncli-sim 1 connect $(get-eclair-pubkey)@lnbits-eclair-1 > /dev/null
  echo "open channel from lnd-2 to eclair-1"
  lncli-sim 1 openchannel $(get-eclair-pubkey) $channel_size $balance_size > /dev/null
  bitcoin-cli-sim -generate $channel_confirms > /dev/null
  wait-for-lnd-channel 1

  # lnd-2 -> eclair-1
  lncli-sim 2 connect $(get-eclair-pubkey)@lnbits-eclair-1 > /dev/null
  echo "open channel from lnd-2 to eclair-1"
  lncli-sim 2 openchannel $(get-eclair-pubkey) $channel_size $balance_size > /dev/null
  bitcoin-cli-sim -generate $channel_confirms > /dev/null
  wait-for-lnd-channel 2

  wait-for-clightning-channel 1
  wait-for-clightning-channel 2
  wait-for-clightning-channel 3

  wait-for-eclair-channel

  lnbits-lightning-sync

}

wait-for-lnd-channel(){
  while true; do
    pending=$(lncli-sim $1 pendingchannels | jq -r '.pending_open_channels | length')
    echo "lnd-$1 pendingchannels: $pending"
    if [[ "$pending" == "0" ]]; then
      break
    fi
    sleep 1
  done
}

wait-for-lnd-sync(){
  while true; do
    if [[ "$(lncli-sim $1 getinfo 2>&1 | jq -r '.synced_to_chain' 2> /dev/null)" == "true" ]]; then
      echo "lnd-$1 is synced!"
      break
    fi
    echo "waiting for lnd-$1 to sync..."
    sleep 1
  done
}

wait-for-clightning-channel(){
  while true; do
    pending=$(lightning-cli-sim $1 getinfo | jq -r '.num_pending_channels | length')
    echo "cln-$1 pendingchannels: $pending"
    if [[ "$pending" == "0" ]]; then
      if [[ "$(lightning-cli-sim $1 getinfo 2>&1 | jq -r '.warning_bitcoind_sync' 2> /dev/null)" == "null" ]]; then
        if [[ "$(lightning-cli-sim $1 getinfo 2>&1 | jq -r '.warning_lightningd_sync' 2> /dev/null)" == "null" ]]; then
          break
        fi
      fi
    fi
    sleep 1
  done
}

wait-for-clightning-sync(){
  while true; do
    if [[ ! "$(lightning-cli-sim $1 getinfo 2>&1 | jq -r '.id' 2> /dev/null)" == "null" ]]; then
      if [[ "$(lightning-cli-sim $1 getinfo 2>&1 | jq -r '.warning_bitcoind_sync' 2> /dev/null)" == "null" ]]; then
        if [[ "$(lightning-cli-sim $1 getinfo 2>&1 | jq -r '.warning_lightningd_sync' 2> /dev/null)" == "null" ]]; then
          echo "cln-$1 is synced!"
          break
        fi
      fi
    fi
    echo "waiting for cln-$1 to sync..."
    sleep 1
  done
}
