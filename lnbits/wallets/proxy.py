from httpx_socks import AsyncProxyTransport
from httpx._config import SSLConfig
from python_socks import ProxyType

from ..settings import FUNDING_PROXY_HOST, FUNDING_PROXY_PORT


def get_httpx_transport(cert):
    if FUNDING_PROXY_HOST is None or FUNDING_PROXY_PORT is None:
        return None

    ssl_context = SSLConfig(
        # Without this it appears CERTIFICATE_VERIFY_FAILED is emitted
        # resulting in a hypercorn.utils.LifespanFailure: Lifespan failure in startup. '' of lnbits
        verify=False
    ).ssl_context
    return AsyncProxyTransport(
        proxy_type=ProxyType.SOCKS5,
        proxy_host=FUNDING_PROXY_HOST,
        proxy_port=FUNDING_PROXY_PORT,
        username=None,
        password=None,
        rdns=None,
        http2=True,
        ssl_context=ssl_context,
        verify=cert,
        cert=None,
        trust_env=True,
    )
