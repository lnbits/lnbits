---
layout: default
parent: For developers
title: Websockets
nav_order: 2
---

# Websockets

`websockets` are a great way to add a two way instant data channel between server and client.

LNbits has a useful in built websocket tool. With a websocket client connect to (obv change `somespecificid`) `wss://demo.lnbits.com/api/v1/ws/somespecificid` (you can use an online websocket tester). Now make a get to `https://demo.lnbits.com/api/v1/ws/somespecificid/somedata`. You can send data to that websocket by using `from lnbits.core.services import websocketUpdater` and the function `websocketUpdater("somespecificid", "somdata")`.

Example vue-js function for listening to the websocket:

```
initWs: async function () {
    if (location.protocol !== 'http:') {
        localUrl =
          'wss://' +
          document.domain +
          ':' +
          location.port +
          '/api/v1/ws/' +
          self.item.id
      } else {
        localUrl =
          'ws://' +
          document.domain +
          ':' +
          location.port +
          '/api/v1/ws/' +
          self.item.id
      }
    this.ws = new WebSocket(localUrl)
    this.ws.addEventListener('message', async ({data}) => {
      const res = JSON.parse(data.toString())
      console.log(res)
    })
},
```
