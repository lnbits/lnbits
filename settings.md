# LNbits Settings Reference

| Name                           | Type                | Default Value                | Env File Only | Description                                                                                           |
|--------------------------------|---------------------|------------------------------|---------------|-------------------------------------------------------------------------------------------------------|
| debug                          | bool                | False                        | Yes           |                                                                                                       |
| debug_database                 | bool                | False                        | Yes           |                                                                                                       |
| bundle_assets                  | bool                | True                         | Yes           |                                                                                                       |
| host                           | str                 | "127.0.0.1"                  | Yes           |                                                                                                       |
| port                           | int                 | 5000                         | Yes           |                                                                                                       |
| forwarded_allow_ips            | str                 | "*"                          | Yes           | allow https behind a proxy                                                                            |
| lnbits_title                   | str                 | "LNbits API"                 | Yes           |                                                                                                       |
| lnbits_path                    | str                 | "."                          | Yes           |                                                                                                       |
| lnbits_extensions_path         | str                 | "lnbits"                     | Yes           | Path where extensions will be installed                                                               |
| super_user                     | str                 | ""                           | Yes           | ID of the super user. The user ID must exist.                                                         |
| auth_secret_key                | str                 | ""                           | Yes           | Secret Key: will default to the hash of the super user.                                               |
| version                        | str                 | "0.0.0"                      | Yes           |                                                                                                       |
| user_agent                     | str                 | ""                           | Yes           |                                                                                                       |
| enable_log_to_file             | bool                | True                         | Yes           | logging into LNBITS_DATA_FOLDER/logs/                                                                 |
| log_rotation                   | str                 | "100 MB"                     | Yes           | https://loguru.readthedocs.io/en/stable/api/logger.html#file                                          |
| log_retention                  | str                 | "3 months"                   | Yes           | https://loguru.readthedocs.io/en/stable/api/logger.html#file                                          |
| cleanup_wallets_days           | int                 | 90                           | Yes           | for database cleanup commands                                                                         |
| funding_source_max_retries     | int                 | 4                            | Yes           | How many times to retry connectiong to the Funding Source before defaulting to the VoidWallet         |
| lnbits_extensions_default_install | list[str]         | []                           | Yes           | Extensions to be installed by default.                                                                |
| lnbits_ext_github_token        | str                 | ""                           | Yes           | GitHub has rate-limits for its APIs. The limit can be increased specifying a GITHUB_TOKEN             |
| lnbits_data_folder             | str                 | "./data"                     | Yes           | Database: to use SQLite, specify LNBITS_DATA_FOLDER                                                   |
| lnbits_database_url            | str or None         | None                         | Yes           | Database: to use PostgreSQL, specify LNBITS_DATABASE_URL                                              |
| lnbits_allowed_funding_sources | list[str]           | See code                     | Yes           | which fundingsources are allowed in the admin ui                                                      |
| lnbits_admin_ui                | bool                | True                         | Yes           | Enable Admin GUI, available for the first user in LNBITS_ADMIN_USERS if available.                    |
| lnbits_admin_users             | list[str]           | []                           | No            | Allow users and admins by user IDs (comma separated list)                                             |
| lnbits_allowed_users           | list[str]           | []                           | No            | Allow users and admins by user IDs (comma separated list)                                             |
| lnbits_allow_new_accounts      | bool                | True                         | No            | Disable account creation for new users                                                                |
| lnbits_admin_extensions        | list[str]           | []                           | No            | Extensions only admin can access                                                                      |
| lnbits_user_default_extensions | list[str]           | []                           | No            | Extensions enabled by default when a user is created                                                  |
| lnbits_extensions_deactivate_all | bool              | False                        | No            | Start LNbits core only. The extensions are not loaded.                                                |
| lnbits_extensions_manifests    | list[str]           | See code                     | No            | LNBITS_EXTENSIONS_MANIFESTS URLs                                                                      |
| lnbits_site_title              | str                 | "LNbits"                     | No            | Change theme                                                                                          |
| lnbits_site_tagline            | str                 | "free and open-source lightning wallet" | No     | Change theme                                                                                          |
| lnbits_site_description        | str or None         | "The world's most powerful suite of bitcoin tools." | No | Change theme                                                                                          |
| lnbits_theme_options           | list[str]           | See code                     | No            | Choose from bitcoin, mint, flamingo, freedom, salvador, autumn, monochrome, classic, cyber            |
| lnbits_custom_logo             | str or None         | None                         | No            | LNBITS_CUSTOM_LOGO URL                                                                               |
| lnbits_default_wallet_name     | str                 | "LNbits wallet"              | No            | Change theme                                                                                          |
| lnbits_hide_api                | bool                | False                        | No            | Hides wallet api, extensions can choose to honor                                                      |
| lnbits_backend_wallet_class    | str                 | "VoidWallet"                 | No            | which fundingsources are allowed in the admin ui                                                      |
| lnbits_service_fee             | float               | 0.0                          | No            | the service fee (in percent)                                                                         |
| lnbits_service_fee_wallet      | str or None         | None                         | No            | the wallet where fees go to                                                                          |
| lnbits_service_fee_max         | int                 | 0                            | No            | the maximum fee per transaction (in satoshis)                                                        |
| lnbits_service_fee_ignore_internal | bool            | True                         | No            | disable fees for internal transactions                                                               |
| lnbits_reserve_fee_min         | int                 | 2000                         | No            | value in millisats                                                                                   |
| lnbits_reserve_fee_percent     | float               | 1.0                          | No            | value in percent                                                                                     |
| lnbits_wallet_limit_max_balance| int                 | 0                            | No            | limit the maximum balance for each wallet                                                            |
| lnbits_wallet_limit_daily_max_withdraw | int         | 0                            | No            | limit the maximum daily withdraw for each wallet                                                     |
| lnbits_wallet_limit_secs_between_trans | int         | 0                            | No            | limit the seconds between transactions                                                               |
| lnbits_allowed_ips             | list[str]           | []                           | No            | Server security, rate limiting ips, blocked ips, allowed ips                                         |
| lnbits_blocked_ips             | list[str]           | []                           | No            | Server security, rate limiting ips, blocked ips, allowed ips                                         |
| lnbits_rate_limit_no           | int                 | 200                          | No            | Server security, rate limiting ips, blocked ips, allowed ips                                         |
| lnbits_rate_limit_unit         | str                 | "minute"                     | No            | Server security, rate limiting ips, blocked ips, allowed ips                                         |
| lnbits_node_ui                 | bool                | False                        | No            | Enable Node Management without activating the LNBITS Admin GUI                                       |
| lnbits_public_node_ui          | bool                | False                        | No            | Enable Node Management without activating the LNBITS Admin GUI                                       |
| lnbits_node_ui_transactions    | bool                | False                        | No            | Enabling the transactions tab can cause crashes on large Core Lightning nodes.                       |
| auth_token_expire_minutes      | int                 | 525600                       | No            | AUTH_TOKEN_EXPIRE_MINUTES                                                                            |
| auth_allowed_methods           | list[str]           | ["user-id-only", "username-password"] | No | Possible authorization methods                                                                       |
| google_client_id               | str                 | ""                           | No            | Google OAuth Config                                                                                  |
| google_client_secret           | str                 | ""                           | No            | Google OAuth Config                                                                                  |
| github_client_id               | str                 | ""                           | No            | GitHub OAuth Config                                                                                  |
| github_client_secret           | str                 | ""                           | No            | GitHub OAuth Config                                                                                  |
| keycloak_client_id             | str                 | ""                           | No            | Keycloak OAuth Config                                                                                |
| keycloak_client_secret         | str                 | ""                           | No            | Keycloak OAuth Config                                                                                |
| keycloak_discovery_url         | str                 | ""                           | No            | Keycloak OAuth Config                                                                                |
| keycloak_client_custom_org     | str or None         | None                         | No            | Keycloak OAuth Config                                                                                |
| keycloak_client_custom_icon    | str or None         | None                         | No            | Keycloak OAuth Config                                                                                |

# ...additional fields omitted for brevity...




### Creation Prompt
```
create a markup table with the fields present in the Settings class (in settings.py) inherited from parent classes.
columns:

- name
- type
- default value
- env file only (yes/no - depending if the field is part of ReadOnlySettings class)
- description (if a comment is present in the .env.example right before the field then use that comment with the # removed)
- do NOT ommit any field
- save the output in settings.md
```
