This is a python3 implementation of a [nostr](https://github.com/nostr-protocol/nostr) relay.

Note: this requires Python 3.9+, but is only tested on 3.11

To intall:

`pip install nostr-relay`

To run:

`nostr-relay serve`

to change the location of the database and other settings, create a yaml config file that looks [like this](https://code.pobblelabs.org/fossil/nostr_relay/file?name=nostr_relay/config.yaml):

and run with `nostr-relay -c /path/to/config.yaml serve`


Then add `ws://127.0.0.1:6969` to your relay list.

(obviously, in production you should use a TLS certificate)

Visit [the nostr-relay fossil repository](https://code.pobblelabs.org/fossil/nostr_relay) for more information.