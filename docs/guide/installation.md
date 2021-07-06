---
layout: default
title: Basic installation
nav_order: 2
---


Basic installation
==================

Download this repo and install the dependencies:

```sh
git clone https://github.com/lnbits/lnbits.git
cd lnbits/
# ensure you have virtualenv installed, on debian/ubuntu 'apt install python3-venv' should work
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
cp .env.example .env
mkdir data
./venv/bin/quart assets
./venv/bin/quart migrate
./venv/bin/hypercorn -k trio --bind 0.0.0.0:5000 'lnbits.app:create_app()'
```

Now you can visit your LNbits at http://localhost:5000/.

Now modify the `.env` file with any settings you prefer and add a proper [funding source](./wallets.md) by modifying the value of `LNBITS_BACKEND_WALLET_CLASS` and providing the extra information and credentials related to the chosen funding source.

Then you can restart it and it will be using the new settings.

You might also need to install additional packages or perform additional setup steps, depending on the chosen backend. See [the short guide](./wallets.md) on each different funding source.

Docker installation
===================

To install using docker you first need to build the docker image as:
```
git clone https://github.com/lnbits/lnbits.git
cd lnbits/ # ${PWD} referred as <lnbits_repo>
docker build -t lnbits .
```

You can launch the docker in a different directory, but make sure to copy `.env.example` from lnbits there
```
cp <lnbits_repo>/.env.example .env
```
and change the configuration in `.env` as required.

Then create the data directory for the user ID 1000, which is the user that runs the lnbits within the docker container.
```
mkdir data
sudo chown 1000:1000 ./data/
```

Then the image can be run as:
```
docker run --detach --publish 5000:5000 --name lnbits --volume ${PWD}/.env:/app/.env --volume ${PWD}/data/:/app/data lnbits
```
Finally you can access your lnbits on your machine at port 5000.


Troubleshooting
===============

### LNBITS cannot connect to the configured system (TCP Layer not checked)

Currently lnbits is not stating what exactly have gone wrong during connection to a wallet. To tackle the issue i will try to give you
a helping hand. In this case lnbits cannot connect, as there is *no* tcp connection possible to the lnd. For instance because
of firewall settings or wrong ip/port configuration. Check your config and try to connect to the ip and port you have set with
netcat or socat. Example:
Config:
```
# LndRestWallet
LND_REST_ENDPOINT=https://1.2.3.4:8080/
LND_REST_CERT="/home/bob/.config/Zap/lnd/bitcoin/mainnet/wallet-1/data/chain/bitcoin/mainnet/tls.cert"
LND_REST_MACAROON="HEXSTRING"
```
Example Timeout:
```
$ nc -v 1.2.3.4 8080
nc: connect to 1.2.3.4 port 8080 (tcp) failed: Connection timed out
```
Example Connection Refused
```
nc -v 127.0.1.5 8081
nc: connect to 127.0.1.5 port 8081 (tcp) failed: Connection refused
```
Example Success
```
nc -v 127.0.0.1 8080
Connection to 127.0.0.1 8080 port [tcp/http-alt] succeeded!
```
If there is a connect timeout or connection refused the service is not reachable or not running. Recheck if it is running and/or 
your configuration is correct.

If you are using it with the supplied dockerfile i used the following quick python snippet to check if the configured system and port is reachable:
```
docker exec -ti lnbits python
```
In python interpreter write:
```
import socket
s = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
s.connect(('1.2.3.4',8080))
s.send(b'GET / HTTP/1.1\r\n\r\n\r\n')
s.recv(2048)
```
Please replace the 1.2.3.4 with your configured ip. You should get some HTTP response.

### LNBITS cannot connect to the configured system (TCP Layer works, but not SSL/TLS Layer)
In dockered Environments or remote machine usage different ip addresses are used. lnbits (correctly) checks if the ip-address it connects to, is in the certifacte. If this is not the case it stops execution and just says it had problems with the system. Before 
this please check IF lnbits can REACH the lnd and port configured.

To tackle this issue:

1. Go to lnd.conf
2. Enter IP address lnbits is connecting to to a new field named: tlsextraip. Example lnd.conf partly:

```
[Application Options]
alias=lcodes-test
color=#F6A400
listen=0.0.0.0:9735
rpclisten=0.0.0.0:10009
restlisten=0.0.0.0:8080
maxpendingchannels=3
minchansize=10000
accept-keysend=true
tlsextraip=1.2.3.4
```
3. After adding new ip, restart lnd, so it is creating a new certificate
4. Copy new certificate to the path of your wallet configuration for LND REST it is LND_REST_CERT.
5. Check if your lnbits is really connecting to the ip address you added to the field in .env of lnbits
```
# LndRestWallet
LND_REST_ENDPOINT=https://1.2.3.4:8080/
LND_REST_CERT="/data/lnd/tls.cert"
LND_REST_MACAROON="HEXSTRING..."
```
6. Restart lnbits  
