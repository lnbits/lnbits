
![Lightning network wallet](https://i.imgur.com/arUWZbH.png)
# LNbits
Simple Python lightning-network wallet/accounts system. Use https://lnbits.com, or run your own LNbits server!

LNbits is a very simple server that sits on top of a funding source, and can be used as: 
* Accounts system to mitigate the risk of exposing applications to your full balance, via unique API keys for each wallet!
* Fallback wallet for the LNURL scheme
* Instant wallet for LN demonstrations 

The wallet can run on top of any lightning-network funding source such as LND, lntxbot, paywall, opennode, etc

LNbits is still in BETA. Please report any vulnerabilities responsibly
## LNbits as an account system
LNbits is packaged with tools to help manage funds, such as a table of transactions, line chart of spending, export to csv + more to come..


![Lightning network wallet](https://i.imgur.com/Sd4ri3T.png)

Each wallet also comes with its own API keys, to help partition the exposure of your funding source. 

(LNbits M5StackSats available here https://github.com/arcbtc/M5StackSats) 

![lnurl ATM](https://i.imgur.com/ABruzAn.png)

## LNbits as an LNURL-withdraw fallback
LNURL has a fallback scheme, so if scanned by a regular QR code reader it can default to a URL. LNbits exploits this to generate an instant wallet using the LNURL-withdraw.

![lnurl fallback](https://i.imgur.com/CPBKHIv.png)
https://github.com/btcontract/lnurl-rfc/blob/master/spec.md

Adding **/lnurlwallet?lightning="LNURL-WITHDRAW"** will trigger a withdraw that builds an LNbits wallet. 
Example use would be an ATM, which utilises LNURL, if the user scans the QR with a regular QR code scanner app, they will stilll be able to access the funds.

![lnurl ATM](https://i.imgur.com/Gi6bn3L.jpg)

## LNbits as an insta-wallet
Wallets can be easily generated and given out to people at events (one click multi-wallet generation to be added soon).
"Go to this  website", has a lot less friction than "Download this app".

![lnurl ATM](https://i.imgur.com/SF5KoIe.png)

# Running LNbits locally
Download this repo

LNbits uses [Flask](http://flask.pocoo.org/).  
Feel free to contribute to the project.

Application dependencies
------------------------
The application uses [Pipenv][pipenv] to manage Python packages.
While in development, you will need to install all dependencies:

    $ pipenv shell
    $ pipenv install --dev

Running the server
------------------

    $ flask run

There is an environment variable called `FLASK_ENV` that has to be set to `development`
if you want to run Flask in debug mode with autoreload

[pipenv]: https://docs.pipenv.org/#install-pipenv-today

# Tip me
If you like this project and might even use or extend it, why not send some tip love!
https://paywall.link/to/f4e4e
