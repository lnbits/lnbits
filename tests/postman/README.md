# Postman API Regression Test
This folder contains some regression test on the API endpoints of LNBits. The test is created in [Postman](https://www.postman.com/). 

## How to run

### Postman
The test can be run from postman. Import the collection- and the environment file and update environment settings to your needs.
If you have any questions ask in [LNBits Telegram](https://t.me/lnbits) and tag <i>teunehv</i>

### Github action
In the github workflow folder an postman.yml is added. This will schedule the test daily on lnbits.com.

## More about the test
Description of the files needed for the test.
### environment.json
This file contains the enviroment settings for the test to run. A test needs several settings:

    E_host        = host of the test to run on
    E_wallet_id   = id of the wallet to use during test. Should contain at least 5 sats
    E_admin_key   = admin key of the wallet to use during test.
    E_invoice_key = invoice key of the wallet to use during test.
    E_wallet_name = wallet name of the wallet to use during test.
    E_user_id     = user id of the owner of the wallet

### Regression.postman_collection

The test contains the following scenarios:

![Testset](https://i.imgur.com/aUcSygD.png)

Additional tests will be added in the future. 

