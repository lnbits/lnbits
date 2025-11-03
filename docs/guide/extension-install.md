---
layout: default
title: Extension Install
nav_order: 1
---

# Extension Install

Anyone can create an extension by following the [example extension](https://github.com/lnbits/example) and [making extensions](https://github.com/lnbits/lnbits/blob/main/docs/devs/extensions.md) dev guide.

Extensions can be installed by an admin user after the **LNbits** instance has been started.

## Configure Repositories

Go to `Manage Server` > `Server` > `Extensions Manifests`

![image](https://user-images.githubusercontent.com/2951406/213494038-e8152d8e-61f2-4cb7-8b5f-361fc3f9a31f.png)

An `Extension Manifest` is a link to a `JSON` file which contains information about various extensions that can be installed (repository of extensions).
Multiple repositories can be configured. For more information check the [Manifest File](https://github.com/lnbits/lnbits/blob/main/docs/guide/extension-install.md#manifest-file) section.

**LNbits** administrators should configure their instances to use repositories that they trust (like the [lnbits-extensions](https://github.com/lnbits/lnbits-extensions/) one).

> **Warning**
> Extensions can have bugs or malicious code, be careful what you install!!

## Install New Extension

Only administrator users can install or upgrade extensions.

Go to `Manage Extensions` > `Add Remove Extensions`
![image](https://user-images.githubusercontent.com/2951406/213647560-67da4f8a-3315-436f-b690-3b3de536d2e6.png)

A list of extensions that can be installed is displayed:
![image](https://user-images.githubusercontent.com/2951406/213647904-d463775e-86b6-4354-a199-d50e08565092.png)

> **Note**
> If the extension is installed from a GitHub repo, then the GitHub star count will be shown.

Click the `Manage` button in order to install a particular release of the extension.
![image](https://user-images.githubusercontent.com/2951406/213648543-6c5c8cae-3bf4-447f-8499-344cac61c566.png)

> **Note**
> An extension can be listed in more than one repository. The admin user must select which repository it wants to install from.

Select the version to be installed (usually the last one) and click `Install`. One can also check the `Release Notes` first.

> **Note**:
>
> For Github repository: the order of the releases is the one in the GitHub releases page
>
> For Explicit Release: the order of the releases is the one in the "extensions" object

The extension has been installed but it cannot be accessed yet. In order to activate the extension toggle it in the `Activated` state.

Go to `Manage Extensions` (as admin user or regular user). Search for the extension and enable it.

## Uninstall Extension

On the `Install` page click `Manage` for the extension you want to uninstall:
![image](https://user-images.githubusercontent.com/2951406/213653194-32cbb1da-dcc8-43cf-8a82-1ec5d2d3dc16.png)

The installed release is highlighted in green.

Click the `Uninstall` button for the release or the one in the bottom.

Users will no longer be able to access the extension.

> **Note**
> The database for the extension is not removed. If the extension is re-installed later, the data will be accessible.

## Manifest File

The manifest file is just a `JSON` file that lists a collection of extensions that can be installed. This file is of the form:

```json
{
    "extensions": [...]
    "repos": [...]
}
```

There are two ways to specify installable extensions:

### Explicit Release

It goes under the `extensions` object and it is of the form:

```json
{
  "id": "lnurlp",
  "name": "LNURL Pay Links",
  "version": 1,
  "shortDescription": "Upgrade to version 111111111",
  "icon": "receipt",
  "details": "All charge names should be <code>111111111</code>. API panel must show: <br>",
  "archive": "https://github.com/lnbits/lnbits-extensions/raw/main/new/lnurlp/1/lnurlp.zip",
  "hash": "a22d02de6bf306a7a504cd344e032cc6d48837a1d4aeb569a55a57507bf9a43a",
  "htmlUrl": "https://github.com/lnbits/lnbits-extensions/tree/main/new/lnurlp/1",
  "infoNotification": "This is a very old version",
  "dependencies": ["other-ext-id"]
}
```

<details><summary>Fields Detailed Description</summary>

| Field                | Type          |           | Description                                                                                                                                                          |
| -------------------- | ------------- | --------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| id                   | string        | mandatory | The ID of the extension. Must be unique for each extension. It is also used as the path in the URL.                                                                  |
| name                 | string        | mandatory | User friendly name for the extension. It will be displayed on the installation page.                                                                                 |
| version              | string        | mandatory | Version of this release. [Semantic versioning](https://semver.org/) is recommended.                                                                                  |
| shortDescription     | string        | optional  | A few words about the extension. It will be displayed on the installation page.                                                                                      |
| icon                 | string        | optional  | quasar valid icon name                                                                                                                                               |
| details              | string (html) | optional  | Details about this particular release                                                                                                                                |
| archive              | string        | mandatory | URL to the `zip` file that contains the extension source-code                                                                                                        |
| hash                 | string        | mandatory | The hash (`sha256`) of the `zip` file. The extension will not be installed if the hash is incorrect.                                                                 |
| htmlUrl              | string        | optional  | Link to the extension home page.                                                                                                                                     |
| infoNotification     | string        | optional  | Users that have this release installed will see a info message for their extension. For example if the extension support will be terminated soon.                    |
| criticalNotification | string        | optional  | Reserved for urgent notifications. The admin user will receive a message each time it visits the `Install` page. One example is if the extension has a critical bug. |
| dependencies         | list          | optional  | A list of extension IDs. It signals that those extensions must be installed BEFORE the this one can be installed.                                                    |

</details>

This mode has the advantage of strictly specifying what releases of an extension can be installed.

### GitHub Repository

It goes under the `repos` object and it is of the form:

```json
{
  "id": "withdraw",
  "organisation": "lnbits",
  "repository": "withdraw-extension"
}
```

| Field        | Type   | Description                                                                                         |
| ------------ | ------ | --------------------------------------------------------------------------------------------------- |
| id           | string | The ID of the extension. Must be unique for each extension. It is also used as the path in the URL. |
| organisation | string | The GitHub organisation (eg: `lnbits`)                                                              |
| repository   | string | The GitHub repository name (eg: `withdraw-extension`)                                               |

The admin user will see all releases from the Github repository:

![image](https://user-images.githubusercontent.com/2951406/213508934-11de5ae5-2045-471c-854b-94b6acbf4434.png)
