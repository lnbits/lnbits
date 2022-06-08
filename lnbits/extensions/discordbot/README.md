# Discord Bot

## Provide LNbits wallets for all your Discord users

_This extension is a modifed version of LNbits [User Manager](../usermanager/README.md)_

The intended usage of this extension is to connect it to a specifically designed [Discord Bot](https://github.com/chrislennon/lnbits-discord-bot) leveraging LNbits as a community based lightning node.

## Setup
This bot can target [lnbits.com](https://lnbits.com) or a self hosted instance.

To setup and run the bot instructions are located [here](https://github.com/chrislennon/lnbits-discord-bot#installation) 

## Usage
This bot will allow users to interact with it in the following ways [full command list](https://github.com/chrislennon/lnbits-discord-bot#commands):

`/create` Will create a wallet for the Discord user 
  - (currently limiting 1 Discord user == 1 LNbits user == 1 user wallet)

![create](https://imgur.com/CWdDusE.png)

`/balance` Will show the balance of the users wallet.

![balance](https://imgur.com/tKeReCp.png)

`/tip @user [amount]` Will sent money from one user to another
  - If the recieving user does not have a wallet, one will be created for them
  - The receiving user will receive a direct message from the bot with a link to their wallet

![tip](https://imgur.com/K3tnChK.png)

`/payme [amount] [description]` Will open an invoice that can be paid by any user

![payme](https://imgur.com/dFvAqL3.png)
