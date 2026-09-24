# Two factor authentication

LNbits supports Google Authenticator, Ente Auth, Aegis and other standard TOTP apps.
No registration with an authenticator provider is needed. Codes have six digits and
a 30-second period. Keep the server clock synchronized.

## Operator setup

1. Generate a key with `uv run lnbits-cli two-factor generate-key`.
2. Store its output as `TOTP_ENCRYPTION_KEY` in the server environment or protected
   configuration outside the data directory. It is 32 random bytes encoded as 64 hex
   characters. Restart LNbits to load it.
3. Back up the key securely, separately from database/data-directory backups. Keep
   it stable across restarts and all workers. LNbits never automatically replaces a
   missing key. Rotation requires re-encrypting stored secrets using the old key;
   simply replacing it makes existing authenticators unreadable.
4. Under **Settings → Two Factor Auth**, enable 2FA and select **Authenticator app (TOTP)**.
5. Under **Account → Two Factor Auth (2FA)**, enroll your authenticator and save the
   ten recovery codes. Confirm that you have saved them.
6. Optionally enable **Require 2FA for all users**. The acting admin must already have
   an enrolled authenticator, saved recovery codes and recent verification.

`TwoFactorSettings` contains `lnbits_two_factor_enabled`,
`lnbits_two_factor_methods` (currently only `totp`), and
`lnbits_two_factor_mandatory`. The feature and mandatory policy default to off.
`totp_encryption_key` is never part of editable or public settings.

## Login and policy

Enrollment activates only after a valid code is entered. Pending setup is not an
active factor. Setup and login challenges expire after five minutes. Starting and
confirming enrollment also require a recent first-factor login; log in again if asked.

Password, Nostr, SSO, user-ID login, and password-reset login apply the local 2FA
policy. User-ID login remains unavailable to admins. Direct `?usr=` access cannot
bypass verification. Users subject to mandatory enrollment can only complete setup
until verified; restricted login and account-creation responses expose no wallet keys.

Sensitive account changes require recent verification using the existing
`auth_credetials_update_threshold` (120 seconds by default). Verify a fresh code
in your account's 2FA section before changing security settings. There is no separate
remembered-device exception. Existing session expiry settings still apply.

An accepted code cannot be reused, including simultaneous requests. Wait for the next
code if one was just used for enrollment or login. Five failed attempts block further
verification for the remainder of a 15-minute window. New challenges and server
restarts do not reset the attempt counter.

Global **OFF** stops requiring 2FA for everyone, including admins, even when mandatory
enrollment was selected. Encrypted secrets, recovery codes and replay state remain.
Global **ON** restores enforcement for existing sessions and new logins.

## Recovery

Use a recovery code instead of an authenticator code after the first login step.
Each works once. Store them separately from your phone. Regenerating them invalidates
the old set. Email is not an alternative verification method.

An operator with access to the server and database can run:

```sh
uv run lnbits-cli two-factor reset USER_ID
```

The command asks for confirmation, clears that account's factor and recovery codes,
and changes its security revision. With 2FA enabled, old sessions are rejected.
The account must log in again; mandatory policy still requires enrollment. The command
does not change passwords or global policy. No remote admin reset endpoint is provided.
If the encryption key was lost, restore it before enrolling again.

## Storage and integration boundaries

Private JSON in `accounts.two_factor` is accessed by dedicated CRUD functions and
excluded from ordinary `Account`, `User` and admin account responses. There is no
`is_2fa_enabled` column. An authenticated account can obtain safe status from
`/api/v1/auth/2fa/status`.

Secrets are encrypted using AES-GCM and bound to the account ID. Recovery codes are
hashed. Conditional database updates make code consumption atomic. Login challenges
use a separate HTTP-only cookie and cannot authenticate ordinary API requests.
Authentication bodies are excluded from audit details; security logs contain no codes.

Wallet API keys and scoped automation tokens continue to work. **Login 2FA does not
stop spending with a stolen spending key.** Automation cannot configure 2FA or bypass
protected security changes. Impersonation requires fresh admin MFA while enabled
and cannot change the target account's security.
