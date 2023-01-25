# CHANGES

## 1.4.9

* Ensure that code is compatible with python 3.9+

## 1.4.8

* Support NIP-33 - parameterized replaceable events
* Fixed verification batch query to not reverify every time
* Allow for limit=0 queries
* Fixed json dump

## 1.4.7

* Added configurable limit for subscriptions per connection: `subscription_limit` (default 32)
* Added configurable timeout for idle connections: `message_timeout` (default 30minutes)
* Fixed verification task not running
* bugfixes for crazy queries

## 1.4.6

* use a better challenge for NIP-42 auth

## 1.4.1 - 1.4.5

* bugfixes for postgres compatibility

## 1.4.0

* See [140upgrade.md](140upgrade.md) for upgrade instructions
* Switch to sqlalchemy for data access
* Refactor to allow pluggable storage backend
* Added `nostr-relay load` command

## 1.3.5

* Update authentication to reflect draft NIP-42
* Serve event json from /e/ instead of /event/
* Added `nostr-relay dump` command to dump all events as JSON

## 1.3.4

* Added command `nostr-relay mirror` to mirror requests between relays
* Reduce noisy logging

## 1.3.3

* bugfix for garbage collector deadlock

## 1.3.1

* Only advertise NIP-42 if authentication is enabled

## 1.3

* Added authentication according to NIP-42
* Allow per-ip rate limit rules
* Refactored to allow for :memory: sqlite databases (for testing or performance)

## 1.2.6

* bugfix: enable foreign keys on the garbage collector

## 1.2.5

* Using subselects for tag queries greatly increases performance

## 1.2.4

* bugfix: foreign keys were not enabled on the sqlite connection
* optimize db upon close

## 1.2.3

* Replace replaceable events if the created time is the same as the replaced event

## 1.2.2

* Reject events that are > 1 hour in the future
* Process tags for all events
* Added cli to reprocess event tags
* Added convenience functions to run the server programatically
   `nostr_relay.web.run_with_gunicorn()`
   `nostr_relay.web.run_with_uvicorn()`

## 1.2.1

* config file wasn't include in wheel
 
## 1.2

* Added rate limiter

## 1.1.8

* Support for NIP-40 -- event expiration tag
 