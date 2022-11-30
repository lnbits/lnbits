---
layout: default
parent: For developers
title: Websockets
nav_order: 2
---


Websockets
=================

`websockets` are a great way to add a two way instant data channel between server and client. This example was taken from the `copilot` extension, we create a websocket endpoint which can be restricted by `id`, then can feed it data to broadcast to any client on the socket using the `updater(extension_id, data)` function (`extension` has been used in place of an extension name, wreplace to your own extension):


```sh
from fastapi import Request, WebSocket, WebSocketDisconnect

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket, extension_id: str):
        await websocket.accept()
        websocket.id = extension_id
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, extension_id: str):
        for connection in self.active_connections:
            if connection.id == extension_id:
                await connection.send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)


manager = ConnectionManager()


@extension_ext.websocket("/ws/{extension_id}", name="extension.websocket_by_id")
async def websocket_endpoint(websocket: WebSocket, extension_id: str):
    await manager.connect(websocket, extension_id)
    try:
        while True:
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


async def updater(extension_id, data):
    extension = await get_extension(extension_id)
    if not extension:
        return
    await manager.send_personal_message(f"{data}", extension_id)
```

Example vue-js function for listening to the websocket:

```
initWs: async function () {
    if (location.protocol !== 'http:') {
        localUrl =
          'wss://' +
          document.domain +
          ':' +
          location.port +
          '/extension/ws/' +
          self.extension.id
      } else {
        localUrl =
          'ws://' +
          document.domain +
          ':' +
          location.port +
          '/extension/ws/' +
          self.extension.id
      }
    this.ws = new WebSocket(localUrl)
    this.ws.addEventListener('message', async ({data}) => {
      const res = JSON.parse(data.toString())
      console.log(res)
    })
},
```
