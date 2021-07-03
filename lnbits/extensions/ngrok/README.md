<h1>Ngrok</h1>
<h2>Serve lnbits over https for free using ngrok</h2>

<img src="https://i.ibb.co/QfDD4FS/Screenshot-2021-07-02-7-28-35-AM.png">

<h2>How it works</h2>

When enabled, ngrok creates a tunnel to ngrok.io with https support and tells you the https web address where you can access your lnbits instance. If you are not the first user to enable it, it doesn't create a new one, it just tells you the existing one. Useful for creating/managing/using lnurls, which must be served either via https or via tor. Note that if you restart your device, your device will generate a new url. If anyone is using your old one for wallets, lnurls, etc., whatever they are doing will stop working.

<h2>Installation</h2>

Check the Extensions page on your instance of lnbits. If you have copy of lnbits with ngrok as one of the built in extensions, click Enable -- that's the only thing you need to do to install it.

If your copy of lnbits does not have ngrok as one of the built in extensions, stop lnbits, create go into your lnbits folder, and run this command: ./venv/bin/pip install pyngrok. Then go into the lnbits subdirectory and the extensions subdirectory within that. (So lnbits > lnbits > extensions.) Create a new subdirectory in there called freetunnel, download this repository as a zip file, and unzip it in the freetunnel directory. If your unzipper creates a new "freetunnel" subdirectory, take everything out of there and put it in the freetunnel directory you created. Then go back to the top level lnbits directory and run these commands:

```
./venv/bin/quart assets
./venv/bin/quart migrate
./venv/bin/hypercorn -k trio --bind 0.0.0.0:5000 'lnbits.app:create_app()'
```
