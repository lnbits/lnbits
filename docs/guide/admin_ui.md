---
layout: default
title: Admin UI
nav_order: 4
---


Admin UI
========
The LNbits Admin UI lets you change LNbits settings via the LNbits frontend.
It is disabled by default and the first time you set the enviroment variable LNBITS_ADMIN_UI=true
the settings are initialized and saved to the database and will be used from there as long the UI is enabled.
From there on the settings from the database are used.


Super User
==========
With the Admin UI we introduced the super user, it is created with the initialisation of the Admin UI and will be shown with a success message in the server logs.
The super user has access to the server and can change settings that may crash the server and make it unresponsive via the frontend and api, like changing funding sources.

Also only the super user can brrrr satoshis to different wallets.

The super user is only stored inside the settings table of the database and after the settings are "reset to defaults" and a restart happened,
a new super user is created.

The super user is never sent over the api and the frontend only receives a bool if you are super user or not.

We also added a decorator for the API routes to check for super user.

There is also the possibility of posting the super user via webhook to another service when it is created. you can look it up here https://github.com/lnbits/lnbits/blob/main/lnbits/settings.py `class SaaSSettings`


Admin Users
===========
enviroment variable: LNBITS_ADMIN_USERS, comma-seperated list of user ids
Admin Users can change settings in the admin ui aswell, with the exception of funding source settings, because they require e server restart and could potentially make the server inaccessable. Also they have access to all the extension defined in LNBITS_ADMIN_EXTENSIONS.


Allowed Users
=============
enviroment variable: LNBITS_ALLOWED_USERS, comma-seperated list of user ids
By defining this users, LNbits will no longer be useable by the public, only defined users and admins can then access the LNbits frontend.


How to activate
=============
```
$ sudo systemctl stop lnbits.service
$ cd ~/lnbits-legend
$ sudo nano .env
```
-> set: `LNBITS_ADMIN_UI=true`

Now start LNbits once in the terminal window
``` 
$ poetry run lnbits 
```
It will now show you the Super User Account:

`SUCCESS | ✔️ Access super user account at: https://127.0.0.1:5000/wallet?usr=5711d7..`

The `/wallet?usr=..` is your super user account. You just have to append it to your normal LNbits web domain.

After that you will find the __`Admin` / `Manage Server`__ between `Wallets` and `Extensions`

Here you can design the interface, it has TOPUP to fill wallets and you can restrict access rights to extensions only for admins or generally deactivated for everyone. You can make users admins or set up Allowed Users if you want to restrict access. And of course the classic settings of the .env file, e.g. to change the funding source wallet or set a charge fee.

Do not forget
```
sudo systemctl start lnbits.service
```
A little hint, if you set `RESET TO DEFAULTS`, then a new Super User Account will also be created. The old one is then no longer valid.
