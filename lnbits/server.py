import time

import click
import uvicorn

from lnbits.settings import HOST, PORT


@click.command(
    context_settings=dict(
        ignore_unknown_options=True,
        allow_extra_args=True,
    )
)
@click.option("--port", default=PORT, help="Port to listen on")
@click.option("--host", default=HOST, help="Host to run LNBits on")
@click.option("--ssl-keyfile", default=None, help="Path to SSL keyfile")
@click.option("--ssl-certfile", default=None, help="Path to SSL certificate")
@click.pass_context
def main(ctx, port: int, host: str, ssl_keyfile: str, ssl_certfile: str):
    """Launched with `poetry run lnbits` at root level"""
    # this beautiful beast parses all command line arguments and passes them to the uvicorn server
    d = dict()
    for a in ctx.args:
        item = a.split("=")
        if len(item) > 1:  # argument like --key=value
            print(a, item)
            d[item[0].strip("--").replace("-", "_")] = (
                int(item[1])  # need to convert to int if it's a number
                if item[1].isdigit()
                else item[1]
            )
        else:
            d[a.strip("--")] = True  # argument like --key

    config = uvicorn.Config(
        "lnbits.__main__:app",
        port=port,
        host=host,
        ssl_keyfile=ssl_keyfile,
        ssl_certfile=ssl_certfile,
        **d
    )
    server = uvicorn.Server(config)
    server.run()


if __name__ == "__main__":
    main()
