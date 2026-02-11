"""Test OIDC authentication settings."""

from lnbits.settings import AuthMethods, Settings


def test_oidc_auth_method_exists():
    """Test that OIDC auth method is available."""
    assert hasattr(AuthMethods, "oidc_auth")
    assert AuthMethods.oidc_auth.value == "oidc-auth"


def test_oidc_settings_structure(settings: Settings):
    """Test that OIDC settings have the correct structure."""
    # Verify OIDC settings attributes exist
    assert hasattr(settings, "oidc_discovery_url")
    assert hasattr(settings, "oidc_client_id")
    assert hasattr(settings, "oidc_client_secret")
    assert hasattr(settings, "oidc_client_custom_org")
    assert hasattr(settings, "oidc_client_custom_icon")


def test_oidc_settings_defaults(settings: Settings):
    """Test that OIDC settings have correct default values."""
    assert settings.oidc_discovery_url == ""
    assert settings.oidc_client_id == ""
    assert settings.oidc_client_secret == ""
    assert settings.oidc_client_custom_org is None
    assert settings.oidc_client_custom_icon is None


def test_oidc_public_settings(settings: Settings):
    """Test that OIDC public settings are accessible."""
    # Verify that custom org and icon fields exist
    # These are used in the frontend for customizing the OIDC login button
    assert hasattr(settings, "oidc_client_custom_org")
    assert hasattr(settings, "oidc_client_custom_icon")

    # Verify the values match expectations for public settings
    # When custom values are set, they should be accessible
    assert settings.oidc_client_custom_org is None or isinstance(
        settings.oidc_client_custom_org, str
    )
    assert settings.oidc_client_custom_icon is None or isinstance(
        settings.oidc_client_custom_icon, str
    )
