# Strike

## Forward all received payments to your Strike account

This extension provides an automated way to forward lightning payments received to your wallet to your Strike account in USD in near real-time.

## Installation Note

If you are using LNBits hosted by someone else, it's possible that they did not configure LNBits with their own Strike API Keys. If that is the case, you are required to enter your own Strike API Keys when using this extension. 

You can create Strike API Keys at https://strike.me/developer/. Registration is free.

If you are hosting LNBits for yourself, or others, you can optionally set the `STRIKE_API_KEY` environment variable in your `.env` file.

## Usage

1. Create a forwarding configuration by clicking "CONFIGURE FORWARDING".
2. Enter your Strike handle/username (check your Strike app if unsure).
3. (optional) Enter a description.
4. (optional?, see note above) Enter your Strike API Key.
5. Click "FORWARD" to save.
6. Any payments received will now be forwarded to your Strike account immediately upon receipt.