from lnbits.settings import FiatProviderLimits, settings


def get_fiat_providers_for_user(user_id: str) -> list[str]:
    """
    Returns a list of fiat payment methods allowed for the user.
    """
    allowed_providers = []
    if settings.stripe_enabled and (
        not settings.stripe_limits.allowed_users
        or user_id in settings.stripe_limits.allowed_users
    ):
        allowed_providers.append("stripe")

    # Add other fiat providers here as needed
    return allowed_providers


def get_fiat_provider_limits(provider: str) -> FiatProviderLimits | None:
    """
    Returns the limits for a specific fiat provider.
    """
    return getattr(settings, provider + "_limits", None)


def is_fiat_provider_enabled(provider: str) -> bool:
    """
    Checks if a specific fiat provider is enabled.
    """
    return getattr(settings, provider + "_enabled", False)
