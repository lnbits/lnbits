# Extension Install

Anyone can create an extension by following the [example extension](https://github.com/lnbits/lnbits/tree/extension_install_02/lnbits/extensions/example).

Extensions can be installed by an admin user after the **LNbits** instance has been started.

## Configure Repositories

Go to `Manage Server` > `Server` > `Extensions Manifests`

![image](https://user-images.githubusercontent.com/2951406/213494038-e8152d8e-61f2-4cb7-8b5f-361fc3f9a31f.png)


An `Extension Manifest` is an link to a `JSON` file whitch contains information about various extensions that can be installed (repository of extensions).
Multiple repositories can be configured.


**LNbits** administrators should configure their instances to use repositories that they trust (like the [lnbits-extensions](https://github.com/lnbits/lnbits-extensions/) one). **Warning**: extensions can have bugs or mallicious code, be carefull what you install!!

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
            "infoNotification": "This is a very old version"
        }
```

| Field                | Type          |           | Description                                                                                                                                                          |
|----------------------|---------------|-----------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| id                   | string        | mandatory | The ID of the extension. Must be unique for each extensions. It is also as path in the URL.                                                                          |
| name                 | string        | mandatory | User friendly name for the extension. It will be displayed on the installation page.                                                                                 |
| version              | string        | mandatory | Version of this release. [Semantic versoning](https://semver.org/) is recommended.                                                                                   |
| shortDescription     | string        | optional  | A few words about the extension. It will be displayed on the installation page.                                                                                      |
| icon                 | string        | optional  | quasar valid icon name                                                                                                                                               |
| details              | string (html) | optional  | Details about this particular release                                                                                                                                |
| archive              | string        | mandatory | URL to the `zip` file that contains the extension source-code                                                                                                        |
| hash                 | string        | mandatory | The hash (`sha256`) of the `zip` file. The extension will not be installed if the hash is incorrect.                                                                 |
| htmlUrl              | string        | optional  | Link to the extension home page.                                                                                                                                     |
| infoNotification     | string        | optional  | Users that have this release installed will see a info message for their extension. For example if the extension support will be terminated soon.                    |
| criticalNotification | string        | optional  | Reserved for urgent notifications. The admin user will receive a message each time it visits the `Install` page. One example is if the extension has a critical bug. |


### GitHub Repository
