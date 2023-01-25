Rate Limiting
=============

To enable rate limiting, add `rate_limits` to your config file, like this:
```
rate_limits:
    global:
        EVENT: 1000/s
    ip:
        EVENT: 1/minute
        REQ: 10/s
```

The rate limiter keeps track of global and per/ip rate limits, per message-type.

The syntax for each option is:
`frequency/interval`

The options for interval are `hour`, `minute`, `second` (or `h`, `m`, `s`)

So, to allow each ip to add 100 events per hour, but only 1 event per second:
```
rate_limits:
    ip:
        EVENT: 100/hour,1/sec
```

Or you can cap the global limit for events, and allow individual connections to exceed the rate:
```
rate_limits:
    global:
        EVENT: 1000/min
    ip:
        EVENT: 100/s
```

== Per/IP Exemptions ==

To exempt or restrict certain addresses from rate limits:

```
rate_limits:
    ip:
        EVENT: 100/hour,10/sec
    127.0.0.1:
        EVENT: 100/sec
    8.8.8.8:
        EVENT: -1/sec
```

In this case, 8.8.8.8 would never be limited.


== Custom Rate Limiter Class ==

You can also customize rate limiting with your own class:
```
rate_limiter_class: my_custom_module.MyRateLimiter
rate_limits:
    arbitrary_option: foo
```

The `rate_limits` dict will be passed to your rate limiter instance. It must implement two methods:
`is_limited(ip_address, message)` and `cleanup()`

