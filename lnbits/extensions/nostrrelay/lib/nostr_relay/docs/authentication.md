# Authentication

nostr-relay implements authentication according to [NIP-42](https://github.com/nostr-protocol/nips/blob/auth/42.md).

The specification allows clients to authenticate whenever they want, using an authentication event of kind 22242. Authentication will persist for the duration of the websocket connection.

The relay may send `NOTICE` messages if authentication is required for certain actions.

Currently, this implementation defines `actions` and `roles`. The actions are `save` and `query`, corresponding to `EVENT` and `REQ` message types.

There can be an arbitrary number of roles. The only role used internally is `a` -- corresponding to an anonymous, logged-out user.  
You can associate public keys with whichever (single-letter) roles you want. In the future, there may be more actions and fine-grained permissions per role.

## Configuration

To enable, add this to your configuration file:
```
authentication:
  valid_urls: 
    - wss://my.relay.url
  enabled: true
  actions:
    save: w
    query: ra
```

This would require the `w` role to add events, but anyone with the `r` role or anyone logged-out (who implictly get the `a` role) would be allowed to query.

If there are no public keys assigned to roles, this configuration would allow access for anyone:
```
authentication:
  valid_urls: 
    - wss://my.relay.url
  enabled: true
  actions:
    save: a
    query: a
```

You must add the url(s) that your relay answers to, in order to validate the authentication event.

## How to assign roles

`nostr-relay -c /your/config/file.yaml role set -p <public_key> -r <roles>`

To get roles:

`nostr-relay -c /your/config/file.yaml role get -p <public_key>`

## Extending Authentication

To implement custom authentication or roles, create your own class somewhere with these methods:

`async def authenticate(auth_event_dict)`

This method should return an opaque token containing auth roles.

and 

`async def can_do(auth_token, action: str, target=None)`

This should return True/False if the auth token can perform the action.

Currently, `target` can be an event or a subscription object.

Then, in your configuration:

```
authentication:
  enabled: true
  authenticator_class: my.custom.module.MyAuthenticator
  actions:
    save: w
    query: ra
```

Your class will be initialized like this:
`MyAuthenticator(storage, authentication_config: dict)`


## Future Work

There will be fine-grained, configurable permission checks -- for instance, to allow pubkeys to save only their own events, or events of pubkeys that follow them, etc.

Another check could evaluate the contents of a `REQ` filter to determine whether to show the results.

