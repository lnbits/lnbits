# Generic OIDC Authentication Configuration

This document explains how to configure generic OIDC authentication for LNbits, which allows integration with various OIDC-compliant authentication providers such as Zitadel, Authentik, and others.

## Overview

The generic OIDC provider (`oidc`) complements the existing Keycloak provider and allows you to integrate any OIDC-compliant authentication service. You can customize the login button with your own organization name and icon.

## Configuration

Add the following environment variables to your `.env` file or system environment:

### Required Settings

```bash
# Enable OIDC authentication
LNBITS_AUTH_ALLOWED_METHODS=oidc-auth

# OIDC Discovery URL (well-known endpoint)
LNBITS_OIDC_DISCOVERY_URL=https://your-oidc-provider-domain/.well-known/openid-configuration

# Client credentials from your OIDC provider
LNBITS_OIDC_CLIENT_ID=your-client-id
LNBITS_OIDC_CLIENT_SECRET=your-client-secret
```

### Optional Settings - Customize the Login Button

You can customize how the OIDC login button appears to your users:

```bash
# Custom organization name (displayed on the login button)
# Example: "Login via Zitadel" or "Login via Authentik"
LNBITS_OIDC_CLIENT_CUSTOM_ORG="Zitadel"

# Custom icon URL (displayed on the login button)
# Can be a full URL or a path to a local image
LNBITS_OIDC_CLIENT_CUSTOM_ICON=https://zitadel.com/favicon.svg
```

If not set, the button will display "Login via OIDC" with a generic lock icon.

## Zitadel Configuration Example

For Zitadel, configure as follows:

1. Create a new application in Zitadel
2. Choose "Web" application type
3. Configure the redirect URI: `https://your-lnbits-domain/api/v1/auth/oidc/token`
4. Save the Client ID and Client Secret
5. Use these environment variables:

```bash
LNBITS_AUTH_ALLOWED_METHODS=oidc-auth
LNBITS_OIDC_DISCOVERY_URL=https://your-oidc-provider-domain/.well-known/openid-configuration
LNBITS_OIDC_CLIENT_ID=your-zitadel-client-id
LNBITS_OIDC_CLIENT_SECRET=your-zitadel-client-secret
# Customize the button to show "Login via Zitadel" with Zitadel's logo
LNBITS_OIDC_CLIENT_CUSTOM_ORG="Zitadel"
LNBITS_OIDC_CLIENT_CUSTOM_ICON="https://zitadel.com/favicon.svg"
```

**Result**: The login page will display a button with the text "Login via Zitadel" and the Zitadel logo.

## Authentik Configuration Example

For Authentik:

1. Create a new OAuth2/OpenID Provider
2. Set the redirect URI: `https://your-lnbits-domain/api/v1/auth/oidc/token`
3. Configure scopes: `openid`, `email`, `profile`
4. Get the Client ID and Client Secret

```bash
LNBITS_AUTH_ALLOWED_METHODS=oidc-auth
LNBITS_OIDC_DISCOVERY_URL=https://authentik.yourdomain.com/application/o/your-app/.well-known/openid-configuration
LNBITS_OIDC_CLIENT_ID=your-authentik-client-id
LNBITS_OIDC_CLIENT_SECRET=your-authentik-client-secret
LNBITS_OIDC_CLIENT_CUSTOM_ORG="Authentik"
```

## Multiple Auth Methods

You can enable multiple authentication methods simultaneously:

```bash
LNBITS_AUTH_ALLOWED_METHODS=username-password,oidc-auth,keycloak-auth
```

## Discovery Endpoint Requirements

Your OIDC provider must expose a standard discovery endpoint (`.well-known/openid-configuration`) that includes:

- `authorization_endpoint`
- `token_endpoint`
- `userinfo_endpoint`
- `jwks_uri` (JSON Web Key Set)

The OIDC implementation will automatically fetch these endpoints from the discovery URL.

## User Mapping

The OIDC provider maps user information from the OIDC userinfo endpoint:

- `sub` → User ID
- `email` → Email address
- `given_name` → First name
- `family_name` → Last name
- `name` or `preferred_username` → Display name
- `picture` → Profile picture URL

## Troubleshooting

### Authentication fails

1. Verify the discovery URL is accessible
2. Check that Client ID and Client Secret are correct
3. Ensure redirect URI in your OIDC provider matches: `https://your-lnbits-domain/api/v1/auth/oidc/token`
4. Check LNbits logs for detailed error messages

### User info not populated

Some OIDC providers may use different claim names. If user information is not correctly populated, check your provider's userinfo endpoint response format and adjust the provider class if needed.

## Security Considerations

- Always use HTTPS in production
- Keep client secrets secure and never commit them to version control
- Use environment variables or secure configuration management
- Regularly rotate client secrets
- Review OIDC provider's security best practices

## Implementation Details

The OIDC provider is implemented in `lnbits/core/models/sso/oidc.py` and extends the `fastapi_sso` library's `SSOBase` class. It uses the standard OpenID Connect flow with:

- Scopes: `openid`, `email`, `profile`
- Response type: `code` (authorization code flow)
- Discovery document for automatic endpoint resolution
