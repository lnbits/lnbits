# Push Notifications

This extension enables you to receive push messages about incoming payments in all your user wallets on multiple
devices.

## Usage

1. Open you LNBits user wallets page in browser on your device
2. Enable and select the push notifications extension
3. Click "Subscribe"
4. Give permission to show notification messages when asked
5. Test notification message is sent as confirmation

## How it works

- Notification API allows displaying messages on device
- Service Worker creates `PushSubscription` object via Push API
- The whole object is stored with endpoint and host name for each user wallet
- The endpoint is used as identifier for the wallet subscriptions
- The host name is required to build URL used to open wallet on message click
- The stored object is directly used to send push notification
- Stale subscriptions get deleted on errors when sending pushes
- Package `pywebpush` is used to send messages and create VAPID key pair
- The VAPID key pair is created once on initialization in data folder
- The VAPID public key is passed to frontend via inline script

## Usage Requirements

- HTTPS hosting of LNbits for Service Worker
- Device with browser that supports Service Worker API, Notifications API and Push API

## Not Supported

* Subscription refreshes (https://w3c.github.io/push-api/#subscription-refreshes)